import truenas_api_key.keyring as api_keyring
from dataclasses import dataclass
from truenas_api_key.constants import UserApiKey
from middlewared.utils.pwenc import encrypt


@dataclass(frozen=True)
class UserKeyringEntry:
    keys: list[UserApiKey]
    username: str


def flush_user_api_keys(api_key_entries: list[UserKeyringEntry]) -> None:
    """
    Insert the list of API keys into the pam keyring.

    Persistent Keyring (for UID 0)
    └── PAM_TRUENAS
        ├── username_1/
        │   ├── API_KEYS/
        │   │   ├── API Key (dbid: 123)
        │   │   ├── API Key (dbid: 124)
        │   │   └── ...
        │   ├── SESSIONS/
        │   └── FAILLOG/
        ├── username_2/
        │   ├── API_KEYS/
        │   │   ├── API Key (dbid: 456)
        │   │   ├── API Key (dbid: 457)
        │   │   └── ...
        │   ├── SESSIONS/
        │   └── FAILLOG/
        └── ...
    """
    for entry in api_key_entries:
        api_keyring.commit_user_entry(entry.username, entry.keys, encrypt)

    usernames = {entry.username for entry in api_key_entries}

    # remove API keys for any user that isn't in our users list
    pam_keyring = api_keyring.get_pam_keyring()
    for entry in pam_keyring.iter_keyring_contents(unlink_expired=True, unlink_revoked=True):
        if entry.key.key_type != 'keyring':
            continue

        # the description for entries in pam keyring is the username
        if entry.key.description in usernames:
            continue

        api_keyring.clear_user_keyring(entry.key.description)
