"""
Fix disk type devices path

Revision ID: b3c5a5321aef
Revises: 2ed09f3b17b7
Create Date: 2022-03-04 13:24:38.186590+00:00

"""
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3c5a5321aef'
down_revision = '2ed09f3b17b7'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    for device in map(dict, conn.execute("SELECT * FROM vm_device WHERE dtype = 'DISK'").fetchall()):
        device["attributes"] = json.loads(device["attributes"])
        if device["attributes"].get("path"):
            device["attributes"]["path"] = device["attributes"]["path"].replace(" ", "+")
            conn.execute("UPDATE vm_device SET attributes = ? WHERE id = ?", (
                json.dumps(device["attributes"]), device["id"]
            ))


def downgrade():
    pass
