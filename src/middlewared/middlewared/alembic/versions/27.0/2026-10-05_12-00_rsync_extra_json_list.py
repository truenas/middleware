"""Store rsync task additional parameters as a JSON list

Revision ID: 3f0c1d84ab27
Revises: 98358f332844
Create Date: 2026-10-05 12:00:00.000000+00:00

"""
import json
import shlex

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '3f0c1d84ab27'
down_revision = '98358f332844'
branch_labels = None
depends_on = None


def regroup(arg):
    try:
        if len(shlex.split(arg)) == 1:
            return arg
    except ValueError:
        return arg

    # quote_extra_args splits each stored parameter again. The boundary split
    # above already ate the escape that held this one together.
    return shlex.quote(arg)


def parse_legacy(value):
    if not value:
        return []

    try:
        args = shlex.split(value.replace('"', r'"\"').replace("'", r'"\"'))
    except ValueError:
        args = value.split()

    return [regroup(arg) for arg in args]


def upgrade():
    # rsync_extra held the parameter list joined into one string. Every read
    # guessed the boundaries back, and guessed wrong for a parameter with a
    # space in it. A JSON list removes the guess.
    #
    # The column stays TEXT. middlewared.sqlalchemy.JSON is a TypeDecorator
    # over Text, so only the encoding changes.
    #
    # Rewrite every row, including empty ones. JSON.process_result_value
    # returns an empty list for a value it cannot parse. A row left in the old
    # format runs with no additional parameters and reports no error.
    conn = op.get_bind()
    for id_, extra in conn.execute(text('SELECT id, rsync_extra FROM tasks_rsync')).fetchall():
        conn.execute(
            text('UPDATE tasks_rsync SET rsync_extra = :extra WHERE id = :id'),
            {'extra': json.dumps(parse_legacy(extra)), 'id': id_},
        )


def downgrade():
    pass
