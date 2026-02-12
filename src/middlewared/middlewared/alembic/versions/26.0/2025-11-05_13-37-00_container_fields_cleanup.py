"""
Container Device fields cleanup

Revision ID: 32ef531bba38
Revises: e794ef384903
Create Date: 2025-11-05 13:37:28.600327+00:00
"""
import json

from alembic import op
from sqlalchemy import text

from middlewared.utils.pwenc import decrypt, encrypt


# revision identifiers, used by Alembic.
revision = '32ef531bba38'
down_revision = 'e794ef384903'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    for device in conn.execute(text("SELECT * FROM container_device")).mappings().all():
        attributes = json.loads(decrypt(device['attributes']))

        if attributes.get('dtype') not in ('DISK', 'RAW', 'USB'):
            continue

        if attributes['dtype'] == 'USB':
            fields_to_remove = ['controller_type']
        else:
            fields_to_remove = ['boot', 'logical_sectorsize', 'physical_sectorsize', 'iotype', 'serial']

        for field in fields_to_remove:
            attributes.pop(field, None)

        conn.execute(
            text("UPDATE container_device SET attributes = :attributes WHERE id = :id"),
            {"attributes": encrypt(json.dumps(attributes)), "id": device['id']}
        )

    with op.batch_alter_table('container_device', schema=None) as batch_op:
        batch_op.drop_column('order')


def downgrade():
    pass
