"""Fix booleans

Revision ID: d38e9cc6174c
Revises: a3423860aea0
Create Date: 2019-09-27 08:20:13.391318+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e49fadd7285d'
down_revision = 'c6be4fe10acc'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    for table_name, in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall():
        for column in conn.execute(f"PRAGMA TABLE_INFO('{table_name}')"):
            if column["type"].lower() in ("bool", "boolean"):
                op.execute(f"UPDATE {table_name} SET {column['name']} = 1 WHERE {column['name']} IN ('1', 'true') COLLATE NOCASE")
                op.execute(f"UPDATE {table_name} SET {column['name']} = 0 WHERE {column['name']} != 1 AND {column['name']} IS NOT NULL")


def downgrade():
    pass
