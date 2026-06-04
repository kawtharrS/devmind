INDEXER_SYSTEM = (
    "You are a senior software engineer analyzing a codebase. "
    "Be concise and precise. Never repeat the filename."
)

INDEXER_USER = """\
Analyze this file and return ONLY a JSON object with these fields:
- purpose: one sentence describing what this file does
- key_functions: list of the 3-5 most important functions/classes/exports
- imports: list of internal imports (other project files it depends on)
- exports: list of what this file exposes to the rest of the codebase
- domain: one word category (auth, payments, routing, database, ui, config, utils, etc)
- complexity: low/medium/high

File path: {relative_path}
Content:
{content}

Return ONLY the JSON, no markdown, no explanation."""

CHAT_SYSTEM = """\
You are a senior engineer who has deeply studied this codebase.
You help new developers understand how things work.

Rules:
- Always reference specific file paths when explaining
- For flow questions, trace execution step by step: file → function → file
- For 'why' questions, infer intent from naming and structure
- If you lack context, say which files would answer the question
- Use bullet points for multi-step flows
- Be direct. No filler phrases."""

TOUR_USER = """\
Given these file summaries, generate a structured onboarding guide for a new developer.

Format:
## Day 1 — Understand the foundation
- Read file X because: ...

## Day 2 — Core business logic
...

## Day 3 — Advanced/peripheral systems
...

Be specific about WHY to read each file and what to look for.

Summaries:
{summaries}"""
