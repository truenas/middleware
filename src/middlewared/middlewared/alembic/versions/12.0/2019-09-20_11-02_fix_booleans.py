"""Fix booleans

Revision ID: d38e9cc6174c
Revises: a3423860aea0
Create Date: 2019-09-27 08:20:13.391318+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'e49fadd7285d'
down_revision = 'c6be4fe10acc'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    for table_name, in conn.execute(text("SELECT name FROM sqlite_master WHERE type = 'table'")).fetchall():
        for column in conn.execute(text(f"PRAGMA TABLE_INFO('{table_name}')")):
            # SQLAlchemy 2.0+ returns tuples: (cid, name, type, notnull, dflt_value, pk)
            column_name = column[1]  # name is at index 1
            column_type = column[2]  # type is at index 2
            if column_type.lower() in ("bool", "boolean"):
                conn.execute(text(f"UPDATE {table_name} SET {column_name} = 1 WHERE {column_name} IN ('1', 'true') COLLATE NOCASE"))
                conn.execute(text(f"UPDATE {table_name} SET {column_name} = 0 WHERE {column_name} != 1 AND {column_name} IS NOT NULL"))


def downgrade():
    pass
