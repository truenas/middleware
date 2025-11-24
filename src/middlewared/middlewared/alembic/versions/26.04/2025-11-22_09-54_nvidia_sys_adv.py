"""
Move nvidia driver configuration to sys adv

Revision ID: bf646ce959c5
Revises: 6f96bf204394
Create Date: 2025-11-22 09:54:18.331279+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'bf646ce959c5'
down_revision = '6f96bf204394'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('system_advanced', schema=None) as batch_op:
        batch_op.add_column(sa.Column('adv_nvidia', sa.Boolean(), server_default='0', nullable=False))

    op.execute(text(
        "UPDATE system_advanced SET adv_nvidia = (SELECT nvidia FROM services_docker LIMIT 1) "
        "WHERE EXISTS (SELECT 1 FROM services_docker)"
    ))

    with op.batch_alter_table('services_docker', schema=None) as batch_op:
        batch_op.drop_column('nvidia')


def downgrade():
    pass
