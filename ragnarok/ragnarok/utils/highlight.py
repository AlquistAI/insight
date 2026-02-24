# -*- coding: utf-8 -*-
"""
    ragnarok.utils.highlight
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Utilities for the text highlighting functionality.
"""

from typing import Any, Generator

# text-embedding-3-* allows up to ~300k tokens/request
MAX_TOKENS_PER_REQ = 240_000
MAX_ITEMS_PER_REQ = 512


def split_text_simple(text: str, chunk_size: int, overlap: int, separators: list[str]) -> list[str]:
    """
    Split text based on maximum chunk size.

    :param text: input text
    :param chunk_size: maximum chunk size
    :param overlap: desired overlap of chunks
    :param separators: list of separator chars/strings
    :return: list of text chunks
    """

    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    for sep in separators:
        if sep not in text or len(parts := text.split(sep)) < 2:
            continue

        out: list[str] = []
        cur = ""

        for i, part in enumerate(parts):
            full = part + (sep if i < len(parts) - 1 else "")

            if len(cur + full) <= chunk_size:
                cur += full
            else:
                if cur.strip():
                    out.append(cur.strip())

                if len(full) > chunk_size:
                    out.extend(split_text_simple(full, chunk_size, overlap, separators[1:]))
                    cur = ""
                else:
                    cur = full

        if cur.strip():
            out.append(cur.strip())
        return out

    chunks: list[str] = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + chunk_size, n)
        if chunk := text[start:end].strip():
            chunks.append(chunk)

        start = end - overlap if overlap > 0 else end
        if start >= n:
            break

    return chunks


def generate_chunk_batches(
        chunks: list[dict[str, Any]],
        max_tokens_per_req: int = MAX_TOKENS_PER_REQ,
        max_items_per_req: int = MAX_ITEMS_PER_REQ,
) -> Generator[list[dict[str, Any]], None, None]:
    """
    Generate chunk batches based on model request limits.

    :param chunks: input chunks
    :param max_tokens_per_req: maximum tokens per model request
    :param max_items_per_req: maximum items per model request
    :return: batched chunks
    """

    def _estimate_tokens(s: str) -> int:
        return max(1, int(len(s.strip()) / 4)) if s else 0

    batch: list[dict[str, Any]] = []
    token_sum = 0

    for c in chunks:
        tok = _estimate_tokens(c.get("text") or "")

        # Flush if adding this would exceed budgets
        if batch and (token_sum + tok > max_tokens_per_req or len(batch) >= max_items_per_req):
            yield batch
            batch = []
            token_sum = 0

        batch.append(c)
        token_sum += tok

    if batch:
        yield batch


def make_chunk_id(source_document_id: str, level: str, start: int, end: int) -> str:
    return f"{source_document_id}_{level}_{start}_{end}"


def preprocess_text_for_chunking(text: str) -> str:
    lines = (text or "").split("\n")
    filtered = [ln for ln in lines if not ln.strip().startswith("SOURCE FILE:")]
    result = "\n".join(filtered)

    while result.startswith("\n\n\n"):
        result = result[1:]
    return result.strip()


def create_chunks_from_text(
        text: str,
        chunk_size: int,
        overlap: int,
        separators: list[str],
) -> list[dict[str, Any]]:
    if not (text := text or "").strip():
        return []

    chunks: list[dict[str, Any]] = []
    texts = split_text_simple(text=text, chunk_size=chunk_size, overlap=overlap, separators=separators)
    current_pos = 0

    for i, t in enumerate(texts):
        if not (tc := t.strip()):
            continue

        if (start_pos := text.find(tc, current_pos)) == -1:
            start_pos = current_pos
            end_pos = min(current_pos + len(tc), len(text))
        else:
            end_pos = start_pos + len(tc)

        current_pos = max(0, end_pos - overlap)
        chunks.append({"text": tc, "chunk_index": i, "char_start": start_pos, "char_end": end_pos})

    return chunks


def create_hierarchical_chunks(
        documents: list[dict[str, Any]],
        l0_size: int,
        l0_overlap: int,
        l1_size: int,
        l1_overlap: int,
        separators: list[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    for doc in documents:
        text = preprocess_text_for_chunking(doc["text"])
        if not (l0s := create_chunks_from_text(text, l0_size, l0_overlap, separators)):
            continue

        for l0_idx, l0 in enumerate(l0s):
            l0_id = make_chunk_id(doc["id"], "L0", l0["char_start"], l0["char_end"])

            out.append({
                "text": l0["text"],
                "metadata": {
                    **doc["metadata"],
                    "source_document_id": doc["id"],
                    "chunk_level": "L0",
                    "chunk_index": l0_idx,
                    "char_start": l0["char_start"],
                    "char_end": l0["char_end"],
                    "chunk_id": l0_id,
                },
            })

            # Split into L1 and convert to absolute offsets
            l1s = create_chunks_from_text(
                l0["text"], l1_size, l1_overlap, separators,
            ) or [{
                "text": l0["text"],
                "char_start": 0,
                "char_end": len(l0["text"]),
            }]

            for l1_idx, l1 in enumerate(l1s):
                abs_start = l0["char_start"] + l1["char_start"]
                abs_end = l0["char_start"] + l1["char_end"]
                l1_id = make_chunk_id(doc["id"], "L1", abs_start, abs_end)

                out.append({
                    "text": l1["text"],
                    "metadata": {
                        **doc["metadata"],
                        "source_document_id": doc["id"],
                        "parent_chunk_id": l0_id,
                        "chunk_level": "L1",
                        "chunk_index": l1_idx,
                        "char_start": abs_start,
                        "char_end": abs_end,
                        "chunk_id": l1_id,
                    },
                })

    return out
