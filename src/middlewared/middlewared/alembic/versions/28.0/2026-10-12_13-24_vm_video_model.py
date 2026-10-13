"""VM video model

Revision ID: c5c3dfe24ea8
Revises: 09cc64d01836
Create Date: 2026-10-12 13:24:00.000000+00:00

"""

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

from middlewared.utils.pwenc import decrypt

# revision identifiers, used by Alembic.
revision = "c5c3dfe24ea8"
down_revision = "09cc64d01836"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("vm_vm", schema=None) as batch_op:
        batch_op.add_column(sa.Column("video_model", sa.String(length=50), nullable=False, server_default="VGA"))

    conn = op.get_bind()
    for row in conn.execute(text("SELECT vm_id, attributes FROM vm_device")).mappings().all():
        if (decrypted := decrypt(row["attributes"])) and json.loads(decrypted).get("dtype") == "DISPLAY":
            conn.execute(text("UPDATE vm_vm SET video_model = 'QXL' WHERE id = :id"), {"id": row["vm_id"]})

    conn.execute(text("UPDATE vm_vm SET video_model = 'VIRTIO' WHERE arch_type = 'aarch64'"))


def downgrade():
    pass
