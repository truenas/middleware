"""
Migration for custom catalogs support

Revision ID: c747d1692290
Revises: 2fb0f87b2f17
Create Date: 2020-08-24 14:32:34.620255+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'c747d1692290'
down_revision = '2fb0f87b2f17'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'services_catalog',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=True),
        sa.Column('repository', sa.String(length=128), nullable=False),
        sa.Column('branch', sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_services_kubernetes')),
    )
    op.execute(
        "INSERT INTO services_catalog (label, repository, branch) VALUES"
        " ('OFFICIAL', 'https://github.com/truenas/charts.git', 'master')"
    )


def downgrade():
    pass
