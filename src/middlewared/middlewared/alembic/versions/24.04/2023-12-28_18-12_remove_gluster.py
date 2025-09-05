""" remove gluster service

Revision ID: 69789458866a
Revises: a598a2c81461
Create Date: 2023-12-23 18:12:00.848725+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '69789458866a'
down_revision = 'a598a2c81461'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(text("DELETE FROM services_services WHERE srv_service = 'glusterd'"))
    with op.batch_alter_table('sharing_cifs_share', schema=None) as batch_op:
        batch_op.drop_column('cifs_cluster_volname')

def downgrade():
    pass
