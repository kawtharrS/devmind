# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`devmind` is an AI-powered developer onboarding CLI. It indexes a git repository into ChromaDB and answers natural-language questions about it using RAG + Claude.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the CLI directly during development
python -m devmind.cli <subcommand>

# Index a repo
python -m devmind.cli index /path/to/repo

# Ask a question
python -m devmind.cli chat "How does X work?"

# Show dependency graph
python -m devmind.cli graph /path/to/repo
```

## Architecture

The data flow is linear:

1. **`cli.py`** parses commands and delegates to the appropriate module.
2. **`indexer.py`** walks the repo (via GitPython), filters files (`utils.py`), chunks them by token count (`utils.py` + tiktoken), calls Claude to summarize each chunk, and hands results to `store.py`.
3. **`graph.py`** independently parses Python ASTs to build an import dependency graph, which is serialized to JSON and stored alongside the index.
4. **`store.py`** owns all ChromaDB interactions — two collections: `chunks` (raw text) and `summaries` (Claude summaries). Chunk IDs are `<repo-relative-path>::<chunk-index>` for idempotent re-indexing.
5. **`chat.py`** handles queries: retrieves top-N chunks from `store.py`, optionally enriches with graph context from `graph.py`, assembles a prompt, and streams a Claude response.
6. **`config.py`** is the single source of truth for model IDs, token budgets, ChromaDB path, and file filter lists. All other modules import constants from here — never hardcode them elsewhere.
7. **`utils.py`** provides shared helpers (token counting, file extension filtering, language detection, path normalization) used by both `indexer.py` and `store.py`.

## Key conventions

- The Anthropic SDK is used directly (not LangChain). Streaming responses are preferred for chat.
- ChromaDB runs in persistent local mode; the DB path comes from `config.CHROMA_PERSIST_DIR`.
- All user-facing output goes through Rich — no bare `print()` calls in the CLI layer.
- File chunk IDs must be deterministic (`path::index`) so re-indexing the same repo is idempotent.
- `ANTHROPIC_API_KEY` must be set in the environment; the SDK picks it up automatically.
