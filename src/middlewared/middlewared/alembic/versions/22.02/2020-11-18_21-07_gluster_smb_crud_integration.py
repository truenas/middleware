"""
gluster intergration with smb crud api

Revision ID: 3d611f8cc676
Revises: ce614715260a
Create Date: 2020-11-18 21:07:55.014310+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3d611f8cc676'
down_revision = 'ce614715260a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('sharing_cifs_share', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'cifs_cluster_volname',
            sa.String(length=255),
            server_default='',
            nullable=False,
        ))


def downgrade():
    with op.batch_alter_table('sharing_cifs_share', schema=None) as batch_op:
        batch_op.drop_column('cifs_cluster_volname')
