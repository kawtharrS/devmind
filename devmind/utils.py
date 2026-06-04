"""
Shared utility helpers.

Responsibilities:
  - Token counting: wrap tiktoken to count tokens for a given string and model,
    and to split a long string into chunks that fit within a max-token budget.
  - File filtering: given a file path, decide whether it should be indexed
    (allowlist of extensions: .py, .js, .ts, .md, .yaml, .toml, .json, etc.)
    and whether it should be skipped (blocklist of dirs: .git, __pycache__,
    node_modules, .venv, dist, build).
  - Language detection: infer the programming language from a file extension,
    returning a short string ("python", "typescript", "markdown", …) used as
    ChromaDB metadata.
  - Path normalization: convert absolute paths to repo-relative paths for
    stable chunk IDs across machines.
"""

import os
import tiktoken

IGNORED_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv",
    "dist", "build", "vendor", ".next",
}

IGNORED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".svg", ".ico",
    ".lock", ".zip", ".env",
}

MAX_LINE_COUNT = 500

_ENCODING = tiktoken.get_encoding("cl100k_base")


def get_repo_files(repo_path: str) -> list[dict]:
    """Walk repo_path recursively and return metadata for each indexable file.

    Returns a list of dicts with keys:
      path          — absolute path to the file
      relative_path — path relative to repo_path
      extension     — lowercase file extension including the dot (e.g. ".py")
      line_count    — number of lines in the file
    """
    results = []
    repo_path = os.path.abspath(repo_path)

    for dirpath, dirnames, filenames in os.walk(repo_path):
        # Prune ignored directories in-place so os.walk won't descend into them.
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]

        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()
            if ext in IGNORED_EXTENSIONS:
                continue

            abs_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(abs_path, repo_path)

            try:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except OSError:
                continue

            line_count = len(lines)
            if line_count > MAX_LINE_COUNT:
                continue

            results.append({
                "path": abs_path,
                "relative_path": rel_path,
                "extension": ext,
                "line_count": line_count,
            })

    return results


def chunk_file(content: str, max_tokens: int = 3000) -> list[str]:
    """Split content into overlapping token-bounded chunks.

    Uses cl100k_base encoding (compatible with Claude and GPT-4).
    Overlap is 10% of max_tokens so context is preserved across chunk boundaries.
    Returns a list of decoded string chunks.
    """
    tokens = _ENCODING.encode(content)

    if len(tokens) <= max_tokens:
        return [content]

    overlap = max_tokens // 10
    step = max_tokens - overlap
    chunks = []

    for start in range(0, len(tokens), step):
        chunk_tokens = tokens[start : start + max_tokens]
        chunks.append(_ENCODING.decode(chunk_tokens))
        if start + max_tokens >= len(tokens):
            break

    return chunks
