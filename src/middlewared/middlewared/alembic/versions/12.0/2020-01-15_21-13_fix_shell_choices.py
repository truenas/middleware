"""Fix user shell choices

Revision ID: a7f13f81a210
Revises: 133f2d9049d2
Create Date: 2020-01-15 21:13:01.570666+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'a7f13f81a210'
down_revision = '133f2d9049d2'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    conn.execute('UPDATE account_bsdUsers SET bsdusr_shell = ? WHERE bsdusr_shell = ?', (
        '/etc/netcli.sh', '//etc/netcli.sh'
    ))


def downgrade():
    pass
