"""Fix references

Revision ID: c6be4fe10acc
Revises:
Create Date: 2019-09-20 11:01:59.648463+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c6be4fe10acc'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute("PRAGMA legacy_alter_table = TRUE")
    for name, sql in conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table'").fetchall():
        if sql is not None and '__old"' in sql:
            sql = sql.replace('__old"', '"')

            index_sqls = []
            for index_sql, in conn.execute("""
                SELECT sql
                FROM sqlite_master
                WHERE type = 'index' AND tbl_name = ?
            """, (name,)).fetchall():
                if index_sql is not None:
                    index_sqls.append(index_sql)

            params = {"table": f'"{name}"', "table_old": f'"{name}__old"'}
            conn.execute("ALTER TABLE %(table)s RENAME TO %(table_old)s" % params)
            conn.execute(sql)
            conn.execute("INSERT INTO %(table)s SELECT * FROM %(table_old)s" % params)
            conn.execute("DROP TABLE %(table_old)s" % params)
            for index_sql in index_sqls:
                conn.execute(index_sql)
    conn.execute("PRAGMA legacy_alter_table = FALSE")


def downgrade():
    pass
