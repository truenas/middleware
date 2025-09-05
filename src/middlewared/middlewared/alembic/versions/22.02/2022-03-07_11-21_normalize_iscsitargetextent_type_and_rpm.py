"""Normalize services_iscsitargetextent type and rpm

Revision ID: 4e027c93e4d1
Revises: 2ed09f3b17b7
Create Date: 2022-03-07 11:21:55.067698+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '4e027c93e4d1'
down_revision = '2ed09f3b17b7'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(text("UPDATE services_iscsitargetextent SET iscsi_target_extent_type = 'DISK' WHERE iscsi_target_extent_type = 'ZVOL'"))
    op.execute(text("UPDATE services_iscsitargetextent SET iscsi_target_extent_type = 'FILE' WHERE iscsi_target_extent_type = 'File'"))
    op.execute(text("UPDATE services_iscsitargetextent SET iscsi_target_extent_rpm = 'UNKNOWN' WHERE iscsi_target_extent_rpm = 'Unknown'"))


def downgrade():
    pass
