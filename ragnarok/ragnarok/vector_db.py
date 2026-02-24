# -*- coding: utf-8 -*-
"""
    ragnarok.vector_db
    ~~~~~~~~~~~~~~~~~~

    Vector database integration.
"""

import copy
import hashlib
import os
import time
import uuid
from datetime import datetime
from tempfile import NamedTemporaryFile
from typing import Any

import requests
from cachetools.func import lru_cache
from dateutil import tz
from elastic_transport.client_utils import DefaultType as ESDefaultType
from elasticsearch import Elasticsearch, helpers
from langchain.embeddings.base import Embeddings
from langchain_community.document_loaders import BSHTMLLoader, PyMuPDFLoader, TextLoader
from langchain_community.vectorstores import ElasticsearchStore
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from common.config import CONFIG, PATH_ES_CERT
from common.core import get_component_logger
from common.core.logger_utils import log_elapsed_time
from common.models import defaults as df, elastic as me
from common.models.enums import SourceType
from common.models.project import EmbeddingModelSettings, RetrievalSettings
from common.utils import exceptions as exc
from common.utils.misc import dict_to_dot_keys, generate_batches
from common.utils.singleton import Singleton
from ragnarok.document_loaders import OpenPyXLLoader, PyDOCXLoader, PyPPTXLoader
from ragnarok.utils import highlight as hl, lc

logger = get_component_logger()

DEFAULT_INDEX_SETTINGS = {
    "mappings": {
        "properties": {
            "metadata": {
                "properties": {
                    # ID fields
                    "kb_id": {"type": "keyword", "ignore_above": 256},
                    "project_id": {"type": "keyword", "ignore_above": 256},
                    "user_id": {"type": "keyword", "ignore_above": 256},

                    # Text/keyword fields
                    "embedding_model": {"type": "keyword", "ignore_above": 256},
                    "language": {"type": "keyword", "ignore_above": 256},
                    "source_file": {"type": "keyword", "ignore_above": 1024},
                    "source_type": {"type": "keyword", "ignore_above": 256},

                    # Non-text fields
                    "created_at": {"type": "date"},
                    "page": {"type": "integer"},
                    "total_pages": {"type": "integer"},

                    # Custom object field - gets populated dynamically
                    "custom": {
                        "properties": {
                            "program_name": {
                                "type": "text",
                                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
                            },
                        },
                    },
                },
            },
            "text": {
                "type": "text",
                "analyzer": "standard_lowercase",
            },
            "vector": {
                "type": "dense_vector",
                "dims": 2048,
                "index": True,
                "similarity": "cosine",
            },
        },
    },
    "settings": {
        "analysis": {"analyzer": {"standard_lowercase": {"tokenizer": "standard", "filter": ["lowercase"]}}},
        "number_of_replicas": 1,
        "number_of_shards": 1,
    },
}

DEFAULT_INDEX_SETTINGS_HIGHLIGHTS = copy.deepcopy(DEFAULT_INDEX_SETTINGS)
DEFAULT_INDEX_SETTINGS_HIGHLIGHTS["mappings"]["properties"]["metadata"]["properties"].update({
    "original_es_id": {"type": "keyword"},
    "source_document_id": {"type": "keyword"},

    "doc_hash": {"type": "keyword"},
    "parent_chunk_id": {"type": "keyword"},
    "chunk_level": {"type": "keyword"},
    "chunk_index": {"type": "integer"},

    "text_length": {"type": "integer"},
    "char_start": {"type": "integer"},
    "char_end": {"type": "integer"},
})
# noinspection PyTypeChecker
DEFAULT_INDEX_SETTINGS_HIGHLIGHTS["settings"]["index.max_result_window"] = 20000

ES_INDEX_REPLACE_CHARS = ' "#*+,./:<>?\\_|'
ES_INDEX_TRANSLATOR = str.maketrans({x: "-" for x in ES_INDEX_REPLACE_CHARS})

MAX_RETRIES = 3
RETRY_DELAY = 10


