"""Add `endpoint` field to system_cloudcredentials.attributes for type STORJ_IX.

Revision ID: 30c9619bf9e7
Revises: 08febd74cdf9
Create Date: 2025-05-07 20:47:46.751451+00:00

"""
import json

from alembic import op

from middlewared.plugins.pwenc import encrypt, decrypt


# revision identifiers, used by Alembic.
revision = '30c9619bf9e7'
down_revision = '08febd74cdf9'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    for entry in map(dict, conn.execute("SELECT id, attributes FROM system_cloudcredentials WHERE provider = 'STORJ_IX'").fetchall()):
        if attributes := decrypt(entry["attributes"]):
            attributes = json.loads(attributes)
            attributes.setdefault("endpoint", "https://gateway.storjshare.io/")
            conn.execute("UPDATE system_cloudcredentials SET attributes = ? WHERE id = ?", (
                encrypt(json.dumps(attributes)), entry["id"]
            ))
