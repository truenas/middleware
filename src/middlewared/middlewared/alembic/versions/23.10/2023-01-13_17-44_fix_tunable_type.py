"""upper-case tun_type column in system_tunable table

Revision ID: d81ede53eb14
Revises: 82ad1e72a7f0
Create Date: 2023-01-13 17:44:37.982722+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'd81ede53eb14'
down_revision = '82ad1e72a7f0'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(text('UPDATE system_tunable SET tun_type = "SYSCTL" where tun_type = "sysctl"'))


def downgrade():
    pass
