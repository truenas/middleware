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
    # We want to skip tables like sqlite_sequence
    tables = conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).all()

    for (table_name,) in tables:
        # PRAGMA TABLE_INFO returns dict-like rows when using .mappings()
        cols = conn.exec_driver_sql(f"PRAGMA TABLE_INFO(\"{table_name}\")").mappings().all()
        for col in cols:
            col_name = col["name"]
            col_type = (col.get("type") or "").lower()
            if col_type in ("bool", "boolean"):
                conn.exec_driver_sql(
                    f'UPDATE "{table_name}" SET "{col_name}" = 1 WHERE "{col_name}" IN (\'1\',\'true\') COLLATE NOCASE'
                )
                conn.exec_driver_sql(
                    f'UPDATE "{table_name}" SET "{col_name}" = 0 WHERE "{col_name}" != 1 AND "{col_name}" IS NOT NULL'
                )


def downgrade():
    pass
