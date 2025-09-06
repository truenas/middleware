from sqlalchemy import text

"""Copy of revision 0e5949153c20 in 23.10

Revision ID: 249b95f63f76
Revises: ec62dbbeb7aa
Create Date: 2025-04-29 16:48:45.824930+00:00

"""
import json

from alembic import op

from middlewared.utils.pwenc import encrypt, decrypt


# revision identifiers, used by Alembic.
revision = '249b95f63f76'
down_revision = 'ec62dbbeb7aa'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    for c in [r._asdict() for r in conn.execute(text("SELECT * FROM system_keychaincredential WHERE type = 'SSH_CREDENTIALS'")).fetchall()]:
        if attributes := decrypt(c["attributes"]):
            attributes = json.loads(attributes)
            attributes.pop("cipher", None)
            conn.execute(text("UPDATE system_keychaincredential SET attributes = :attributes WHERE id = :id"), {
                "attributes": encrypt(json.dumps(attributes)), "id": c["id"]
            })
