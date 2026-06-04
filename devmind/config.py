"""
Central configuration: model names, paths, and tuneable constants.

Defines:
  ANTHROPIC_MODEL      — Claude model ID used for summarization and chat answers.
  EMBED_MODEL          — Embedding model identifier passed to ChromaDB.
  CHROMA_PERSIST_DIR   — Local directory where ChromaDB stores its data.
  MAX_CHUNK_TOKENS     — Maximum tokens per indexed chunk (used by utils.py).
  SUMMARY_MAX_TOKENS   — Max tokens Claude may use when writing a file summary.
  CHAT_MAX_TOKENS      — Max tokens for the chat answer response.
  CHAT_CONTEXT_CHUNKS  — Number of chunks retrieved from ChromaDB per query.
  INDEXABLE_EXTENSIONS — Set of file extensions that should be indexed.
  IGNORED_DIRS         — Directory names that are always skipped during walking.
"""
