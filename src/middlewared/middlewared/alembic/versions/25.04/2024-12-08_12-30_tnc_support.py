"""
TNC Support

Revision ID: 83d9689fcbc8
Revises: 4e6f1334f0f0
Create Date: 2024-11-30 12:30:41.855489+00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '83d9689fcbc8'
down_revision = '4e6f1334f0f0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'truenas_connect',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.BOOLEAN(), nullable=False),
        sa.Column('jwt_token', sa.TEXT(), nullable=True),
        sa.Column('ips', sa.TEXT(), nullable=False, server_default='[]'),
        sa.Column('registration_details', sa.TEXT(), nullable=False, server_default='{}'),
        sa.Column('status', sa.String(length=255), nullable=False),
        sa.Column('certificate_id', nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_truenas_connect')),
        sa.ForeignKeyConstraint(
            ['certificate_id'], ['system_certificate.id'],
            name=op.f('fk_truenas_connect_certificate_id_system_certificate')
        ),
        sqlite_autoincrement=True,
    )


def downgrade():
    pass
