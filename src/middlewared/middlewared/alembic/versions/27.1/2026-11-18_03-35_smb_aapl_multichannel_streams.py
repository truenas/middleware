"""Remove SMB aapl_extensions, multichannel and streams

Revision ID: 7c9f747412d6
Revises: f605e9ad654d
Create Date: 2026-11-18 03:35:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c9f747412d6'
down_revision = 'f605e9ad654d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_cifs', schema=None) as batch_op:
        batch_op.drop_column('cifs_srv_aapl_extensions')
        batch_op.drop_column('cifs_srv_multichannel')

    with op.batch_alter_table('sharing_cifs_share', schema=None) as batch_op:
        batch_op.drop_column('cifs_streams')


def downgrade():
    with op.batch_alter_table('sharing_cifs_share', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cifs_streams', sa.Boolean(), nullable=False, server_default='1'))

    with op.batch_alter_table('services_cifs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cifs_srv_multichannel', sa.Boolean(), nullable=False, server_default='1'))
        batch_op.add_column(sa.Column('cifs_srv_aapl_extensions', sa.Boolean(), nullable=False, server_default='1'))
