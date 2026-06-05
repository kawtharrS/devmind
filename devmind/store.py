import hashlib
import json
import os

import chromadb
import numpy as np

_COLLECTION_NAME = "codebase"
_EMBED_DIM = 1024


class _OfflineEmbeddingFunction:
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
    key_fns = summary.get("key_functions") or []
    if isinstance(key_fns, list):
        key_fns = ", ".join(key_fns)
    return (
        f"{summary.get('purpose', '')}. "
        f"Key functions: {key_fns}. "
        f"Domain: {summary.get('domain', 'unknown')}."
    )


def build_store(index_json_path: str, store_path: str) -> int:
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

    if ids:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    return len(ids)


def search(query: str, store_path: str, n_results: int = 5) -> list[dict]:
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
