# devmind

AI-powered developer onboarding assistant. Point it at any git repository and ask questions about the codebase in plain English.

## What it does

- **Indexes** a repository by walking source files, chunking them, and storing embeddings in a local ChromaDB database.
- **Understands structure** by extracting Python import graphs to surface dependencies between files.
- **Answers questions** using retrieval-augmented generation: relevant code chunks are fetched from the vector store and passed to Claude along with your question.

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...
```

## Usage

```bash
# Index a repository
devmind index /path/to/repo

# Ask a question
devmind chat "How does authentication work?"

# Show the dependency graph
devmind graph /path/to/repo
```

## Architecture

```
cli.py        CLI entry point (Click)
indexer.py    Repo walking + Claude-powered file summarization
graph.py      Import/dependency graph extraction (ast)
store.py      ChromaDB vector storage (upsert, query, delete)
chat.py       RAG pipeline + streaming Claude answer
utils.py      Token counting, file filtering, language detection
config.py     Model names, paths, tuneable constants
```
