"""Remove CUSTOM retention policy from replication tasks that use name_regex

Revision ID: f0e551d2defc
Revises: ae2a519c8b9a
Create Date: 2022-10-12 10:41:03.028186+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f0e551d2defc'
down_revision = 'ae2a519c8b9a'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE storage_replication
        SET repl_retention_policy = 'NONE',
            repl_lifetime_unit = NULL,
            repl_lifetime_value = NULL,
            repl_lifetimes = '[]'
        WHERE repl_name_regex IS NOT NULL
    """)


def downgrade():
    pass
