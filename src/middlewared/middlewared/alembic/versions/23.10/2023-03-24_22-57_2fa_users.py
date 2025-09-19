"""
2FA support for multiple users

Revision ID: 55836e7dac39
Revises: c55b034b7654
Create Date: 2023-03-24 22:57:01.757983+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


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
    existing_secret_record = conn.execute(text('SELECT secret FROM system_twofactorauthentication')).mappings().first()
    existing_secret = existing_secret_record['secret'] if existing_secret_record else None

    for row in conn.execute(text('SELECT id,bsdusr_uid FROM account_bsdusers')).mappings().all():
        secret = existing_secret if row['bsdusr_uid'] == 0 else None
        conn.execute(text('INSERT INTO account_twofactor_user_auth (secret,user_id) VALUES (:secret, :user_id)'), {'secret': secret, 'user_id': row['id']})

    with op.batch_alter_table('system_twofactorauthentication', schema=None) as batch_op:
        batch_op.drop_column('secret')


def downgrade():
    pass
