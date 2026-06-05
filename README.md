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
# Index a repository (runs index + vector store + graph in one step)
devmind setup --repo /path/to/repo

# Ask questions interactively
devmind chat

# Session commands inside chat:
#   /graph <file>  — show ASCII dependency tree for a file
#   /tour          — generate onboarding guide inline
#   /exit          — quit

# Generate a Day 1/2/3 onboarding guide
devmind tour

# Show index stats (domain breakdown, hub files, cost)
devmind stats

# Show dependency graph for the most-imported files
devmind graph
```

## Architecture

```
cli.py          CLI entry point (Click) — all user-facing output via Rich
indexer.py      Repo walking + Claude Haiku file summarization
graph.py        Import/dependency graph extraction (fuzzy matching)
store.py        ChromaDB vector storage (offline hash embeddings)
chat.py         RAG pipeline + streaming Claude answer
prompts.py      All system prompts and user prompt templates
utils.py        Token counting, file filtering, chunking
config.py       Model names, paths, token budgets, filter lists
mcp_server.py   MCP stdio server (Claude Desktop / Claude Code integration)
```

## MCP Server

devmind exposes an MCP server so Claude Desktop and Claude Code can query your indexed codebase directly as tools.

### Prerequisites

Run `devmind setup` on your repo first. Optionally pre-generate the tour:

```bash
devmind setup --repo /path/to/repo
devmind tour > .devmind/tour.md
```

### Tools exposed

| Tool | Description |
|---|---|
| `search_codebase` | Semantic search over indexed files |
| `get_file_summary` | Full summary for a single file (accepts partial paths) |
| `get_dependency_graph` | What a file imports and what imports it |
| `get_onboarding_tour` | Returns `.devmind/tour.md` if it exists |

### Register with Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "devmind": {
      "command": "devmind-mcp",
      "env": {
        "ANTHROPIC_API_KEY": "sk-...",
        "DEVMIND_PATH": "/absolute/path/to/repo/.devmind"
      }
    }
  }
}
```

Restart Claude Desktop. The four devmind tools will appear in the tools panel.

### Register with Claude Code

Create `.mcp.json` at the project root (already included in this repo):

```json
{
  "mcpServers": {
    "devmind": {
      "command": "py",
      "args": ["-3.11", "-m", "devmind.mcp_server"],
      "env": {
        "DEVMIND_PATH": "C:\\path\\to\\repo\\.devmind"
      }
    }
  }
}
```

Claude Code picks up `.mcp.json` automatically. You'll be prompted to approve the server on first use.
