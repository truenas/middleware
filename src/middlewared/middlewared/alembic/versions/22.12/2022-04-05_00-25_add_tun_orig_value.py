"""add tunables_orig_value

Revision ID: 1bd044af765d
Revises: 6e73632d6e88
Create Date: 2022-04-05 00:25:56.744546+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '1bd044af765d'
down_revision = '6e73632d6e88'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('system_tunable', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tun_orig_value', sa.String(length=512), server_default='', nullable=False))

    nocase = 'COLLATE NOCASE'
    op.execute(text(f'DELETE FROM system_tunable WHERE tun_type = "loader" {nocase} or tun_type = "rc" {nocase}'))

    conn = op.get_bind()
    for entry in conn.execute(text('SELECT * FROM system_tunable WHERE tun_type = "sysctl" COLLATE NOCASE')).fetchall():
        # It's impossible to (easily) determine the default value of a sysctl tunable because
        # of the order in which the upgrade service runs compared to systemd-sysctl service.
        # We'll simply use the user-provided value to normalize the database. There is no
        # change in functionality by doing it this way.
        conn.execute(text('UPDATE system_tunable SET tun_orig_value = :value WHERE id = :id'), {'value': entry['tun_value'], 'id': entry['id']})


def downgrade():
    pass
