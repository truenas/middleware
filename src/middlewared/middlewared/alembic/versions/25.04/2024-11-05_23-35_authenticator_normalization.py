"""
Normalize authenticator attributes

Revision ID: 0e1cd4d5fcf0
Revises: 65964bb7b139
Create Date: 2024-11-05 23:35:45.960915+00:00

"""
import json

from alembic import op

from middlewared.plugins.pwenc import encrypt, decrypt


revision = '0e1cd4d5fcf0'
down_revision = '65964bb7b139'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    for authenticator_config in conn.execute("SELECT * FROM system_acmednsauthenticator").fetchall():
        authenticator_config = dict(authenticator_config)
        attributes = json.loads(decrypt(authenticator_config['attributes']))
        attributes['authenticator'] = authenticator_config['authenticator']
        conn.execute(
            "UPDATE system_acmednsauthenticator SET attributes = ? WHERE id = ?",
            (encrypt(json.dumps(attributes)), authenticator_config['id'])
        )

    with op.batch_alter_table('system_acmednsauthenticator', schema=None) as batch_op:
        batch_op.drop_column('authenticator')


def downgrade():
    pass
