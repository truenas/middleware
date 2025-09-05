from sqlalchemy import text

"""
Change official catalog label

Revision ID: 441144fa08e7
Revises: 08539dfd0500
Create Date: 2023-05-18 08:00:08.436590+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '441144fa08e7'
down_revision = '08539dfd0500'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    conn.execute(text("DELETE FROM services_catalog WHERE label = 'TRUENAS'"))
    conn.execute("UPDATE services_catalog SET label = ? WHERE label = ?", (
        'TRUENAS', 'OFFICIAL'
    ))


def downgrade():
    pass
