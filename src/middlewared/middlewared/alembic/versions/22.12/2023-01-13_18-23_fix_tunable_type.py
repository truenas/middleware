"""upper-case tun_type column in system_tunable table

Revision ID: c86a02e21e9d
Revises: 5cc601ce9a8e
Create Date: 2023-01-13 18:23:46.735430+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'c86a02e21e9d'
down_revision = '5cc601ce9a8e'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(text('UPDATE system_tunable SET tun_type = "SYSCTL" where tun_type = "sysctl"'))


def downgrade():
    pass
