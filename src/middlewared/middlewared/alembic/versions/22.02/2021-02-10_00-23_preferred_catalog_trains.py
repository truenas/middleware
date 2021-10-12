"""
Add Preferred Train option for catalogs

Revision ID: daa17e858eaf
Revises: c747d1692290
Create Date: 2021-02-10 00:23:15.609666+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'daa17e858eaf'
down_revision = 'c747d1692290'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_catalog', schema=None) as batch_op:
        batch_op.add_column(sa.Column('preferred_trains', sa.TEXT(), nullable=False, server_default='[\"charts\"]'))


def downgrade():
    pass
