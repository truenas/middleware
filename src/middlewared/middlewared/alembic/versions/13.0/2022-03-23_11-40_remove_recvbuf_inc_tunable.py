from sqlalchemy import text

"""remove net.inet.tcp.recvbuf_inc (was removed in 13)

Revision ID: 88bfe11b5be5
Revises: 99aef90c4cd6
Create Date: 2022-03-23 11:40:32.149486+00:00

"""
from alembic import op


revision = '88bfe11b5be5'
down_revision = '99aef90c4cd6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(text('DELETE FROM system_tunable WHERE tun_var = "net.inet.tcp.recvbuf_in"'))
