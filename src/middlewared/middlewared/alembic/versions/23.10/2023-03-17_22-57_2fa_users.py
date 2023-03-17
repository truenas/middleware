"""
2FA support for multiple usrers

Revision ID: 55836e7dac39
Revises: 7310292225d3
Create Date: 2023-03-15 22:57:01.757983+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '55836e7dac39'
down_revision = '7310292225d3'
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
        sa.PrimaryKeyConstraint('id', name=op.f('pk_account_twofactor_user_auth')),
        sqlite_autoincrement=True,
    )

    with op.batch_alter_table('account_bsdusers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('bsdusr_twofactor_auth_id', sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f('ix_account_bsdusers_bsdusr_twofactor_auth_id'), ['bsdusr_twofactor_auth_id'], unique=False,
        )
        batch_op.create_foreign_key(
            batch_op.f('fk_account_bsdusers_bsdusr_twofactor_auth_id_account_twofactor_user_auth'),
            'account_twofactor_user_auth', ['bsdusr_twofactor_auth_id'], ['id'], ondelete='CASCADE'
        )

    conn = op.get_bind()
    existing_secret = conn.execute('SELECT secret FROM system_twofactorauthentication').fetchone()['secret']

    for row in map(
        dict, conn.execute(
            'SELECT id,bsdusr_uid FROM account_bsdusers WHERE bsdusr_twofactor_auth_id is NULL'
        ).fetchall()
    ):
        row = dict(row)
        secret = existing_secret if row['bsdusr_uid'] == 0 else None
        conn.execute('INSERT INTO account_twofactor_user_auth (secret) VALUES (?)', (secret,))
        foreign_id = conn.execute('SELECT MAX(id) as id FROM account_twofactor_user_auth').fetchone()['id']
        conn.execute(f'UPDATE account_bsdusers SET bsdusr_twofactor_auth_id={foreign_id} WHERE id={row["id"]}')

    with op.batch_alter_table('system_twofactorauthentication', schema=None) as batch_op:
        batch_op.drop_column('secret')


def downgrade():
    pass
