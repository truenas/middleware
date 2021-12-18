"""add servicelb toggle

Revision ID: daec6faa9589
Revises: 91b71800c7fe
Create Date: 2021-11-09 22:08:27.526805+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'daec6faa9589'
down_revision = '91b71800c7fe'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_kubernetes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('servicelb', sa.Boolean(), server_default='1', nullable=False))


def downgrade():
    pass
