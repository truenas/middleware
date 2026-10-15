"""VM video model

Revision ID: e2a7c4f19b63
Revises: 3f0c1d84ab27
Create Date: 2026-10-15 12:00:00.000000+00:00

"""

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

from middlewared.utils.pwenc import decrypt

# revision identifiers, used by Alembic.
revision = "e2a7c4f19b63"
down_revision = "3f0c1d84ab27"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    # Databases that already ran the 28.0 revision c5c3dfe24ea8 have the column and possibly user-chosen values.
    if "video_model" in {column["name"] for column in sa.inspect(conn).get_columns("vm_vm")}:
        return

    with op.batch_alter_table("vm_vm", schema=None) as batch_op:
        batch_op.add_column(sa.Column("video_model", sa.String(length=50), nullable=False, server_default="VGA"))

    for row in conn.execute(text("SELECT vm_id, attributes FROM vm_device")).mappings().all():
        if (decrypted := decrypt(row["attributes"])) and json.loads(decrypted).get("dtype") == "DISPLAY":
            conn.execute(text("UPDATE vm_vm SET video_model = 'QXL' WHERE id = :id"), {"id": row["vm_id"]})

    conn.execute(text("UPDATE vm_vm SET video_model = 'VIRTIO' WHERE arch_type = 'aarch64'"))


def downgrade():
    pass
