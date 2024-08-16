"""Merge migration for changes in SMB-related fields from 24.04

Revision ID: 135a7e02cbec
Revises: 4f11cc19bb9c, f38c2bbe776a
Create Date: 2024-05-02 12:00:35.086514+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '135a7e02cbec'
down_revision = ('4f11cc19bb9c', 'f38c2bbe776a')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
