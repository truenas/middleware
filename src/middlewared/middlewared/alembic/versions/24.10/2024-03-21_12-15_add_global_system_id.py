"""Add global system ID

Revision ID: 14974a858948
Revises: 7836261b2f64
Create Date: 2024-03-21 12:15:50.886820+00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '14974a858948'
down_revision = '7836261b2f64'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'system_globalid',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('system_uuid', sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_system_globalid')),
    )


def downgrade():
    pass
