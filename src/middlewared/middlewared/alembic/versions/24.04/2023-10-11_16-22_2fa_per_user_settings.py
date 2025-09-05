"""
2FA Per user settings

Revision ID: 0a95d753f6d3
Revises: 6f338216a965
Create Date: 2023-10-11 16:22:17.935672+00:00
"""
import sqlalchemy as sa
from sqlalchemy import text

from alembic import op


revision = '0a95d753f6d3'
down_revision = '6f338216a965'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('account_twofactor_user_auth', schema=None) as batch_op:
        batch_op.add_column(sa.Column('interval', sa.INTEGER(), nullable=False, server_default='30'))
        batch_op.add_column(sa.Column('otp_digits', sa.INTEGER(), nullable=False, server_default='6'))

    conn = op.get_bind()

    if twofactor_config := list(map(
        dict, conn.execute(text('SELECT * FROM system_twofactorauthentication')).fetchall()
    )):
        twofactor_config = twofactor_config[0]
        for row in map(dict, conn.execute(text('SELECT id FROM account_twofactor_user_auth')).fetchall()):
            conn.execute(text(
                'UPDATE account_twofactor_user_auth SET interval = :interval, otp_digits = :otp_digits WHERE id = :id'), {
                    'interval': twofactor_config['interval'], 'otp_digits': twofactor_config['otp_digits'], 'id': row['id']
                }
            )

    with op.batch_alter_table('system_twofactorauthentication', schema=None) as batch_op:
        batch_op.drop_column('interval')
        batch_op.drop_column('otp_digits')


def downgrade():
    pass
