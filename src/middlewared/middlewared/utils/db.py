import sqlite3

FREENAS_DATABASE = '/data/freenas-v1.db'


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def query_config_table(table, database_path=None, prefix=None):
    database_path = database_path or FREENAS_DATABASE
    conn = sqlite3.connect(database_path)
    conn.row_factory = dict_factory
    c = conn.cursor()
    c.execute(f"SELECT * FROM {table}")
    result = c.fetchone()
    if prefix:
        result = {k.replace(prefix, ''): v for k, v in result.items()}
    return result
