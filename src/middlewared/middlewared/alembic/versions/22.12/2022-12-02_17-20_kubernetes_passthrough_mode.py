"""
Kubernetes passthrough mode

Revision ID: fa4097ef2236
Revises: dc9ffe67a56f
Create Date: 2022-12-02 17:20:21.541782+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'fa4097ef2236'
down_revision = 'dc9ffe67a56f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_kubernetes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('passthrough_mode', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    pass
