"""increase minimum number of NFS servers

Revision ID: 99aef90c4cd6
Revises: cd7569a7b973
Create Date: 2022-02-11 19:54:32.149486+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '99aef90c4cd6'
down_revision = 'cd7569a7b973'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(text("UPDATE services_nfs SET nfs_srv_servers = 16 WHERE nfs_srv_servers = 4"))
