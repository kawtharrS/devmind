<<<<<<< HEAD
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
=======
HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-6"

DEVMIND_DIR = ".devmind"
CHROMA_DIR = "chroma"

MAX_CHUNK_TOKENS = 3000
MAX_LINE_COUNT = 500
SUMMARIZE_MAX_TOKENS = 512
CHAT_MAX_TOKENS = 1024
TOUR_MAX_TOKENS = 2048
CHAT_CONTEXT_CHUNKS = 5

INPUT_COST_PER_M = 0.80
OUTPUT_COST_PER_M = 4.00
AVG_SUMMARY_OUTPUT_TOKENS = 150

IGNORED_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv",
    "dist", "build", "vendor", ".next",
}
IGNORED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".svg", ".ico",
    ".lock", ".zip", ".env",
}
>>>>>>> ks-str
