"""Delete OneDrive cloud sync tasks

Revision ID: 2eafc0aa58a0
Revises: 8f8942557260
Create Date: 2023-12-22 11:29:54.877781+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2eafc0aa58a0'
down_revision = '8f8942557260'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute("DELETE FROM tasks_cloudsync WHERE credential_id in (SELECT id FROM system_cloudcredentials WHERE "
                 "provider = 'ONEDRIVE')")
    conn.execute("DELETE FROM system_cloudcredentials WHERE provider = 'ONEDRIVE'")


def downgrade():
    pass
