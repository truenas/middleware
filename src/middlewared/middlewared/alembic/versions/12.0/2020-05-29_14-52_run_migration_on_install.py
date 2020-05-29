"""Run data migration on install / factory reset

Revision ID: b694f05c1169
Revises: a3ac49efb063
Create Date: 2020-05-29 14:52:52.049932+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b694f05c1169'
down_revision = 'a3ac49efb063'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("REPLACE INTO system_keyvalue (key, value) VALUES ('run_migration', 'true')")


def downgrade():
    pass
