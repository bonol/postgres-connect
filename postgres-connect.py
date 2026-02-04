import json
import os
import sys

import psycopg2
from psycopg2.extras import RealDictCursor
from loguru import logger
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Postgres_Connect")
logger.remove()
logger.add(sys.stderr, level="INFO")

_READ_ONLY_START = ("select", "with")
_BLOCKED_KEYWORDS = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "truncate",
    "grant",
    "revoke",
    "copy",
    "call",
    "do",
)


def _is_read_only(sql_query: str) -> bool:
    query = sql_query.strip().lower()
    if not query.startswith(_READ_ONLY_START):
        return False
    if ";" in query:
        return False
    return not any(f" {kw} " in f" {query} " for kw in _BLOCKED_KEYWORDS)


def _fetch_rows(sql_query: str, params: tuple | None = None) -> tuple[list[dict] | None, dict | None]:
    db_name = os.getenv("PGDATABASE", "awe_development")
    db_user = os.getenv("PGUSER", "postgres")
    db_pass = os.getenv("PGPASSWORD", "password")
    db_host = os.getenv("PGHOST", "localhost")
    db_port = os.getenv("PGPORT", "5432")

    conn = None
    cursor = None

    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_pass,
            host=db_host,
            port=db_port,
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(sql_query, params)
        rows = cursor.fetchall()
        return rows, None
    except psycopg2.OperationalError as exc:
        logger.error("Database connection failed: {}", exc)
        return None, {"error": "Database connection failed", "detail": str(exc)}
    except Exception as exc:
        logger.exception("Query failed")
        return None, {"error": str(exc)}
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@mcp.tool()
def query_data_read(sql_query: str) -> str:
    if not _is_read_only(sql_query):
        return json.dumps(
            {"error": "Only single-statement read-only SELECT/CTE queries are allowed."},
            indent=2,
        )
    logger.info("Executing SQL query: {}", sql_query)

    rows, error = _fetch_rows(sql_query)
    if error is not None:
        return json.dumps(error, indent=2)
    return json.dumps(rows, indent=2, default=str)


@mcp.tool()
def get_table_schema(table_name: str, schema_name: str | None = None) -> str:
    logger.info("Fetching table schema for {}.{}", schema_name, table_name)
    columns_sql = """
        SELECT
            ordinal_position,
            column_name,
            data_type,
            udt_name,
            is_nullable,
            column_default,
            character_maximum_length,
            numeric_precision,
            numeric_scale
        FROM information_schema.columns
        WHERE table_name = %s
          AND table_schema = COALESCE(%s, current_schema())
        ORDER BY ordinal_position
    """
    columns, error = _fetch_rows(columns_sql, (table_name, schema_name))
    if error is not None:
        return json.dumps(error, indent=2)

    constraints_sql = """
        SELECT
            tc.constraint_type,
            tc.constraint_name,
            kcu.column_name,
            ccu.table_schema AS foreign_table_schema,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints tc
        LEFT JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        LEFT JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.table_name = %s
          AND tc.table_schema = COALESCE(%s, current_schema())
          AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE')
        ORDER BY tc.constraint_type, kcu.ordinal_position
    """
    constraints, error = _fetch_rows(constraints_sql, (table_name, schema_name))
    if error is not None:
        return json.dumps(error, indent=2)

    payload = {
        "table_name": table_name,
        "schema_name": schema_name,
        "columns": columns,
        "constraints": constraints,
    }
    return json.dumps(payload, indent=2, default=str)


@mcp.tool()
def get_table_indexes(table_name: str, schema_name: str | None = None) -> str:
    logger.info("Fetching indexes for {}.{}", schema_name, table_name)
    sql_query = """
        SELECT
            schemaname,
            tablename,
            indexname,
            indexdef
        FROM pg_indexes
        WHERE tablename = %s
          AND schemaname = COALESCE(%s, current_schema())
        ORDER BY indexname
    """
    rows, error = _fetch_rows(sql_query, (table_name, schema_name))
    if error is not None:
        return json.dumps(error, indent=2)
    return json.dumps(rows, indent=2, default=str)


@mcp.tool()
def get_table_functions(table_name: str, schema_name: str | None = None) -> str:
    logger.info("Fetching trigger functions for {}.{}", schema_name, table_name)
    sql_query = """
        SELECT
            n.nspname AS function_schema,
            p.proname AS function_name,
            pg_get_function_identity_arguments(p.oid) AS function_arguments,
            pg_get_function_result(p.oid) AS function_return_type,
            t.tgname AS trigger_name,
            pg_get_triggerdef(t.oid) AS trigger_definition
        FROM pg_trigger t
        JOIN pg_proc p ON p.oid = t.tgfoid
        JOIN pg_namespace n ON n.oid = p.pronamespace
        JOIN pg_class c ON c.oid = t.tgrelid
        JOIN pg_namespace tn ON tn.oid = c.relnamespace
        WHERE NOT t.tgisinternal
          AND c.relname = %s
          AND tn.nspname = COALESCE(%s, current_schema())
        ORDER BY t.tgname, p.proname
    """
    rows, error = _fetch_rows(sql_query, (table_name, schema_name))
    if error is not None:
        return json.dumps(error, indent=2)
    return json.dumps(rows, indent=2, default=str)


if __name__ == "__main__":
    logger.info("Starting server...")
    mcp.run(transport="stdio")
