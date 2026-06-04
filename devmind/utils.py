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
    results = []
    repo_path = os.path.abspath(repo_path)

    for dirpath, dirnames, filenames in os.walk(repo_path):
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
