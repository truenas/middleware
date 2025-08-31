"""Add nullable QXL memory fields to VM display devices

Revision ID: f0e0a8aacb5d
Revises: 7767afd88989
Create Date: 2025-08-31 16:20:00.000000+00:00

"""
import json

from alembic import op

from middlewared.plugins.pwenc import encrypt, decrypt


# revision identifiers, used by Alembic.
revision = 'f0e0a8aacb5d'
down_revision = '7767afd88989'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add nullable vgamem, ram, and vram fields to all DISPLAY devices.
    All fields default to None to use libvirt defaults.
    """
    conn = op.get_bind()

    for device in conn.execute("SELECT * FROM vm_device").fetchall():
        if decrypted := decrypt(device['attributes']):
            attributes = json.loads(decrypted)
        else:
            continue

        if attributes.get('dtype') != 'DISPLAY':
            continue

        # Add the new nullable fields if they don't exist
        modified = False
        for field in ['vgamem', 'ram', 'vram']:
            if field not in attributes:
                attributes[field] = None
                modified = True

        if modified:
            conn.execute(
                "UPDATE vm_device SET attributes = ? WHERE id = ?",
                (encrypt(json.dumps(attributes)), device['id'])
            )


def downgrade():
    pass
