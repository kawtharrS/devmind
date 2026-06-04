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

import hashlib
import json
import os

import chromadb
import numpy as np

_COLLECTION_NAME = "codebase"
_EMBED_DIM = 1024


class _OfflineEmbeddingFunction:
    """Bag-of-words hash embedding — works offline, no model download needed.

    Uses the hashing trick: each whitespace-delimited token is hashed into a
    fixed-length float vector, then L2-normalised so cosine distance is valid.
    Consistent across runs because SHA-256 is deterministic.

    Tradeoff vs semantic embeddings: synonym/paraphrase matching is weaker,
    but for codebases with consistent terminology (function names, domain words)
    the retrieval quality is sufficient.
    """

    def name(self) -> str:
        return "devmind-offline-hash"

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self(input)

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        return self(input)

    def __call__(self, input: list[str]) -> list[list[float]]:
        result: list[list[float]] = []
        for text in input:
            vec = np.zeros(_EMBED_DIM, dtype=np.float32)
            for token in text.lower().split():
                digest = hashlib.sha256(token.encode()).digest()
                # Use first 8 bytes as a uint64 to index into the vector.
                idx = int.from_bytes(digest[:8], "little") % _EMBED_DIM
                # Use next 4 bytes for the weight so common words don't all add 1.
                weight = 1.0 + (int.from_bytes(digest[8:12], "little") % 8) / 8.0
                vec[idx] += weight
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            result.append(vec.tolist())
        return result


_EF = _OfflineEmbeddingFunction()


def _open_collection(store_path: str) -> chromadb.Collection:
    client = chromadb.PersistentClient(path=store_path)
    return client.get_or_create_collection(
        name=_COLLECTION_NAME,
        embedding_function=_EF,
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
    metadatas_list = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    for meta, distance in zip(metadatas_list, distances):
        hits.append({
            "relative_path": meta.get("relative_path", ""),
            "purpose": meta.get("purpose", ""),
            "domain": meta.get("domain", "unknown"),
            "similarity_score": round(1 - distance, 4),
        })

    return hits