class VectorStore(metaclass=Singleton):

    def __init__(self):
        self.index_name = CONFIG.ES_INDEX_EMBEDDINGS
        self.index_name_highlights = CONFIG.ES_INDEX_HIGHLIGHT_CHUNKS
        self._embeddings: dict[str, Embeddings] = {}

        self.es = Elasticsearch(
            hosts=str(CONFIG.ES_URL),
            basic_auth=(CONFIG.ES_USER, CONFIG.ES_PASSWORD.get_secret_value()),
            ca_certs=PATH_ES_CERT if PATH_ES_CERT.exists() else ESDefaultType.value,
            timeout=30,
        )

    @lru_cache(maxsize=64)
    def get_index_name(self, model_name: str) -> str:
        return f"{self.index_name}_{self._normalize_model_name(model_name)}"

    @lru_cache(maxsize=64)
    def get_index_name_highlights(self, model_name: str) -> str:
        return f"{self.index_name_highlights}_{self._normalize_model_name(model_name)}"

    @staticmethod
    def _normalize_model_name(model_name: str) -> str:
        """Normalize model name to be used as an index name."""

        # FixMe: Hack to handle indices with old model names -> rename indices and remove this.
        if model_name == "text-embedding-3-large":
            return "openai-3-large"

        return model_name.translate(ES_INDEX_TRANSLATOR).lower()

    def _prepare_embedding_index(self, name: str, base_settings: dict[str, Any], dim: int):
        """Create embedding index if it does not already exist."""

        if self.es.indices.exists(index=name):
            return

        logger.info("Preparing ElasticSearch index %s", name)
        settings = copy.deepcopy(base_settings)
        settings["mappings"]["properties"]["vector"]["dims"] = dim
        self.es.indices.create(index=name, body=settings)

    def _prepare_embedding_model(self, emb_settings: EmbeddingModelSettings) -> Embeddings:
        """
        Retrieve or prepare embedding model instance and set up default indices.

        :param emb_settings: embedding model settings
        :return: LangChain embedding model instance
        """

        if model := self._embeddings.get(emb_settings.name):
            return model

        model, dim = lc.get_embeddings(settings=emb_settings)

        # Prepare index for main chunk embeddings
        self._prepare_embedding_index(
            name=self.get_index_name(emb_settings.name),
            base_settings=DEFAULT_INDEX_SETTINGS,
            dim=dim,
        )

        # Prepare index for highlight chunk embeddings
        self._prepare_embedding_index(
            name=self.get_index_name_highlights(emb_settings.name),
            base_settings=DEFAULT_INDEX_SETTINGS_HIGHLIGHTS,
            dim=dim,
        )

        self._embeddings[emb_settings.name] = model
        return model

    def _embed_and_store(
            self,
            batches: dict[str, list[Document]],
            emb_settings: EmbeddingModelSettings,
            retries: int = 0,
    ):
        """
        Embed document batches and store them in ES.

        Retry upload for batches that failed to upload to ES.

        :param batches: batches dict with batch IDs as keys and document batches as values
        :param emb_settings: embedding model settings
        :param retries: number of retries so far
        """

        if not batches:
            return

        if retries > MAX_RETRIES:
            logger.warning("Max upload retries reached - batches failed to upload: %s", batches.keys())
            return

        if retries > 0:
            logger.warning("Failed to upload %d batch(es) --> retrying after %d seconds", len(batches), RETRY_DELAY)
            time.sleep(RETRY_DELAY)

        failed_batches = {}
        index_name = self.get_index_name(model_name=emb_settings.name)
        embedding = self._prepare_embedding_model(emb_settings=emb_settings)

        def _count_uploaded_docs(bid: str) -> int:
            return self.es.count(index=index_name, query={"term": {"metadata.batch_id.keyword": bid}})["count"]

        def _delete_batch(bid: str):
            self.es.delete_by_query(index=index_name, query={"term": {"metadata.batch_id.keyword": bid}})

        for batch_id, doc_batch in batches.items():
            logger.debug("(Re)trying upload of document batch %s (%d documents)", batch_id, len(doc_batch))

            if retries > 0:
                if _count_uploaded_docs(batch_id) == len(doc_batch):
                    logger.debug("Document batch %s already present in ES --> skipping", batch_id)
                    continue
                _delete_batch(batch_id)

            for doc in doc_batch:
                doc.metadata["batch_id"] = batch_id
                doc.metadata["retries"] = retries

            try:
                ElasticsearchStore.from_documents(
                    documents=doc_batch,
                    embedding=embedding,
                    es_connection=self.es,
                    index_name=index_name,
                )

            except Exception as e:
                logger.warning("Failed to upload batch %s: %s", batch_id, e)
                failed_batches[batch_id] = doc_batch

        self.es.indices.refresh(index=index_name)
        self._embed_and_store(batches=failed_batches, emb_settings=emb_settings, retries=retries + 1)

    def _index_highlighting(self, documents: list[Document], emb_settings: EmbeddingModelSettings):
        """
        Index hierarchical chunks for highlighting (no separate pages index).

        Steps:
          - Cleans existing KB entries once.
          - Builds L0/L1 chunks with canonical IDs.
          - Embeds + indexes in token-aware batches to avoid limits.

        :param documents: input documents
        :param emb_settings: embedding model settings
        """

        chunks_index = self.get_index_name_highlights(model_name=emb_settings.name)
        page_docs: list[dict[str, Any]] = []

        for doc in documents:
            md = dict(doc.metadata)
            raw_id = f"{md.get('project_id')}|{md.get('kb_id')}|{md.get('source_file')}|{md.get('page')}"
            doc_id = hashlib.md5(raw_id.encode("utf-8")).hexdigest()
            text = doc.page_content

            page_docs.append({
                "id": doc_id,
                "text": text,
                "metadata": {
                    "kb_id": md.get("kb_id"),
                    "project_id": md.get("project_id"),
                    "source_file": md.get("source_file"),
                    "source_type": md.get("source_type"),
                    "language": md.get("language"),
                    "embedding_model": md.get("embedding_model", emb_settings.name),
                    "created_at": md.get("created_at") or datetime.now(tz=tz.UTC).isoformat(),
                    "page": md.get("page"),
                    "text_length": len(text or ""),
                    "original_es_id": md.get("id"),
                    "doc_hash": hashlib.md5((text or "").encode("utf-8")).hexdigest()[:12],
                },
            })

        if not page_docs:
            return

        # Create hierarchical chunks
        chunks = hl.create_hierarchical_chunks(
            documents=page_docs,
            l0_size=1200,
            l0_overlap=300,
            l1_size=700,
            l1_overlap=175,
            separators=["\n\n", "\n", ". ", ", ", " "],
        )

        if not chunks:
            return

        # Stream batches: embed then bulk index
        embedding = self._prepare_embedding_model(emb_settings=emb_settings)

        for batch in hl.generate_chunk_batches(chunks):
            vectors = embedding.embed_documents([c["text"] for c in batch])

            def gen_batch():
                for i, c in enumerate(batch):
                    c_meta = c.setdefault("metadata", {})
                    c_meta["text_length"] = len(c.get("text") or "")

                    # Use canonical id if present; otherwise compute the same char-range id
                    cid = c_meta.get("chunk_id") or hl.make_chunk_id(
                        source_document_id=c_meta["source_document_id"],
                        level=c_meta["chunk_level"],
                        start=c_meta["char_start"],
                        end=c_meta["char_end"],
                    )

                    yield {"_index": chunks_index, "_id": cid, "_source": {**c, "vector": vectors[i]}}

            helpers.bulk(self.es, gen_batch())

        # One refresh at the end
        self.es.indices.refresh(index=chunks_index)

    def upload_file(
            self,
            content: bytes,
            kb_id: str,
            project_id: str | None = None,
            source_file: str = "",
            source_type: SourceType = SourceType.PDF,
            language: str = df.LANG,
            emb_settings: EmbeddingModelSettings | None = None,
            custom_metadata: dict[str, Any] | None = None,
            enable_highlights: bool = False,
    ) -> me.KBMetadata:
        """
        Parse file contents and upload to vector DB.

        :param content: binary file content
        :param kb_id: knowledge base ID
        :param project_id: project ID
        :param source_file: source file name (path)
        :param source_type: type/format of the content (e.g. PDF)
        :param language: text language
        :param emb_settings: embedding model settings
        :param custom_metadata: custom metadata
        :param enable_highlights: build and index chunks required for the highlighting functionality
        :return: metadata of the uploaded knowledge base
        """

        emb_settings = emb_settings or EmbeddingModelSettings()
        self._prepare_embedding_model(emb_settings=emb_settings)
        documents = self._parse_file(content=content, source_type=source_type)

        metadata = {
            "kb_id": kb_id,
            "project_id": project_id,
            "source_file": source_file,
            "source_type": source_type.value,
            "language": language,
            "embedding_model": emb_settings.name,
            "custom": custom_metadata or {},
            "created_at": datetime.now(tz=tz.UTC).isoformat(),
        }

        for doc in documents:
            doc.metadata = {
                "author": doc.metadata.get("author", ""),
                "page": doc.metadata.get("page", 0) + 1,
                "title": doc.metadata.get("title", ""),
                "total_pages": doc.metadata.get("total_pages", 1),
            }

            doc.metadata.update(metadata)

            # Add source file name/path to the content
            doc.page_content = f"SOURCE FILE: {source_file}\n\n{doc.page_content}"

        # Remove already existing data for given knowledge base ID
        self.delete_kb(kb_id=kb_id, project_id=project_id, raise_not_found=False)

        # Embed and store the documents in the vector DB
        batches = {str(uuid.uuid4()): doc_batch for doc_batch in generate_batches(documents, 50)}
        self._embed_and_store(batches=batches, emb_settings=emb_settings)

        # Build and index highlighting chunks for these documents (best-effort)
        if enable_highlights:
            try:
                self._index_highlighting(documents=documents, emb_settings=emb_settings)
            except Exception as e:
                logger.warning("Highlight indexing failed (non-blocking): %s", e)

        return me.KBMetadata.model_validate(documents[0].metadata)

    def upload_url(
            self,
            url: str,
            kb_id: str,
            project_id: str | None = None,
            language: str = df.LANG,
            emb_settings: EmbeddingModelSettings | None = None,
            custom_metadata: dict[str, Any] | None = None,
            enable_highlights: bool = False,
    ) -> me.KBMetadata:
        """
        Download HTML content from a given URL, parse it, and upload to vector DB.

        :param url: input URL
        :param kb_id: knowledge base ID
        :param project_id: project ID
        :param language: text language
        :param emb_settings: embedding model settings
        :param custom_metadata: custom metadata
        :param enable_highlights: build and index chunks required for the highlighting functionality
        :return: metadata of the uploaded knowledge base
        """

        return self.upload_file(
            content=requests.get(url, timeout=(10, 30)).content,
            kb_id=kb_id,
            project_id=project_id,
            source_file=url,
            source_type=SourceType.HTML,
            language=language,
            emb_settings=emb_settings,
            custom_metadata=custom_metadata,
            enable_highlights=enable_highlights,
        )

    def _parse_file(self, content: bytes, source_type: SourceType) -> list[Document]:
        """
        Parse file contents.

        :param content: binary file content
        :param source_type: type/format of the content (e.g. PDF)
        :return: parsed documents
        """

        tmp_file = NamedTemporaryFile(delete=False, suffix=f".{source_type.value}")
        tmp_file.write(content)
        tmp_file.close()

        if source_type == SourceType.DOCX:
            documents = self._parse_docx(tmp_file.name)
        elif source_type == SourceType.HTML:
            documents = self._parse_html(tmp_file.name)
        elif source_type == SourceType.PDF:
            documents = self._parse_pdf(tmp_file.name)
        elif source_type == SourceType.PPTX:
            documents = self._parse_pptx(tmp_file.name)
        elif source_type == SourceType.TXT:
            documents = self._parse_txt(tmp_file.name)
        elif source_type == SourceType.XLSX:
            documents = self._parse_xlsx(tmp_file.name)
        else:
            raise ValueError(f"Unsupported source type: {source_type.value}")

        os.remove(tmp_file.name)
        return documents

    @staticmethod
    def _parse_docx(path: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> list[Document]:
        loader = PyDOCXLoader(path)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        return loader.load_and_split(text_splitter)

    @staticmethod
    def _parse_html(path: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> list[Document]:
        loader = BSHTMLLoader(path)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        return loader.load_and_split(text_splitter)

    @staticmethod
    def _parse_pdf(path: str) -> list[Document]:
        # text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        # return PyMuPDFLoader(path).load_and_split(text_splitter)
        return PyMuPDFLoader(path).load()

    @staticmethod
    def _parse_pptx(path: str) -> list[Document]:
        return PyPPTXLoader(path).load()

    @staticmethod
    def _parse_txt(path: str, chunk_size: int = 1000, chunk_overlap: int = 100) -> list[Document]:
        loader = TextLoader(path)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        return loader.load_and_split(text_splitter)

    @staticmethod
    def _parse_xlsx(path: str) -> list[Document]:
        return OpenPyXLLoader(path).load()

    @log_elapsed_time
    def knn_search(
            self,
            query: str,
            project_id: str,
            kb_ids: list[str] | None = None,
            settings: RetrievalSettings | None = None,
            ftr_custom: list[dict[str, Any]] | None = None,
    ) -> list[me.KBEntry]:
        """
        Perform a KNN vector search for a given query.

        :param query: user query
        :param project_id: project ID
        :param kb_ids: knowledge base IDs to include (None for all project documents)
        :param settings: retrieval settings
        :param ftr_custom: custom filters added to the default ones
        :return: search operation result
        """

        settings = settings or RetrievalSettings()
        embeddings = self._prepare_embedding_model(emb_settings=settings.model)
        ftr = [{"term": {"metadata.project_id": project_id}}]

        if kb_ids:
            ftr_should = [{"term": {"metadata.kb_id": _id}} for _id in kb_ids]
            # noinspection PyTypeChecker
            ftr.append({"bool": {"should": ftr_should}})

        if ftr_custom:
            ftr.extend(ftr_custom)

        res = self.es.search(
            index=self.get_index_name(model_name=settings.model.name),
            knn={
                "field": "vector",
                "query_vector": embeddings.embed_query(query),
                "k": settings.k_emb,
                "num_candidates": settings.num_candidates,
                "filter": ftr,
            },
            size=settings.k_emb,
            source_excludes="vector",
        )

        if res["hits"]["total"]["value"] == 0:
            raise exc.DBRecordNotFound(kb_ids)
        return [me.KBEntry.model_validate(x) for x in res["hits"]["hits"]]

    @log_elapsed_time
    def bm25_search(
            self,
            query: str,
            project_id: str,
            kb_ids: list[str] | None = None,
            settings: RetrievalSettings | None = None,
            ftr_custom: list[dict[str, Any]] | None = None,
    ):
        """
        Perform a text search (BM25) for a given query.

        :param query: user query
        :param project_id: project ID
        :param kb_ids: knowledge base IDs to include (None for all project documents)
        :param settings: retrieval settings
        :param ftr_custom: custom filters added to the default ones
        :return: search operation result
        """

        settings = settings or RetrievalSettings()
        ftr = [{"term": {"metadata.project_id": project_id}}]

        if kb_ids:
            ftr_should = [{"term": {"metadata.kb_id": _id}} for _id in kb_ids]
            # noinspection PyTypeChecker
            ftr.append({"bool": {"should": ftr_should}})

        if ftr_custom:
            ftr.extend(ftr_custom)

        res = self.es.search(
            index=self.get_index_name(settings.model.name),
            query={
                "bool": {
                    "must": {"match": {"text": query}},
                    "filter": ftr,
                },
            },
            size=settings.k_bm25,
            source_excludes="vector",
        )

        return [me.KBEntry.model_validate(x) for x in res["hits"]["hits"]]

    def get_kb_metadata(self, kb_id: str, project_id: str | None = None) -> me.KBMetadata:
        """Get general metadata for a given knowledge base."""

        query = {"bool": {"filter": [{"term": {"metadata.kb_id": kb_id}}]}}
        if project_id:
            query["bool"]["filter"].append({"term": {"metadata.project_id": project_id}})

        res = self.es.search(
            index=f"{self.index_name}_*",
            query=query,
            size=1,
            source_includes="metadata",
        )

        if res["hits"]["total"]["value"] == 0:
            raise exc.DBRecordNotFound(kb_id)

        output = res["hits"]["hits"][0]["_source"]["metadata"]
        output.pop("page", None)
        return me.KBMetadata.model_validate(output)

    def get_kb_page(self, kb_id: str, page: int = 1, project_id: str | None = None) -> me.KBEntry:
        """Get knowledge base data for one parsed page."""

        query = {
            "bool": {
                "filter": [
                    {"term": {"metadata.kb_id": kb_id}},
                    {"term": {"metadata.page": page}},
                ],
            },
        }

        if project_id:
            query["bool"]["filter"].append({"term": {"metadata.project_id": project_id}})

        res = self.es.search(
            index=f"{self.index_name}_*",
            query=query,
            size=1,
            source_excludes="vector",
        )

        if res["hits"]["total"]["value"] == 0:
            raise exc.DBRecordNotFound(kb_id)
        return me.KBEntry.model_validate(res["hits"]["hits"][0])

    def get_kb_ids(self, project_id: str | None = None) -> list[str]:
        """Get a list of available knowledge base IDs."""

        res = self.es.search(
            index=f"{self.index_name}_*",
            query={"bool": {"filter": {"term": {"metadata.project_id": project_id}}}} if project_id else None,
            aggs={"kb_ids": {"terms": {"field": "metadata.kb_id", "size": 10000}}},
            size=0,
        )

        if not (buckets := res["aggregations"]["kb_ids"]["buckets"]):
            raise exc.DBRecordNotFound(project_id)
        return [x["key"] for x in buckets]

    def get_project_ids(self) -> list[str]:
        """Get a list of available project IDs."""

        res = self.es.search(
            index=f"{self.index_name}_*",
            aggs={"project_ids": {"terms": {"field": "metadata.project_id", "size": 10000}}},
            size=0,
        )

        if "aggregations" not in res:
            return []
        return [x["key"] for x in res["aggregations"]["project_ids"]["buckets"]]

    def update_kb_metadata(
            self,
            kb_id: str,
            metadata: dict[str, Any],
            project_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Update the metadata for a given knowledge base ID.

        :param kb_id: knowledge base ID
        :param metadata: dict with updated metadata
        :param project_id: project ID
        :return: update by query operation response
        """

        def _format_value(v) -> str:
            if isinstance(v, str):
                return f"'{v}'"
            if v is None:
                return "null"
            return str(v)

        metadata = dict_to_dot_keys(metadata, prefix="ctx._source.metadata")
        scripts = [f"{k}={_format_value(v)}" for k, v in metadata.items()]

        query = {"bool": {"filter": [{"term": {"metadata.kb_id": kb_id}}]}}
        if project_id:
            query["bool"]["filter"].append({"term": {"metadata.project_id": project_id}})

        res = self.es.update_by_query(
            index=f"{self.index_name}_*",
            query=query,
            script={
                "source": ";".join(scripts),
                "lang": "painless",
            },
        )

        return dict(res.body)

    def delete_kb(self, kb_id: str, project_id: str | None = None, raise_not_found: bool = False) -> tuple[int, int]:
        """
        Delete knowledge base data by knowledge base ID.

        :param kb_id: knowledge base ID
        :param project_id: project ID
        :param raise_not_found: raise exception on 0 matches
        :return: deleted counts - main index, highlights index
        """

        query = {"bool": {"filter": [{"term": {"metadata.kb_id": kb_id}}]}}
        if project_id:
            query["bool"]["filter"].append({"term": {"metadata.project_id": project_id}})

        deleted = self.es.delete_by_query(index=f"{self.index_name}_*", query=query)["deleted"]
        deleted_hl = self.es.delete_by_query(index=f"{self.index_name_highlights}_*", query=query)["deleted"]

        if raise_not_found and deleted + deleted_hl == 0:
            raise exc.DBRecordNotFound(kb_id)
        return deleted, deleted_hl

    def delete_project(self, project_id: str, raise_not_found: bool = False) -> tuple[int, int]:
        """
        Delete all project data.

        :param project_id: project ID
        :param raise_not_found: raise exception on 0 matches
        :return: deleted counts - main index, highlights index
        """

        query = {"term": {"metadata.project_id": project_id}}
        deleted = self.es.delete_by_query(index=f"{self.index_name}_*", query=query)["deleted"]
        deleted_hl = self.es.delete_by_query(index=f"{self.index_name_highlights}_*", query=query)["deleted"]

        if raise_not_found and deleted + deleted_hl == 0:
            raise exc.DBRecordNotFound(project_id)
        return deleted, deleted_hl

    def _score_l0(
            self,
            index_name: str,
            query: str | None,
            query_vector: list[float],
            base_filter: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        ftr = base_filter + [{"term": {"metadata.chunk_level": "L0"}}]
        source_includes = ["text", "metadata"]
        l0_size = 5

        l0_query = {
            "query": {
                "bool": {
                    "must": [{
                        "script_score": {
                            "query": {
                                "bool": {
                                    "should": [
                                        {"match": {"text": {"query": query, "boost": 1.0}}},
                                        {"match_phrase": {"text": {"query": query, "boost": 1.5}}},
                                    ],
                                    "filter": ftr,
                                },
                            },
                            "script": {
                                "source": "(_score * 0.4) + (cosineSimilarity(params.q, 'vector') * 0.6) + 1.0",
                                "params": {"q": query_vector},
                            },
                        },
                    }],
                },
            },
            "size": l0_size,
            "_source": source_includes,
        }

        try:
            l0_resp = self.es.search(index=index_name, body=l0_query)
        except Exception as e:
            logger.debug("L0 script_score query failed, retrying with text query; error: %s", e)

            l0_resp = self.es.search(
                index=index_name,
                query={"bool": {"must": [{"match": {"text": query}}], "filter": ftr}},
                size=l0_size,
                _source=source_includes,
            )

        return l0_resp.get("hits", {}).get("hits", [])

    def _score_l1_for_parent(
            self,
            parent_id: str,
            index_name: str,
            query_vector: list[float],
            base_filter: list[dict[str, Any]],
            k: int = 10,
            num_candidates: int = 200,
    ) -> list[dict[str, Any]]:
        ftr = base_filter + [
            {"term": {"metadata.chunk_level": "L1"}},
            {"term": {"metadata.parent_chunk_id": parent_id}},
        ]

        source_includes = [
            "metadata.char_start", "metadata.char_end", "metadata.chunk_index", "metadata.chunk_level",
            "metadata.page", "metadata.kb_id", "metadata.source_file", "text",
        ]

        try:
            resp = self.es.search(
                index=index_name,
                knn={
                    "field": "vector",
                    "query_vector": query_vector,
                    "k": max(k, 20),  # scan a bit more than we'll keep
                    "num_candidates": max(num_candidates, 200),
                    "filter": ftr,
                },
                size=max(k, 20),
                source_includes=source_includes,
            )

        except Exception as e:
            logger.debug("L1 KNN search failed, retrying with script_score query; error: %s", e)

            resp = self.es.search(
                index=index_name,
                body={
                    "query": {
                        "bool": {
                            "must": [{
                                "script_score": {
                                    "query": {"match_all": {}},
                                    "script": {
                                        "source": "cosineSimilarity(params.q, 'vector') + 1.0",
                                        "params": {"q": query_vector},
                                    },
                                },
                            }],
                            "filter": ftr,
                        },
                    },
                    "size": max(k, 20),
                    "_source": source_includes,
                },
            )

        out: list[dict[str, Any]] = []
        for h in resp.get("hits", {}).get("hits", []):
            src = h.get("_source", {})
            md = src.get("metadata", {})

            out.append({
                "kb_id": md.get("kb_id"),
                "source_file": md.get("source_file"),
                "page": md.get("page"),
                "start": md.get("char_start"),
                "end": md.get("char_end"),
                "text": src.get("text"),
                "score": h.get("_score"),
                "chunk_index": md.get("chunk_index"),
                "chunk_level": md.get("chunk_level"),
            })

        return out

    def fetch_highlight_spans(
            self,
            *,
            kb_id: str,
            project_id: str,
            source_file: str,
            page: int,
            emb_settings: EmbeddingModelSettings | None = None,
            query: str | None = None,
            k: int = 10,
            num_candidates: int = 200,
    ) -> list[dict[str, Any]]:
        """
        Return highlight spans for a page using hierarchical retrieval.

        Steps:
          1) pick best L0 on the page (BM25+phrase+vector),
          2) score its L1 children (vector), select top 50% (and above floor),
          3) return spans for the L0 + selected L1s (char offsets are relative to the page's text *without* header).

        If `query` is None, fall back to returning all L1 spans ordered by index (existing behavior).

        :param kb_id: knowledge base ID
        :param project_id: project ID
        :param source_file: source file name (path)
        :param page: page in the document
        :param emb_settings: embedding model settings
        :param query: user query
        :param k: top-k results (kept for L1 top-k; L0 uses a small fixed pool)
        :param num_candidates: number of candidates for approximate KNN (lower -> faster, higher -> more accurate)
        :return: highlight spans
        """

        index_name = self.get_index_name_highlights(model_name=emb_settings.name)
        embeddings = self._prepare_embedding_model(emb_settings=emb_settings)
        query_vector = embeddings.embed_query(query)

        base_filter = [
            {"term": {"metadata.kb_id": kb_id}},
            {"term": {"metadata.project_id": project_id}},
            {"term": {"metadata.source_file": source_file}},
            {"term": {"metadata.page": page}},
        ]

        # 1) L0 candidates on this page
        l0_hits = self._score_l0(
            index_name=index_name,
            query=query,
            query_vector=query_vector,
            base_filter=base_filter,
        )

        # 2) For each L0 candidate, score its L1 children. Let L1s "vote" for the parent L0.
        candidates = []

        for h in l0_hits:
            # ToDo: Parallelize the calls to ES.
            l1_all = self._score_l1_for_parent(
                parent_id=h["_id"],
                index_name=index_name,
                query_vector=query_vector,
                base_filter=base_filter,
                k=k,
                num_candidates=num_candidates,
            )

            l1_all.sort(key=lambda x: (x["score"] or 0.0), reverse=True)

            # Keep top 50% and apply a light floor
            if l1_all:
                half = max(1, len(l1_all) // 2)
                l1_top = l1_all[:half]
                l1_top = [x for x in l1_top if (x["score"] or 0.0) >= 0.05]
            else:
                l1_top = []

            l1_votes = len(l1_top)
            l1_avg = (sum((x["score"] or 0.0) for x in l1_top) / l1_votes) if l1_votes > 0 else 0.0
            l0_score = (h["_score"] - 1.0) if h.get("_score") is not None else 0.0
            combined = (0.5 * l0_score) + (0.3 * l1_avg) + (0.2 * min(l1_votes / 5.0, 1.0))

            candidates.append({
                "l0_id": h["_id"],
                "l0_text": h["_source"]["text"],
                "l0_md": h["_source"]["metadata"],
                "l0_score": l0_score,
                "l1_top": l1_top,
                "l1_votes": l1_votes,
                "l1_avg": l1_avg,
                "combined": combined,
            })

        if not candidates:
            return []

        candidates.sort(key=lambda c: c["combined"], reverse=True)
        best = candidates[0]

        # 3) Build spans: winning L0 (combined score) + its selected L1s (individual scores)
        l0_md = best["l0_md"]
        spans = [{
            "kb_id": l0_md.get("kb_id"),
            "source_file": l0_md.get("source_file"),
            "page": l0_md.get("page"),
            "start": l0_md.get("char_start"),
            "end": l0_md.get("char_end"),
            "text": best["l0_text"],
            "score": best["combined"],
            "chunk_index": l0_md.get("chunk_index"),
            "chunk_level": "L0",
        }] + best["l1_top"]

        return spans
