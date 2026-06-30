from cryptography import x509
from cryptography.hazmat.primitives import serialization
import truenas_keyring
import truenas_pyscram

from middlewared.utils.user_api_key import UserApiKey, UserKeyringEntry, flush_user_api_keys

# Must match pam_truenas's PAM_SCRAM_BINDING_NAME. pam_truenas reads this as a
# `user`-type key directly from the uid=0 persistent keyring (a sibling of the
# PAM_TRUENAS keyring) and uses its payload as the RFC 5929 tls-server-end-point
# value to verify SCRAM-PLUS channel binding.
SERVER_BINDING_DESCRIPTION = 'TRUENAS_SCRAM_PLUS_SERVER_BINDING'


def convert_keys(username, keys) -> UserKeyringEntry:
    user_api_keys = []

    for key in keys:
        if key['expires_at'] is None:
            expiry = 0
        elif key['revoked']:
            # Backstop. We filter these out when we etc.generate, but we don't
            # want to have an avenue to accidentally insert revoked keys.
            continue
        else:
            expiry = int(key['expires_at'].timestamp())

        user_api_keys.append(UserApiKey(
            algorithm='SHA512',
            expiry=expiry,
            dbid=key['id'],
            username=username,
            salt=key['salt'],
            iterations=key['iterations'],
            server_key=key['server_key'],
            stored_key=key['stored_key']
        ))

    return UserKeyringEntry(
        username=username,
        keys=user_api_keys
    )


def _resolve_ui_cert_pem(middleware) -> str | None:
    general = middleware.call_sync('system.general.config')
    if not general['ui_certificate']:
        return None

    # Use query instead of get_instance so a missing/odd cert can't raise and break
    # pam rendering (mirrors the nginx template).
    cert_list = middleware.call_sync(
        'certificate.query', [['id', '=', general['ui_certificate']]]
    )
    if not cert_list:
        return None

    return cert_list[0]['certificate']


def _compute_server_binding(pem: str) -> bytes:
    der = x509.load_pem_x509_certificate(pem.encode()).public_bytes(serialization.Encoding.DER)
    return bytes(truenas_pyscram.compute_tls_server_end_point(der))


def _server_binding_key(persistent):
    try:
        return persistent.search(
            key_type=truenas_keyring.KeyType.USER, description=SERVER_BINDING_DESCRIPTION
        )
    except FileNotFoundError:
        return None


def _store_server_binding(binding: bytes) -> bool:
    """ Idempotently publish the binding. Returns True if the keyring changed.

    add_key(2) updates the `user` key in place when one with this description already
    exists in the keyring, so a rotated cert just overwrites the payload atomically. """
    persistent = truenas_keyring.get_persistent_keyring()
    existing = _server_binding_key(persistent)
    if existing is not None and existing.read_data() == binding:
        return False

    truenas_keyring.add_key(
        key_type=truenas_keyring.KeyType.USER,
        description=SERVER_BINDING_DESCRIPTION,
        data=binding,
        target_keyring=persistent.key.serial,
    )
    return True


def _remove_server_binding() -> bool:
    """ Remove the binding if present. Returns True if a key was removed. """
    persistent = truenas_keyring.get_persistent_keyring()
    existing = _server_binding_key(persistent)
    if existing is None:
        return False

    persistent.unlink_key(existing.serial)
    return True


def _flush_server_channel_binding(middleware) -> None:
    """ Publish/refresh (or clear) the SCRAM-PLUS server channel binding so pam_truenas
    can verify channel-bound SCRAM logins. Best-effort: a failure here must not break
    pam rendering. """
    try:
        pem = _resolve_ui_cert_pem(middleware)
        if pem is None:
            if _remove_server_binding():
                middleware.logger.warning(
                    'Removed SCRAM-PLUS channel binding: no active UI certificate'
                )
        elif _store_server_binding(_compute_server_binding(pem)):
            middleware.logger.info('Published SCRAM-PLUS tls-server-end-point channel binding')
    except Exception:
        middleware.logger.error(
            'Failed to refresh SCRAM-PLUS tls-server-end-point channel binding', exc_info=True
        )


def render(service, middleware, render_ctx):
    api_keys = render_ctx['api_key.query']
    entries = {}
    for key in api_keys:
        if key['username'] not in entries:
            entries[key['username']] = [key]
        else:
            entries[key['username']].append(key)

    flush_user_api_keys([convert_keys(user, keys) for user, keys in entries.items()])

    _flush_server_channel_binding(middleware)
