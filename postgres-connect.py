import json
import os
import sys

import psycopg2
from psycopg2.extras import RealDictCursor
from loguru import logger
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Postgres_Connect")
logger.remove()
logger.add(sys.stdout, level="INFO")

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


@mcp.tool()
def query_data_read(sql_query: str) -> str:
    if not _is_read_only(sql_query):
        return json.dumps(
            {"error": "Only single-statement read-only SELECT/CTE queries are allowed."},
            indent=2,
        )
    logger.info("Executing SQL query: {}", sql_query)

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

        cursor.execute(sql_query)

        rows = cursor.fetchall()
        return json.dumps(rows, indent=2, default=str)
    except psycopg2.OperationalError as exc:
        logger.error("Database connection failed: {}", exc)
        return json.dumps({"error": "Database connection failed", "detail": str(exc)}, indent=2)
    except Exception as exc:
        logger.exception("Query failed")
        return json.dumps({"error": str(exc)}, indent=2)
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    print("starting server...")
    mcp.run(transport="stdio")
