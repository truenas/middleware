"""Store the hosts table as a list instead of one newline-joined string

`gc_hosts` held every entry of the hosts table in one text column, joined by a line feed, so the
reader had to split it. A value pasted with CRLF left a carriage return at the end of every entry,
and an entry could never be told apart from its own separator. The column becomes a JSON list.

Revision ID: a4c63b1ff6cf
Revises: 6d08137a3def
Create Date: 2026-11-10 11:00:00.000000+00:00

"""
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4c63b1ff6cf'
down_revision = '6d08137a3def'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    rows = connection.execute(sa.text('SELECT id, gc_hosts FROM network_globalconfiguration')).fetchall()
    for id_, stored in rows:
        # A carriage return becomes a separator of its own: the reader split on a line feed alone, so a
        # value pasted with CRLF would otherwise leave one at the end of every entry.
        normalized = (stored or '').replace('\r\n', '\n').replace('\r', '\n')
        entries = [entry.strip() for entry in normalized.split('\n') if entry.strip()]
        connection.execute(
            sa.text('UPDATE network_globalconfiguration SET gc_hosts = :value WHERE id = :id'),
            {'value': json.dumps(entries), 'id': id_},
        )


def downgrade():
    pass
