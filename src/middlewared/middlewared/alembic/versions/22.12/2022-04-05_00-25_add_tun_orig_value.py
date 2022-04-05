"""add tunables_orig_value

Revision ID: 1bd044af765d
Revises: 6e73632d6e88
Create Date: 2022-04-05 00:25:56.744546+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1bd044af765d'
down_revision = '6e73632d6e88'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('system_tunable', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tun_orig_value', sa.String(length=512), server_default='', nullable=False))


def downgrade():
    pass
