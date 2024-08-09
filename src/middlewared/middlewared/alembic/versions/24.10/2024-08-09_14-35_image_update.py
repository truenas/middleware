"""
Add flag to see if image update is requried

Revision ID: 4b0b7ba46e63
Revises: 81b8bae8fb11
Create Date: 2024-08-09 14:35:35.379137+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '4b0b7ba46e63'
down_revision = '81b8bae8fb11'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_docker', schema=None) as batch_op:
        batch_op.add_column(sa.Column('enable_image_updates', sa.Boolean(), nullable=False, server_default='1'))


def downgrade():
    pass
