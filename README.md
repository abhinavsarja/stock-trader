# stock-trader

A LangChain + LangGraph powered stock trading agent, managed with [`uv`](https://docs.astral.sh/uv/).

## Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)

## Setup

1. Copy the example env file and fill in your secrets:

   ```bash
   cp .env.example .env
   ```

2. Sync dependencies (creates a `.venv` and installs everything from `pyproject.toml`):

   ```bash
   uv sync
   ```

## Run

Run the entry point as a module:

```bash
uv run python -m main.main
```

Or via the installed script:

```bash
uv run stock-trader
```

## Project layout

```
.
├── main/
│   ├── __init__.py
│   └── main.py        # contains the `main()` entry point
├── .env.example
├── .env               # git-ignored
├── pyproject.toml
└── README.md
```

## Dependencies

Core:

- `langchain`, `langchain-core`, `langchain-community`, `langchain-openai`
- `langgraph`
- `python-dotenv`
- `pydantic`

Dev:

- `ruff`, `pytest`
