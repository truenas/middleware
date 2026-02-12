from middlewared.utils.user_api_key import (
    UserApiKey,
    UserKeyringEntry,
    flush_user_api_keys
)


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


def render(service, middleware, render_ctx):
    api_keys = render_ctx['api_key.query']
    entries = {}
    keyring_entries = []
    for key in api_keys:
        if key['username'] not in entries:
            entries[key['username']] = [key]
        else:
            entries[key['username']].append(key)

    for user, keys in entries.items():
        entry = convert_keys(user, keys)
        keyring_entries.append(entry)

    flush_user_api_keys(keyring_entries)
