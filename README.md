# MCP Server Chat Demo

A minimal Python project that connects an LLM (`ChatGroq`) to MCP tools via `mcp-use`, then runs an interactive terminal chat with conversation memory.

## Features

- Interactive chat loop in terminal.
- Memory-enabled agent (`memory_enabled=True`).
- Built-in commands:
  - `exit` to quit.
  - `clear` to clear conversation history.
- MCP servers loaded from `brower_mcp.json`:
  - Playwright MCP
  - DuckDuckGo Search MCP

## Project Structure

- `app.py` - main async chat application.
- `brower_mcp.json` - MCP server configuration.
- `pyproject.toml` - project metadata and dependencies.
- `requirements.txt` - minimal dependency list.
- `main.py` - simple placeholder entry script.

## Prerequisites

- Python `3.11+`
- Node.js and npm (required because MCP servers are started with `npx`)
- A Groq API key

## Setup

1. Clone the repository and enter the directory.
2. Create a virtual environment.
3. Install dependencies.
4. Create a `.env` file with your API key.

Example:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Add your environment variable in `.env`:

```env
GROQ_API_KEY=your_groq_api_key_here
```

## Run

Start the interactive memory chat:

```bash
python app.py
```

When prompted:

- Type your message and press Enter.
- Type `clear` to reset memory.
- Type `exit` to stop.

## MCP Configuration

The app reads MCP servers from `brower_mcp.json`.

Current config uses:

- `@playwright/mcp@latest`
- `duckduckgo-mcp-server`

If you add more MCP servers, update `brower_mcp.json` accordingly.

## Notes

- `app.py` is the actual runtime entrypoint for this project.
- `main.py` currently prints a placeholder message and is not used for the chat workflow.
