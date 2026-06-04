"""
ChromaDB vector storage module.

Responsibilities:
  - Initialize and manage a persistent ChromaDB client pointed at the path
    defined in config.py (CHROMA_PERSIST_DIR).
  - Maintain two collections:
      * "chunks"    — raw file chunks with metadata (path, line range, language).
      * "summaries" — Claude-generated summaries of each chunk.
  - Provide `upsert(chunks)` to add or refresh documents (keyed by file path +
    chunk index so re-indexing is idempotent).
  - Provide `query(text, n_results)` that embeds the query and returns the top-N
    most relevant chunks and their metadata.
  - Provide `delete_by_prefix(path_prefix)` to remove all chunks for a file or
    directory when it is deleted or moved.
"""

import json
import os

import chromadb

_COLLECTION_NAME = "codebase"


def _open_collection(store_path: str) -> chromadb.Collection:
    client = chromadb.PersistentClient(path=store_path)
    return client.get_or_create_collection(
        name=_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _doc_string(summary: dict) -> str:
    """Compose the text that gets embedded for a file summary."""
    key_fns = summary.get("key_functions") or []
    if isinstance(key_fns, list):
        key_fns = ", ".join(key_fns)
    return (
        f"{summary.get('purpose', '')}. "
        f"Key functions: {key_fns}. "
        f"Domain: {summary.get('domain', 'unknown')}."
    )


def build_store(index_json_path: str, store_path: str) -> None:
    """Load index.json and upsert every file summary into ChromaDB.

    Documents are keyed by relative_path so re-running is idempotent.
    Metadata stored per document: path, relative_path, domain, complexity.
    """
    with open(index_json_path, "r", encoding="utf-8") as f:
        summaries: list[dict] = json.load(f)

    os.makedirs(store_path, exist_ok=True)
    collection = _open_collection(store_path)

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for summary in summaries:
        rel = summary.get("relative_path")
        if not rel:
            continue

        ids.append(rel)
        documents.append(_doc_string(summary))
        metadatas.append({
            "path": summary.get("path", ""),
            "relative_path": rel,
            "domain": summary.get("domain", "unknown"),
            "complexity": summary.get("complexity", "unknown"),
            "purpose": summary.get("purpose", ""),
        })

    if not ids:
        print("No summaries to store.")
        return

    # Upsert in one batch; ChromaDB handles adds and updates transparently.
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    print(f"Stored {len(ids)} files in vector DB")


def search(query: str, store_path: str, n_results: int = 5) -> list[dict]:
    """Semantic search over the codebase collection.

    Returns up to n_results dicts, each with:
      relative_path, purpose, domain, similarity_score

    similarity_score is 1 - cosine_distance, so 1.0 is a perfect match.
    """
    collection = _open_collection(store_path)

    result = collection.query(
        query_texts=[query],
        n_results=min(n_results, collection.count()),
        include=["metadatas", "distances"],
    )

    hits = []
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    for meta, distance in zip(metadatas, distances):
        hits.append({
            "relative_path": meta.get("relative_path", ""),
            "purpose": meta.get("purpose", ""),
            "domain": meta.get("domain", "unknown"),
            "similarity_score": round(1 - distance, 4),
        })

    return hits
