"""
2FA support for multiple users

Revision ID: 55836e7dac39
Revises: c55b034b7654
Create Date: 2023-03-24 22:57:01.757983+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '55836e7dac39'
down_revision = 'c55b034b7654'
branch_labels = None
depends_on = None


def upgrade():
    # We want 3 things here:
    # 1) Have a model where we can keep user 2fa data
    # 2) Have a model where global 2fa configurations can be enforced
    # 3) Migrate

    op.create_table(
        'account_twofactor_user_auth',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('secret', sa.String(length=16), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ['user_id'], ['account_bsdusers.id'], name=op.f('fk_account_twofactor_user_auth_user_id_account_bsdusers'),
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_account_twofactor_user_auth')),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table('account_twofactor_user_auth', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_account_twofactor_user_auth_user_id'), ['user_id'], unique=False)

    conn = op.get_bind()
    existing_secret_record = conn.execute('SELECT secret FROM system_twofactorauthentication').fetchone()
    existing_secret = existing_secret_record['secret'] if existing_secret_record else None

    for row in map(dict, conn.execute('SELECT id,bsdusr_uid FROM account_bsdusers').fetchall()):
        row = dict(row)
        secret = existing_secret if row['bsdusr_uid'] == 0 else None
        conn.execute('INSERT INTO account_twofactor_user_auth (secret,user_id) VALUES (?,?)', (secret, row['id']))

    with op.batch_alter_table('system_twofactorauthentication', schema=None) as batch_op:
        batch_op.drop_column('secret')


def downgrade():
    pass
