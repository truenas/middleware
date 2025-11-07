"""
Cleanup disk/raw devices from containers

Revision ID: 6041af215ccd
Revises: ff14ac328c3f
Create Date: 2025-11-06 21:48:28.600327+00:00
"""
import json

from alembic import op
from sqlalchemy import text

from middlewared.utils.pwenc import decrypt


# revision identifiers, used by Alembic.
revision = '6041af215ccd'
down_revision = 'ff14ac328c3f'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Get all container devices and delete those with dtype 'DISK' or 'RAW'
    for device in conn.execute(text("SELECT * FROM container_device")).mappings().all():
        attributes = json.loads(decrypt(device['attributes']))

        if attributes.get('dtype') in ('DISK', 'RAW'):
            conn.execute(
                text("DELETE FROM container_device WHERE id = :id"),
                {"id": device['id']}
            )


def downgrade():
    pass
