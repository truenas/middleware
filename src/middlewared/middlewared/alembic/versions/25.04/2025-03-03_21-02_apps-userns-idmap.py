"""Add userns_idmap to apps user and group

Revision ID: 0257529fa6d5
Revises: 9ada77affbb9
Create Date: 2025-03-03 21:02:55.899182+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '0257529fa6d5'
down_revision = '9ada77affbb9'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(text('UPDATE account_bsdusers SET bsdusr_userns_idmap="DIRECT" WHERE bsdusr_uid=568'))
    conn.execute(text('UPDATE account_bsdgroups SET bsdgrp_userns_idmap="DIRECT" WHERE bsdgrp_gid=568'))
