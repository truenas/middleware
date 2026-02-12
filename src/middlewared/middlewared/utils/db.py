import sqlite3
from typing import Any

FREENAS_DATABASE = '/data/freenas-v1.db'
FREENAS_DATABASE_MODE = 0o600


def dict_factory(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict[str, Any]:
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def query_config_table(table: str, database_path: str | None = None, prefix: str | None = None) -> dict[str, Any]:
    return query_table(table, database_path, prefix)[0]


def query_table(table: str, database_path: str | None = None, prefix: str | None = None) -> list[dict[str, Any]]:
    database_path = database_path or FREENAS_DATABASE
    conn = sqlite3.connect(database_path)
    result: list[dict[str, Any]] = []
    try:
        conn.row_factory = dict_factory
        c = conn.cursor()
        try:
            for row in c.execute(f"SELECT * FROM {table}").fetchall():
                row = dict(row)
                if prefix:
                    row = {k.removeprefix(prefix): v for k, v in row.items()}
                result.append(row)
        finally:
            c.close()
    finally:
        conn.close()
    return result


def update_table(query: str, params: tuple[Any, ...], database_path: str | None = None) -> None:
    database_path = database_path or FREENAS_DATABASE
    conn = sqlite3.connect(database_path)
    try:
        c = conn.cursor()
        try:
            c.execute(query, params)
        finally:
            c.close()
        conn.commit()
    finally:
        conn.close()
