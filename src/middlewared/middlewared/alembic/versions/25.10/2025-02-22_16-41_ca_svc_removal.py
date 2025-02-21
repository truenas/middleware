"""
Remove CA plugin

Revision ID: 9a5b103ec2e4
Revises: ae78ab5ebf07
Create Date: 2025-02-22 16:41:53.749089+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '9a5b103ec2e4'
down_revision = 'ae78ab5ebf07'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()


def downgrade():
    pass
