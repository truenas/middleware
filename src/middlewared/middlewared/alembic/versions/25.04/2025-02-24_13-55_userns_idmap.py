"""Add userns_idmap field to accounts

Revision ID: 9ada77affbb9
Revises: ae78ab5ebf07
Create Date: 2025-02-24 13:55:21.268932+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9ada77affbb9'
down_revision = 'ae78ab5ebf07'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('account_bsdgroups', schema=None) as batch_op:
        batch_op.add_column(sa.Column('bsdgrp_userns_idmap', sa.Integer(), nullable=False, server_default='0'))

    with op.batch_alter_table('account_bsdusers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('bsdusr_userns_idmap', sa.Integer(), nullable=False, server_default='0'))
