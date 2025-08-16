"""Add nvme.host

Revision ID: d625ec2aeeee
Revises: 9fbe2e3c32b6
Create Date: 2025-08-16 00:33:22.399101+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd625ec2aeeee'
down_revision = '9fbe2e3c32b6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('storage_nvme_host',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nvme_host_hostid_a', sa.String(length=32), nullable=False),
    sa.Column('nvme_host_hostnqn_a', sa.String(), nullable=False),
    sa.Column('nvme_host_hostid_b', sa.String(length=32), nullable=False),
    sa.Column('nvme_host_hostnqn_b', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_storage_nvme_host')),
    sqlite_autoincrement=True
    )


def downgrade():
    pass
