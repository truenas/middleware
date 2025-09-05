"""Add auditing backend tables

Revision ID: 6f338216a965
Revises: 3df553b07a99
Create Date: 2023-10-02 19:31:49.067706+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '6f338216a965'
down_revision = '3df553b07a99'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    op.create_table('system_audit',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('retention', sa.Integer(), nullable=False),
    sa.Column('reservation', sa.Integer(), nullable=False),
    sa.Column('quota', sa.Integer(), nullable=False),
    sa.Column('quota_fill_warning', sa.Integer(), nullable=False),
    sa.Column('quota_fill_critical', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_system_audit')),
    sqlite_autoincrement=True
    )
    with op.batch_alter_table('system_advanced', schema=None) as batch_op:
        batch_op.add_column(sa.Column('adv_syslog_audit', sa.Boolean(), nullable=True))

    conn.execute(text('UPDATE system_advanced SET adv_syslog_audit = :audit'), {'audit': False})
    with op.batch_alter_table('system_advanced', schema=None) as batch_op:
        batch_op.alter_column('adv_syslog_audit', existing_type=sa.Boolean(), nullable=False)
