"""Make all primary keys autoincrement

Revision ID: 2fb0f87b2f17
Revises: c68c71c34771
Create Date: 2021-01-20 10:19:30.500426+00:00

"""
import re

from alembic import op


# revision identifiers, used by Alembic.
revision = '2fb0f87b2f17'
down_revision = 'c68c71c34771'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute("PRAGMA legacy_alter_table = TRUE")
    for name, sql in conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table'").fetchall():
        if m := re.match(r'CREATE TABLE "(.+)" \(\s*"?id"? integer (NOT NULL |)PRIMARY KEY,', sql, flags=re.IGNORECASE):
            table_name = m.group(1)
            new_sql = m.group(0).replace('PRIMARY KEY', 'PRIMARY KEY AUTOINCREMENT') + sql[len(m.group(0)):]
        elif m := re.match(r'(CREATE TABLE "?(.+) \((\s*)"?id"? integer( NOT NULL|),)(.+)'
                           r'\n\s(CONSTRAINT ([a-z_]+) |)PRIMARY KEY \(id\),?',
                           sql, flags=re.IGNORECASE | re.DOTALL):
            table_name = m.group(2).rstrip('"')
            new_sql = f'CREATE TABLE {table_name} ({m.group(3)}id integer{m.group(4)} PRIMARY KEY AUTOINCREMENT,' + \
                      m.group(5) + sql[len(m.group(0)):]
            new_sql = new_sql.rstrip().rstrip(')').rstrip().rstrip(',') + '\n)'
        elif re.match(r'CREATE TABLE "(.+)" \("id" integer (NOT NULL |)PRIMARY KEY AUTOINCREMENT,', sql):
            continue
        else:
            assert sql.startswith((
                'CREATE TABLE sqlite_sequence',
                'CREATE TABLE alembic_version',
                'CREATE TABLE "storage_disk"',
            ))
            continue

        index_sqls = []
        for index_sql, in conn.execute("""
            SELECT sql
            FROM sqlite_master
            WHERE type = 'index' AND tbl_name = ?
        """, (table_name,)).fetchall():
            if index_sql is not None:
                index_sqls.append(index_sql)

        params = {"table": f'"{name}"', "table_old": f'"{name}__old"'}
        conn.execute("ALTER TABLE %(table)s RENAME TO %(table_old)s" % params)
        conn.execute(new_sql)
        conn.execute("INSERT INTO %(table)s SELECT * FROM %(table_old)s" % params)
        conn.execute("DROP TABLE %(table_old)s" % params)
        for index_sql in index_sqls:
            conn.execute(index_sql)

    conn.execute("PRAGMA legacy_alter_table = FALSE")


def downgrade():
    pass
