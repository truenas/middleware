"""
iSCSI Vendor configuration

Revision ID: 22230265ab30
Revises: 43779dce3a07
Create Date: 2020-05-04 21:19:22.658721-07:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '22230265ab30'
down_revision = '43779dce3a07'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_iscsitargetextent', schema=None) as batch_op:
        batch_op.add_column(sa.Column('iscsi_target_extent_vendor', sa.TEXT(), nullable=True))

    conn = op.get_bind()
    for extent in conn.execute(text("SELECT * FROM services_iscsitargetextent")).mappings():
        conn.execute(text("UPDATE services_iscsitargetextent SET iscsi_target_extent_vendor = :vendor WHERE id = :id"), {
            'vendor': 'FreeBSD' if extent['iscsi_target_extent_legacy'] else None, 'id': extent['id']
        })

    with op.batch_alter_table('services_iscsitargetextent', schema=None) as batch_op:
        batch_op.drop_column('iscsi_target_extent_legacy')
