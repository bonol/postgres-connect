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

## Test (STDIO smoke test)

This runs the server as a child process, performs the MCP initialize handshake,
lists tools, and calls `query_data_read` with `select 1 as ok`.

```bash
source .venv/bin/activate
python scripts/stdio_smoketest.py
```

If initialization fails due to protocol version mismatch, the script retries with
the server's supported protocol version and prints it.

## Tools

The MCP server exposes these tools:

- `query_data_read(sql_query: str)`
- `get_table_schema(table_name: str, schema_name: str | None = None)`
- `get_table_indexes(table_name: str, schema_name: str | None = None)`
- `get_table_functions(table_name: str, schema_name: str | None = None)`

### Examples

Fetch table columns and constraints:

```json
{"tool": "get_table_schema", "args": {"table_name": "users", "schema_name": "public"}}
```

Fetch index definitions:

```json
{"tool": "get_table_indexes", "args": {"table_name": "users", "schema_name": "public"}}
```

Fetch trigger-linked functions:

```json
{"tool": "get_table_functions", "args": {"table_name": "users", "schema_name": "public"}}
```

## Limitations

- Only single-statement `SELECT` or `WITH` queries are allowed.
- Queries with semicolons are rejected.
- Write operations are blocked.

## Notes

This is intentionally minimal. Additional tools and capabilities will be added later.
