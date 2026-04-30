from middlewared.api.current import ApiKeyEntry
from middlewared.utils.user_api_key import UserApiKey, UserKeyringEntry, flush_user_api_keys


def convert_keys(username: str, keys: list[ApiKeyEntry]) -> UserKeyringEntry:
    user_api_keys = []

    for key in keys:
        if key.expires_at is None:
            expiry = 0
        elif key.revoked:
            # Backstop. We filter these out when we etc.generate, but we don't
            # want to have an avenue to accidentally insert revoked keys.
            continue
        else:
            expiry = int(key.expires_at.timestamp())

        user_api_keys.append(UserApiKey(
            algorithm='SHA512',
            expiry=expiry,
            dbid=key.id,
            username=username,
            salt=key.salt.get_secret_value(),
            iterations=key.iterations,
            server_key=key.server_key.get_secret_value(),
            stored_key=key.stored_key.get_secret_value(),
        ))

    return UserKeyringEntry(
        username=username,
        keys=user_api_keys,
    )


def render(service, middleware, render_ctx):
    entries: dict[str, list[ApiKeyEntry]] = {}
    for key in render_ctx['api_key.query']:
        entries.setdefault(key.username, []).append(key)

    flush_user_api_keys([convert_keys(user, keys) for user, keys in entries.items()])
