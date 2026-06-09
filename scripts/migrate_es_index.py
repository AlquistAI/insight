# -*- coding: utf-8 -*-
"""
    scripts.migrate_es_index
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Migrate ElasticSearch index to another (already created) index.
"""

from time import sleep

from elasticsearch import Elasticsearch, helpers
from tqdm import tqdm

SOURCE_ES = "https://es.promethist.dev:443"
SOURCE_USER = "elastic"
SOURCE_PASSWORD = "..."
SOURCE_INDEX = "ragnarok-kb_openai-3-large"

TARGET_ES = "https://es.alquist.ai"
TARGET_USER = "elastic"
TARGET_PASSWORD = "..."
TARGET_INDEX = "ragnarok-kb_text-embedding-3-large"

# Batch sizes:
# - 1000-2000 for smaller documents (e.g. logs)
# - 100-200 for larger documents (e.g. vector DB)
BATCH_SIZE = 100
LOCK_TARGET_INDEX = True


def generate_actions():
    docs = helpers.scan(
        client=source_es,
        index=SOURCE_INDEX,
        query={"query": {"match_all": {}}},
        size=BATCH_SIZE,
        preserve_order=False,
    )

    for doc in docs:
        yield {
            "_op_type": "index",
            "_index": TARGET_INDEX,
            "_id": doc["_id"],
            "_source": doc["_source"],
        }


source_es = Elasticsearch(
    hosts=SOURCE_ES,
    basic_auth=(SOURCE_USER, SOURCE_PASSWORD),
    request_timeout=300,
)

target_es = Elasticsearch(
    hosts=TARGET_ES,
    basic_auth=(TARGET_USER, TARGET_PASSWORD),
    request_timeout=300,
)

if __name__ == "__main__":
    if LOCK_TARGET_INDEX:
        print("Locking target index...")
        target_settings_orig = target_es.indices.get_settings(index=TARGET_INDEX)[TARGET_INDEX]
        target_es.indices.put_settings(
            index=TARGET_INDEX,
            settings={"index": {"number_of_replicas": 0, "refresh_interval": "-1"}},
        )

        print("Original settings:", target_settings_orig)
        print("Locked settings:", target_es.indices.get_settings(index=TARGET_INDEX)[TARGET_INDEX])
    else:
        target_settings_orig = {}

    sleep(1)
    total_docs = source_es.count(index=SOURCE_INDEX)["count"]
    progress = tqdm(total=total_docs, desc="Migrating ES index")

    for ok, result in helpers.streaming_bulk(
            client=target_es,
            actions=generate_actions(),
            chunk_size=BATCH_SIZE,
            request_timeout=300,
            raise_on_error=False,
            raise_on_exception=False,
    ):
        if ok:
            progress.update(1)
        else:
            print("FAILED:", result)

    progress.close()
    sleep(1)

    if LOCK_TARGET_INDEX:
        print("Unlocking target index...")
        target_es.indices.put_settings(
            index=TARGET_INDEX,
            settings={
                "index": {
                    "number_of_replicas": target_settings_orig["settings"]["index"].get("number_of_replicas", 1),
                    "refresh_interval": target_settings_orig["settings"]["index"].get("refresh_interval", None),
                },
            },
        )

        print("Original settings:", target_settings_orig)
        print("Unlocked settings:", target_es.indices.get_settings(index=TARGET_INDEX)[TARGET_INDEX])
