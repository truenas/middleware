"""Converting smb loglevel to debug boolean

Revision ID: a42bdf8fe47d
Revises: bda3a0ff206e
Create Date: 2024-12-03 20:17:16.865011+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a42bdf8fe47d'
down_revision = 'bda3a0ff206e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_cifs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cifs_srv_debug', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.drop_column('cifs_srv_next_rid')
        batch_op.drop_column('cifs_srv_loglevel')


def downgrade():
    with op.batch_alter_table('services_cifs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cifs_srv_loglevel', sa.VARCHAR(length=120), nullable=False))
        batch_op.add_column(sa.Column('cifs_srv_next_rid', sa.INTEGER(), nullable=False))
        batch_op.drop_column('cifs_srv_debug')
