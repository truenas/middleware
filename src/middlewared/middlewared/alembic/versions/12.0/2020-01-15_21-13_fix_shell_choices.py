"""Fix user shell choices

Revision ID: f3875acb8d76
Revises: 39a133a04496
Create Date: 2020-01-15 21:13:01.570666+00:00

"""
from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'f3875acb8d76'
down_revision = '39a133a04496'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    conn.execute(text('UPDATE account_bsdUsers SET bsdusr_shell = :new_shell WHERE bsdusr_shell = :old_shell'), {
        'new_shell': '/etc/netcli.sh', 'old_shell': '//etc/netcli.sh'
    })


def downgrade():
    pass
