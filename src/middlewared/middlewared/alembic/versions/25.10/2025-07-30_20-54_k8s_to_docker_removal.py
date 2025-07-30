"""
Remove CA plugin

Revision ID: 7767afd88989
Revises: 3298b9ae612b
Create Date: 2025-07-30 20:54:53.749089+00:00

"""
from alembic import op


revision = '7767afd88989'
down_revision = '3298b9ae612b'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('services_kubernetes')

def downgrade():
    pass
