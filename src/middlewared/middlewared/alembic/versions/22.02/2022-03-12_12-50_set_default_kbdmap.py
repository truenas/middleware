"""Set default kbdmap

Revision ID: 8c9ad60244de
Revises: b3c5a5321aef
Create Date: 2022-03-12 12:50:48.732801+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '8c9ad60244de'
down_revision = 'b3c5a5321aef'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(text("UPDATE system_settings SET stg_kbdmap = 'us' WHERE stg_kbdmap = ''"))


def downgrade():
    pass
