"""Account privileges

Revision ID: 79942334975f
Revises: e3a81e1c2135
Create Date: 2022-08-09 13:37:57.243188+00:00

"""
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '79942334975f'
down_revision = 'e3a81e1c2135'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('account_privilege',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('builtin_name', sa.String(length=200), nullable=True),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('local_groups', sa.TEXT(), nullable=False),
    sa.Column('ds_groups', sa.TEXT(), nullable=False),
    sa.Column('allowlist', sa.TEXT(), nullable=False),
    sa.Column('web_shell', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_account_privilege')),
    sqlite_autoincrement=True
    )

    conn = op.get_bind()
    for row in conn.execute("SELECT * FROM account_bsdgroups WHERE bsdgrp_group = 'builtin_administrators'").fetchall():
        builtin_administrators_id = row["id"]
        break
    else:
        conn.execute("INSERT INTO account_bsdgroups (bsdgrp_gid, bsdgrp_group, bsdgrp_builtin, bsdgrp_sudo, bsdgrp_smb,"
                     "bsdgrp_sudo_commands, bsdgrp_sudo_nopasswd) VALUES (544, 'builtin_administrators', 1, 0, 1, '[]',"
                     "0)")
        builtin_administrators_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    root_id = conn.execute("SELECT * FROM account_bsdusers WHERE bsdusr_uid = 0").fetchone()["id"]

    allowlist = [{"method": "*", "resource": "*"}]
    op.execute("INSERT INTO account_privilege (builtin_name, name, local_groups, ds_groups, allowlist, web_shell) "
               f"VALUES ('LOCAL_ADMINISTRATOR', 'Local Administrator', '[544]', '[]', '{json.dumps(allowlist)}', 1)")
    if not list(conn.execute(
        f"SELECT * FROM account_bsdgroupmembership WHERE bsdgrpmember_group_id = {builtin_administrators_id} AND "
        f"bsdgrpmember_user_id = {root_id}"
    ).fetchall()):
        op.execute(f"INSERT INTO account_bsdgroupmembership (bsdgrpmember_group_id, bsdgrpmember_user_id) VALUES "
                   f"({builtin_administrators_id}, {root_id})")

    with op.batch_alter_table('system_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stg_ds_auth', sa.Boolean(), nullable=False, server_default='0'))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('system_settings', schema=None) as batch_op:
        batch_op.drop_column('stg_ds_auth')

    op.drop_table('account_privilege')
    # ### end Alembic commands ###
