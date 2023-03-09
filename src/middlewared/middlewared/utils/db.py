import sqlite3

FREENAS_DATABASE = '/data/freenas-v1.db'


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def query_config_table(table, database_path=None, prefix=None):
    return query_table(table, database_path, prefix)[0]


def query_table(table, database_path=None, prefix=None):
    database_path = database_path or FREENAS_DATABASE
    conn = sqlite3.connect(database_path)
    result = []
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
