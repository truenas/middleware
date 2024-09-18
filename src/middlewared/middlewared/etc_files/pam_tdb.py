from datetime import datetime
from middlewared.utils.user_api_key import (
    UserApiKey,
    PamTdbEntry,
    flush_user_api_keys
)


def convert_keys(username, keys) -> PamTdbEntry:
    user_api_keys = []

    for key in keys:
        if key['expires_at'] is None:
            expiry = 0
        else:
            expiry = int(key['expires_at'].timestamp())

        user_api_keys.append(UserApiKey(
            expiry=expiry,
            dbid=key['id'],
            userhash=key['keyhash']
        ))

    return PamTdbEntry(
        username=username,
        keys=user_api_keys
    )


def render(service, middleware, render_ctx):
    api_keys = render_ctx['api_key.query']
    entries = {}
    pdb_entries = []
    for key in api_keys:
        if key['username'] not in entries:
            entries[key['username']] = [key]
        else:
            entries[key['username']].append(key)

    for user, keys in entries.items():
        entry = convert_keys(user, keys)
        pdb_entries.append(entry)

    flush_user_api_keys(pdb_entries)
