"""
Allow container image updates to be configurable

Revision ID: 920a1a135ef7
Revises: 3d611f8cc676
Create Date: 2020-12-14 05:11:26.058680+00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '920a1a135ef7'
down_revision = '3d611f8cc676'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'services_container',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('enable_image_updates', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_services_container')),
    )
