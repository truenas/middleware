"""Remove legacy freenas sysctls

Revision ID: 85346ccd33c0
Revises: ffcd02f6af9f
Create Date: 2020-05-28 16:29:33.277126+00:00

"""
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '85346ccd33c0'
down_revision = 'ffcd02f6af9f'
branch_labels = None
depends_on = None


TABLE = 'system_tunable'


def remove_freenas_sysctls():
    conn = op.get_bind()
    conn.execute(text(
        f'DELETE FROM {TABLE}'
        ' WHERE tun_var'
        ' LIKE "freenas.%"'
    ))


def upgrade():
    remove_freenas_sysctls()
