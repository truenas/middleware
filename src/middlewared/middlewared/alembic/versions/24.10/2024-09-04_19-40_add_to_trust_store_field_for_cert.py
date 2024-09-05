"""
Add add_to_trust_store field for certifacates

Revision ID: c31881e67797
Revises: 98c1ebde0079
Create Date: 2024-09-04 19:40:16.801832+00:00
"""
from alembic import op
import sqlalchemy as sa


revision = 'c31881e67797'
down_revision = '98c1ebde0079'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('system_certificate', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cert_add_to_trusted_store', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    pass
