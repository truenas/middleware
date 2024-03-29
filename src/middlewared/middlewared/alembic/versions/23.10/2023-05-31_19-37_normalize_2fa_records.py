"""
Normalize 2FA AD records

Revision ID: 1519ee5b6e29
Revises: a63a2c20632a
Create Date: 2023-05-31 19:37:17.935672+00:00
"""
from alembic import op


revision = '1519ee5b6e29'
down_revision = 'a63a2c20632a'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    # We will now get all existing records from 2fa table and then if some user does not has his record in 2fa table
    # we will add it to the 2fa table
    existing_records = [
        user_id['user_id'] for user_id in map(
            dict, conn.execute('SELECT user_id FROM account_twofactor_user_auth').fetchall()
        )
    ]
    for row in map(dict, conn.execute('SELECT id FROM account_bsdusers').fetchall()):
        if row['id'] in existing_records:
            continue

        secret = None
        conn.execute('INSERT INTO account_twofactor_user_auth (secret,user_id) VALUES (?,?)', (secret, row['id']))


def downgrade():
    pass
