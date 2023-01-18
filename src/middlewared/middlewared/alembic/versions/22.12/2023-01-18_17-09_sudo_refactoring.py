"""sudo refactoring

Revision ID: 004f0934ff0f
Revises: 48d82c064ea2
Create Date: 2023-01-18 17:09:36.160574+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004f0934ff0f'
down_revision = '48d82c064ea2'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    for table, prefix in [("account_bsdusers", "bsdusr_"), ("account_bsdgroups", "bsdgrp_")]:
        op.execute(f"""
            UPDATE {table}
            SET {prefix}sudo_commands = '["ALL"]'
            WHERE {prefix}sudo = 1 AND {prefix}sudo_commands = '[]'
        """)
        op.execute(f"""
            UPDATE {table}
            SET {prefix}sudo_commands_nopasswd = {prefix}sudo_commands, {prefix}sudo_commands = '[]'
            WHERE {prefix}sudo = 1 AND {prefix}sudo_nopasswd = 1
        """)

    with op.batch_alter_table('account_bsdgroups', schema=None) as batch_op:
        batch_op.drop_column('bsdgrp_sudo_nopasswd')
        batch_op.drop_column('bsdgrp_sudo')

    with op.batch_alter_table('account_bsdusers', schema=None) as batch_op:
        batch_op.drop_column('bsdusr_sudo')
        batch_op.drop_column('bsdusr_sudo_nopasswd')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('account_bsdusers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('bsdusr_sudo_nopasswd', sa.BOOLEAN(), server_default=sa.text("'0'"), nullable=False))
        batch_op.add_column(sa.Column('bsdusr_sudo', sa.BOOLEAN(), nullable=False))

    with op.batch_alter_table('account_bsdgroups', schema=None) as batch_op:
        batch_op.add_column(sa.Column('bsdgrp_sudo', sa.BOOLEAN(), nullable=False))
        batch_op.add_column(sa.Column('bsdgrp_sudo_nopasswd', sa.BOOLEAN(), server_default=sa.text("'0'"), nullable=False))

    # ### end Alembic commands ###
