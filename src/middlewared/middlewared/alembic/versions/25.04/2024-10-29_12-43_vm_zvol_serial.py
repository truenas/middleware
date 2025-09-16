"""
Add serial to VM zvol disk devices

Revision ID: a4ce4939b908
Revises: dd6e581235b2
Create Date: 2024-10-29 12:43:45.960915+00:00

"""
import json
from secrets import choice
from string import ascii_letters, digits, punctuation

from alembic import op

from middlewared.utils.pwenc import encrypt, decrypt


revision = 'a4ce4939b908'
down_revision = 'dd6e581235b2'
branch_labels = None
depends_on = None


def generate_string(string_size=8, punctuation_chars=False, extra_chars=None):
    """
    Generate a cryptographically secure random string of size `string_size`.
    If `punctuation_chars` is True, then punctuation characters will be added to the string.
    Otherwise, only ASCII (upper and lower) and digits (0-9) are used to generate the string.
    """
    initial_string = ascii_letters + digits
    if punctuation_chars:
        initial_string += punctuation
    if extra_chars is not None and isinstance(extra_chars, str):
        initial_string += extra_chars

    # remove any duplicates since extra_chars is user-provided
    initial_string = ''.join(set(initial_string))
    return ''.join(choice(initial_string) for i in range(string_size))


def upgrade():
    conn = op.get_bind()
    for device in conn.execute("SELECT * FROM vm_device WHERE dtype IN ('DISK', 'RAW')").fetchall():
        attributes = json.loads(decrypt(device['attributes']))
        attributes['serial'] = generate_string(string_size=8)
        conn.execute("UPDATE vm_device SET attributes = ? WHERE id = ?", (encrypt(json.dumps(attributes)), device['id']))


def downgrade():
    pass
