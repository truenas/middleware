"""
Remove validate_host_path column from k8s column

Revision ID: a1917e15f409
Revises: 1cdfe58ae329
Create Date: 2023-07-13 20:35:14.561629+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1917e15f409'
down_revision = '1cdfe58ae329'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_kubernetes', schema=None) as batch_op:
        batch_op.drop_column('validate_host_path')


def downgrade():
    pass
