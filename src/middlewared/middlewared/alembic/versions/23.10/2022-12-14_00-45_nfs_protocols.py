"""Replace v4 with protocols in nfs service configuration.

Revision ID: 60de23d5cd17
Revises: 136adf794fed
Create Date: 2022-12-14 00:45:57.157120+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '60de23d5cd17'
down_revision = '136adf794fed'
branch_labels = None
depends_on = None


def upgrade():
    # Replace nfs_srv_v4 (a boolean) with nfs_srv_protocols

    # First read the current state, so that we can tweak the default value of
    # the new column based upon the values.
    conn = op.get_bind()
    share_count = conn.execute(text("SELECT COUNT(id) FROM sharing_nfs_share")).first()[0]
    nfs_srv_v4  = conn.execute(text("SELECT nfs_srv_v4 FROM services_nfs")).first()[0]

    # Want to check whether we can change the default to include
    with op.batch_alter_table('services_nfs', schema=None) as batch_op:
        if share_count == 0 or nfs_srv_v4:
            batch_op.add_column(sa.Column('nfs_srv_protocols', sa.TEXT(), nullable=False, server_default='["NFSV3", "NFSV4"]'))
        else:
            batch_op.add_column(sa.Column('nfs_srv_protocols', sa.TEXT(), nullable=False, server_default='["NFSV3"]'))
        batch_op.drop_column('nfs_srv_v4')


def downgrade():
    conn = op.get_bind()
    nfs_srv_protocols = conn.execute(text("SELECT nfs_srv_protocols FROM services_nfs")).first()[0]
    with op.batch_alter_table('services_nfs', schema=None) as batch_op:
        if "NFSV4" in nfs_srv_protocols:
            batch_op.add_column(sa.Column('nfs_srv_v4', sa.BOOLEAN(), nullable=False, server_default='1'))
        else:
            batch_op.add_column(sa.Column('nfs_srv_v4', sa.BOOLEAN(), nullable=False, server_default='0'))
        batch_op.drop_column('nfs_srv_protocols')
