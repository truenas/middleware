"""Strip leading and trailing whitespace from API key names

Revision ID: ac2610fcbe38
Revises: b4ada61420a1
Create Date: 2026-11-16 12:00:00.000000+00:00

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "ac2610fcbe38"
down_revision = "b4ada61420a1"
branch_labels = None
depends_on = None


def unique_name(id_, name, taken):
    if not name:
        name = f"api-key-{id_}"

    candidate = name
    suffix = 0
    while candidate in taken:
        suffix += 1
        candidate = f"{name[:199 - len(str(suffix))]}-{suffix}"

    return candidate


def upgrade():
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, name FROM account_api_key ORDER BY id")).fetchall()
    taken = {name for id_, name in rows}

    for id_, name in rows:
        stripped = name.strip()
        if stripped == name:
            continue

        taken.discard(name)
        # `api_key.update` rejects any change to a key that shares its name with another key
        new_name = unique_name(id_, stripped, taken)
        taken.add(new_name)

        conn.execute(
            sa.text("UPDATE account_api_key SET name = :name WHERE id = :id"),
            {"name": new_name, "id": id_},
        )


def downgrade():
    pass
