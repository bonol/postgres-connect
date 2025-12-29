# Postgres MCP Server (Read-Only)

This repo provides a simple MCP server that executes read-only SQL queries against a
Postgres database and returns JSON results. Write queries are blocked.

## Requirements

- Python 3.10+ (or your local version)
- Dependencies: `mcp`, `psycopg2`, `loguru`

## Setup

Create and activate a venv, then install dependencies with `uv`:

```bash
uv venv
source .venv/bin/activate
uv pip install mcp psycopg2 loguru
```

## Configuration

The server reads standard Postgres environment variables:

- `PGHOST`
- `PGDATABASE`
- `PGUSER`
- `PGPASSWORD`
- `PGPORT`

If unset, it falls back to defaults defined in `postgres-connect.py`.

## Run

```bash
source .venv/bin/activate
python postgres-connect.py
```

## Limitations

- Only single-statement `SELECT` or `WITH` queries are allowed.
- Queries with semicolons are rejected.
- Write operations are blocked.

## Notes

This is intentionally minimal. Additional tools and capabilities will be added later.
