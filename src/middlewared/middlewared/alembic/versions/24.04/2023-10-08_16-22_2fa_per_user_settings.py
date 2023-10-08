"""
2FA Per user settings

Revision ID: 0a95d753f6d3
Revises: 3df553b07a99
Create Date: 2023-10-08 16:22:17.935672+00:00
"""
import sqlalchemy as sa

from alembic import op


revision = '0a95d753f6d3'
down_revision = '3df553b07a99'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('account_twofactor_user_auth', schema=None) as batch_op:
        batch_op.add_column(sa.Column('interval', sa.INTEGER(), nullable=False, server_default='30'))
        batch_op.add_column(sa.Column('otp_digits', sa.INTEGER(), nullable=False, server_default='6'))
        batch_op.add_column(sa.Column('window', sa.INTEGER(), nullable=False, server_default='0'))


def downgrade():
    pass
