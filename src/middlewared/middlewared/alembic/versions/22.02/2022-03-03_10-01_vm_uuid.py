"""
Add VM uuid field

Revision ID: 2ed09f3b17b7
Revises: 7a143979d99b
Create Date: 2022-03-03 10:01:38.186590+00:00

"""
import uuid

from alembic import op
import sqlalchemy as sa


revision = '2ed09f3b17b7'
down_revision = '7a143979d99b'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    with op.batch_alter_table('vm_vm', schema=None) as batch_op:
        batch_op.add_column(sa.Column('uuid', sa.String(length=255), nullable=False, server_default=''))

    for vm in map(dict, conn.execute("SELECT * FROM vm_vm").fetchall()):
        conn.execute("UPDATE vm_vm SET uuid = ? WHERE id = ?", (str(uuid.uuid4()), vm['id']))


def downgrade():
    pass
