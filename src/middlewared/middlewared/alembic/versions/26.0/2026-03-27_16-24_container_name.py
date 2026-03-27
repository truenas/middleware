"""
Sanitize container names to conform to RFC 1123 hostname rules

Revision ID: c7d8e9f0a1b2
Revises: cb58cc72a1d5
Create Date: 2026-03-27 16:24:00.000000+00:00

"""
import re

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'c7d8e9f0a1b2'
down_revision = 'cb58cc72a1d5'
branch_labels = None
depends_on = None

# Local copy of the container name regex — migrations must be self-contained.
# RFC 1123 hostname: labels are 1-63 alphanumeric/hyphen chars starting and
# ending with alphanumeric, separated by dots, total 1-253 chars.
# IPv4 dotted-decimal (e.g. 10.2.0.52) is rejected.
_RE_NAME = re.compile(
    r"\A"
    r"(?!\d{1,3}(?:\.\d{1,3}){3}\Z)"
    r"(?=.{1,253}\Z)"
    r"(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)*"
    r"[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?"
    r"\Z",
    re.IGNORECASE,
)


def _sanitize_name(name, container_id, existing_names):
    """Sanitize a container name to conform to the new RFC 1123 regex.

    Existing names were created under the old regex ``^[a-zA-Z_0-9\\-]+$``
    so they can only contain alphanumeric, underscores, and hyphens (no dots).

    Steps:
      1. Replace underscores with hyphens
      2. Strip leading/trailing hyphens
      3. Collapse consecutive hyphens
      4. Truncate to 63 chars (single label), strip trailing hyphen
      5. Fallback to ``container-{id}`` if empty or still invalid
      6. Resolve collisions by appending ``-N`` suffix
    """
    new_name = name.replace('_', '-')
    new_name = new_name.strip('-')
    new_name = re.sub(r'-{2,}', '-', new_name)

    if len(new_name) > 63:
        new_name = new_name[:63].rstrip('-')

    if not new_name or not _RE_NAME.match(new_name):
        new_name = f'container-{container_id}'

    final_name = new_name
    if final_name in existing_names:
        suffix = 1
        while True:
            candidate = f'{new_name}-{suffix}'
            if len(candidate) > 63:
                max_base = 63 - len(f'-{suffix}')
                candidate = f'{new_name[:max_base].rstrip("-")}-{suffix}'
            if candidate not in existing_names:
                final_name = candidate
                break
            suffix += 1

    return final_name


def upgrade():
    conn = op.get_bind()

    # Sanitize container names that do not conform to RFC 1123 hostname rules.
    # The validation was tightened to enforce proper hostname labels: each label
    # must start and end with alphanumeric, contain only alphanumeric/hyphens,
    # and be 1-63 chars.  Previously underscores and leading/trailing hyphens
    # were allowed.
    #
    # The dataset column is intentionally not updated here — the ZFS dataset
    # rename and corresponding dataset column update are handled by the
    # filesystem migration (0019_container_name.py).
    rows = conn.execute(text('SELECT id, name FROM container_container')).mappings().all()
    existing_names = {row['name'] for row in rows}

    for row in rows:
        name = row['name']
        if _RE_NAME.match(name):
            continue

        final_name = _sanitize_name(name, row['id'], existing_names)

        existing_names.discard(name)
        existing_names.add(final_name)

        conn.execute(
            text('UPDATE container_container SET name = :name WHERE id = :id'),
            {'name': final_name, 'id': row['id']},
        )


def downgrade():
    pass
