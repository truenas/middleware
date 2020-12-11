"""
Migration for ix-applications support

Revision ID: f8b573192e43
Revises: 6dfba265232e
Create Date: 2020-08-24 14:32:34.620255+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'f8b573192e43'
down_revision = '6dfba265232e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'services_kubernetes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pool', sa.String(length=255), nullable=True),
        sa.Column('cluster_cidr', sa.String(length=128), nullable=False),
        sa.Column('service_cidr', sa.String(length=128), nullable=False),
        sa.Column('cluster_dns_ip', sa.String(length=128), nullable=False),
        sa.Column('route_v4_interface', sa.String(length=128), nullable=True),
        sa.Column('route_v4_gateway', sa.String(length=128), nullable=True),
        sa.Column('route_v6_interface', sa.String(length=128), nullable=True),
        sa.Column('route_v6_gateway', sa.String(length=128), nullable=True),
        sa.Column('node_ip', sa.String(length=128), nullable=False),
        sa.Column('cni_config', sa.TEXT(), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_services_kubernetes')),
    )


def downgrade():
    pass
