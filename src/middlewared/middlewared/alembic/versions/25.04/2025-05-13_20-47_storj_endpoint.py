from sqlalchemy import text

"""Add `endpoint` field to system_cloudcredentials.attributes for type STORJ_IX.

Revision ID: 30c9619bf9e7
Revises: 7c663f5ec8a1
Create Date: 2025-05-07 20:47:46.751451+00:00

"""
import json

from alembic import op

from middlewared.utils.pwenc import encrypt, decrypt


# revision identifiers, used by Alembic.
revision = '30c9619bf9e7'
down_revision = '7c663f5ec8a1'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    for entry in conn.execute(text("SELECT id, attributes FROM system_cloudcredentials WHERE provider = 'STORJ_IX'")).mappings().all():
        if attributes := decrypt(entry["attributes"]):
            attributes = json.loads(attributes)
            attributes.setdefault("endpoint", "https://gateway.storjshare.io/")
            conn.execute(text("UPDATE system_cloudcredentials SET attributes = :attributes WHERE id = :id"), {
                "attributes": encrypt(json.dumps(attributes)), "id": entry["id"]
            })
