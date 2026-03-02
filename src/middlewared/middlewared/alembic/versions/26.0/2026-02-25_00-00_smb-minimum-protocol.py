"""SMB: replace enable_smb1 boolean with minimum_protocol string

Revision ID: a4b1e7f9c2d5
Revises: ce5aac1ae6e8
Create Date: 2026-02-25 00:00:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'a4b1e7f9c2d5'
down_revision = 'ce5aac1ae6e8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_cifs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cifs_srv_minimum_protocol', sa.String(length=120), nullable=True))

    op.execute(text(
        "UPDATE services_cifs SET cifs_srv_minimum_protocol = "
        "CASE WHEN cifs_srv_enable_smb1 = 1 THEN 'SMB1' ELSE 'SMB2' END"
    ))

    with op.batch_alter_table('services_cifs', schema=None) as batch_op:
        batch_op.alter_column('cifs_srv_minimum_protocol', nullable=False)
        batch_op.drop_column('cifs_srv_enable_smb1')


def downgrade():
    with op.batch_alter_table('services_cifs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cifs_srv_enable_smb1', sa.Boolean(), nullable=True))

    op.execute(text(
        "UPDATE services_cifs SET cifs_srv_enable_smb1 = "
        "CASE WHEN cifs_srv_minimum_protocol = 'SMB1' THEN 1 ELSE 0 END"
    ))

    with op.batch_alter_table('services_cifs', schema=None) as batch_op:
        batch_op.alter_column('cifs_srv_enable_smb1', nullable=False)
        batch_op.drop_column('cifs_srv_minimum_protocol')
