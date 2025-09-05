"""Add fields for local password STIG requirements

Revision ID: ec62dbbeb7aa
Revises: df0bffcf1595
Create Date: 2025-03-26 18:30:31.856948+00:00

"""
from alembic import op
from datetime import datetime, UTC
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'ec62dbbeb7aa'
down_revision = 'df0bffcf1595'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    now = int(datetime.now(UTC).timestamp())

    with op.batch_alter_table('account_bsdusers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('bsdusr_last_password_change', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('bsdusr_password_history', sa.TEXT(), nullable=True))

    with op.batch_alter_table('system_security', schema=None) as batch_op:
        batch_op.add_column(sa.Column('min_password_age', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('max_password_age', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('password_complexity_ruleset', sa.TEXT(), nullable=True))
        batch_op.add_column(sa.Column('min_password_length', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('password_history_length', sa.Integer(), nullable=True))

    # Initialize the password last set date for local accounts with passwords
    # This ensures that accounts will not get locked out if admin sets a max password age
    conn.execute(text(f'UPDATE account_bsdusers SET bsdusr_last_password_change="{now}" WHERE bsdusr_unixhash!="*"'))
