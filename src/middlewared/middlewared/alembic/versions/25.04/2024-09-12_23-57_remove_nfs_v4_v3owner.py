"""Remove deprecated v4_v3owner NFS configuration option


Revision ID: 6dedf12c1035
Revises: 7b618b9ca77d
Create Date: 2024-09-12 23:57:43.814512+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6dedf12c1035'
down_revision = '7b618b9ca77d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_nfs', schema=None) as batch_op:
        batch_op.drop_column('nfs_srv_v4_v3owner')


def downgrade():
    pass
