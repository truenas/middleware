"""Disable password when empty string is used.

Revision ID: 595b38b52541
Revises: d7e3a916db65
Create Date: 2025-04-14 15:57:08.141738+00:00

"""
from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '595b38b52541'
down_revision = 'd7e3a916db65'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(text('UPDATE account_bsdusers SET bsdusr_password_disabled = TRUE WHERE bsdusr_unixhash = "*"'))


def downgrade():
    pass
