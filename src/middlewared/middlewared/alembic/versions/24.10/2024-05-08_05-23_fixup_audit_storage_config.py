"""
Allow the system.audit quota and reservation fields to be disabled with a 'None' setting.

Revision ID: d8e7c9bab524
Revises: 135a7e02cbec
Create Date: 2024-05-08 05:23:43.195180+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd8e7c9bab524'
down_revision = '135a7e02cbec'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('system_audit', schema=None) as batch_op:
        batch_op.alter_column('reservation',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('quota',
               existing_type=sa.INTEGER(),
               nullable=True)

    conn = op.get_bind()
    conn.execute("UPDATE system_audit SET quota = NULL WHERE quota = 0")
    conn.execute("UPDATE system_audit SET reservation = NULL WHERE reservation = 0")


def downgrade():
    pass
