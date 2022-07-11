"""Merge migration post acltemplate comment addition

Revision ID: 0feebf8ad1ed
Revises: adb5c45a0383, 1c8a45c2ec20
Create Date: 2022-07-11 17:49:00.772568+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0feebf8ad1ed'
down_revision = ('adb5c45a0383', '1c8a45c2ec20')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
