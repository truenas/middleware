"""Fix references

Revision ID: c6be4fe10acc
Revises:
Create Date: 2019-09-20 11:01:59.648463+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'c6be4fe10acc'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(text("PRAGMA legacy_alter_table = TRUE"))
    for name, sql in conn.execute(text("SELECT name, sql FROM sqlite_master WHERE type = 'table'")).fetchall():
        if sql is not None and '__old"' in sql:
            sql = sql.replace('__old"', '"')

            index_sqls = []
            for index_sql, in conn.execute(text("""
                SELECT sql
                FROM sqlite_master
                WHERE type = 'index' AND tbl_name = :tbl_name
            """), {"tbl_name": name}).fetchall():
                if index_sql is not None:
                    index_sqls.append(index_sql)

            params = {"table": f'"{name}"', "table_old": f'"{name}__old"'}
            conn.execute(text(f"ALTER TABLE {params['table']} RENAME TO {params['table_old']}"))
            conn.execute(text(sql))
            conn.execute(text(f"INSERT INTO {params['table']} SELECT * FROM {params['table_old']}"))
            conn.execute(text(f"DROP TABLE {params['table_old']}"))
            for index_sql in index_sqls:
                conn.execute(text(index_sql))
    conn.execute(text("PRAGMA legacy_alter_table = FALSE"))


def downgrade():
    pass
