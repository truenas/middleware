"""Add table for fc.fc_host CRUD APIs

Revision ID: 05147f987272
Revises: dd6e581235b2
Create Date: 2024-10-21 20:30:12.596692+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '05147f987272'
down_revision = 'dd6e581235b2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('services_fc_host',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('fc_host_alias', sa.String(length=32), nullable=False),
    sa.Column('fc_host_wwpn', sa.String(length=20), nullable=True),
    sa.Column('fc_host_wwpn_b', sa.String(length=20), nullable=True),
    sa.Column('fc_host_npiv', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_services_fc_host')),
    sa.UniqueConstraint('fc_host_alias', name=op.f('uq_services_fc_host_fc_host_alias')),
    sa.UniqueConstraint('fc_host_wwpn', name=op.f('uq_services_fc_host_fc_host_wwpn')),
    sa.UniqueConstraint('fc_host_wwpn_b', name=op.f('uq_services_fc_host_fc_host_wwpn_b')),
    sqlite_autoincrement=True
    )


def downgrade():
    op.drop_table('services_fc_host')
