from sqlalchemy import text

"""
Normalize authenticator attributes

Revision ID: 0e1cd4d5fcf0
Revises: 65964bb7b139
Create Date: 2024-11-05 23:35:45.960915+00:00

"""
import json
from collections import defaultdict

from alembic import op

from middlewared.utils.pwenc import encrypt, decrypt


revision = '0e1cd4d5fcf0'
down_revision = '65964bb7b139'
branch_labels = None
depends_on = None


def remove_authenticator_ref(authenticator_id, cert_ids, conn):
    if not cert_ids:
        return

    for cert in conn.execute(
        f"SELECT * FROM system_certificate WHERE id IN ({','.join(['?'] * len(cert_ids))})", tuple(cert_ids)
    ).fetchall():
        cert = dict(cert)

        try:
            authenticators = json.loads(decrypt(cert['cert_domains_authenticators']) or '{}')
        except json.decoder.JSONDecodeError:
            # Shouldn't happen, but just being safe
            continue

        # Filter out the authenticator reference
        updated_authenticators = {
            domain: aid for domain, aid in authenticators.items() if aid != authenticator_id
        }

        # Only update if a change was made
        if updated_authenticators != authenticators:
            conn.execute(
                "UPDATE system_certificate SET cert_domains_authenticators = :auths WHERE id = :id",
                {'auths': encrypt(json.dumps(updated_authenticators)), 'id': cert['id']}
            )


def upgrade():
    conn = op.get_bind()
    authenticator_configs = [
        dict(config) for config in conn.execute(text("SELECT * FROM system_acmednsauthenticator")).fetchall()
    ]
    authenticator_mapping = defaultdict(list)
    encrypted_domains_certs = []
    for cert in conn.execute(text("SELECT * FROM system_certificate")).fetchall():
        cert = dict(cert)
        try:
            value = decrypt(cert['cert_domains_authenticators']) if cert['cert_domains_authenticators'] else '{}'
            if value is None:
                encrypted_domains_certs.append(cert['id'])
                continue

            authenticators = json.loads(value)
        except json.JSONDecodeError:
            continue

        for value in authenticators.values():
            authenticator_mapping[value].append(cert['id'])

    for authenticator_config in authenticator_configs:
        authenticator_config = dict(authenticator_config)
        try:
            attributes = json.loads(decrypt(authenticator_config['attributes']))
        except json.JSONDecodeError:
            remove_authenticator_ref(
                authenticator_config['id'], authenticator_mapping[authenticator_config['id']], conn
            )
            conn.execute("DELETE FROM system_acmednsauthenticator WHERE id = :id", {'id': authenticator_config['id']})
        else:
            attributes['authenticator'] = authenticator_config['authenticator']
            conn.execute(
                "UPDATE system_acmednsauthenticator SET attributes = ? WHERE id = ?",
                (encrypt(json.dumps(attributes)), authenticator_config['id'])
            )

    # For certs where we were not able to read domains mappings, we will now unset those as they are not usable
    # anymore
    if encrypted_domains_certs:
        placeholders = ', '.join(map(str, encrypted_domains_certs))
        conn.execute(
            f"UPDATE system_certificate SET cert_domains_authenticators = NULL WHERE id IN ({placeholders})"
        )

    with op.batch_alter_table('system_acmednsauthenticator', schema=None) as batch_op:
        batch_op.drop_column('authenticator')


def downgrade():
    pass
