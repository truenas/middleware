"""
Change official catalog label

Revision ID: 441144fa08e7
Revises: 7035fa70c0c0
Create Date: 2023-04-27 08:00:08.436590+00:00

"""
import json

from alembic import op


# revision identifiers, used by Alembic.
revision = '441144fa08e7'
down_revision = '7035fa70c0c0'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    conn.execute("DELETE FROM services_catalog WHERE label = 'TRUENAS'")
    conn.execute("UPDATE services_catalog SET label = ? WHERE label = ?", (
        'TRUENAS', 'OFFICIAL'
    ))


def downgrade():
    pass
