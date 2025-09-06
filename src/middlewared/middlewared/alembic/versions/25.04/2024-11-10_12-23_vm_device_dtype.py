from sqlalchemy import text

"""
Normalize vm_device attributes with dtype

Revision ID: 0972c1f572b8
Revises: f077d0ae123d
Create Date: 2024-11-10 12:23:04.993358+00:00
"""
import json

from alembic import op

from middlewared.utils.pwenc import encrypt, decrypt


revision = '0972c1f572b8'
down_revision = 'f077d0ae123d'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    for vm_device_config in [row._asdict() for row in conn.execute(text("SELECT * FROM vm_device")).fetchall()]:
        attributes = json.loads(decrypt(vm_device_config['attributes']))
        attributes['dtype'] = vm_device_config['dtype']
        conn.execute(
            text("UPDATE vm_device SET attributes = :attributes WHERE id = :id"),
            {'attributes': encrypt(json.dumps(attributes)), 'id': vm_device_config['id']}
        )

    with op.batch_alter_table('vm_device', schema=None) as batch_op:
        batch_op.drop_column('dtype')


def downgrade():
    pass
