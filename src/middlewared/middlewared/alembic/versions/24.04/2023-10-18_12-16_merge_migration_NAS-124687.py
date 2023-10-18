""" Merge migration for NAS-124687

Revision ID: e48b983ea0a0
Revises: 0a95d753f6d3, f7d06a57f8a1
Create Date: 2023-10-18 12:16:35.860672+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e48b983ea0a0'
down_revision = ('0a95d753f6d3', 'f7d06a57f8a1')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
