"""
Fix disk type devices path

Revision ID: b3c5a5321aef
Revises: 4e027c93e4d1
Create Date: 2022-03-08 13:24:38.186590+00:00

"""
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'b3c5a5321aef'
down_revision = '4e027c93e4d1'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    for device in map(dict, conn.execute(text("SELECT * FROM vm_device WHERE dtype = 'DISK'")).fetchall()):
        device["attributes"] = json.loads(device["attributes"])
        if device["attributes"].get("path"):
            device["attributes"]["path"] = device["attributes"]["path"].replace(" ", "+")
            conn.execute(text("UPDATE vm_device SET attributes = :attributes WHERE id = :id"), {
                'attributes': json.dumps(device["attributes"]), 'id': device["id"]
            })


def downgrade():
    pass
