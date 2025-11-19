# Utilities related to faillock entries in the PAM_TRUENAS keyring
#
# The PAM_TRUENAS keyring has the following structure
#
# (Unlocked user)
# persistent-keyring:uid=0
# └── PAM_TRUENAS
#     └── username
#         ├── API_KEYS
#         │   ├── 0 (reserved for user password SCRAM auth)
#         │   ├── 1 (API key)
#         │   └── 2 (API key)
#         ├── SESSIONS
#         │   └── <uuid> (contains kr_sess_t struct)
#         └── FAILLOG
#             └── <timestamp> (contains ptn_tally_t struct)
#
# (locked user)
# persistent-keyring:uid=0
# └── PAM_TRUENAS
#     └── username
#         ├── API_KEYS
#         │   ├── 0 (reserved for user password SCRAM auth)
#         │   ├── 1 (API key)
#         │   └── 2 (API key)
#         ├── SESSIONS
#         │   └── <uuid> (contains kr_sess_t struct)
#         ├── FAILLOG
#         │   ├── <timestamp> (contains ptn_tally_t struct)
#         │   ├── <timestamp> (contains ptn_tally_t struct)
#         │   └── ...
#         └── tally_lock

import truenas_keyring
import errno


# Since the code-path to check whether local accounts are tally_locked is
# potentially hot we store references to a few different keyring objects here
# to reduce the number of lookups per-user.
PAM_TRUENAS_KEYRING_NAME = "PAM_TRUENAS"
TALLY_LOCK = 'tally_lock'
FAILLOG = 'FAILLOG'
keyrings = {'persistent': None, 'truenas_pam': None}


def __get_persistent_keyring():
    if not keyrings['persistent']:
        keyrings['persistent'] = truenas_keyring.get_persistent_keyring()

    return keyrings['persistent']


def __get_truenas_pam_keyring():
    if keyrings['truenas_pam']:
        return keyrings['truenas_pam']

    persistent = __get_persistent_keyring()
    try:
        # The PAM keyring is lazy-initialized by the pam_truenas module
        pam_keyring = persistent.search(
            key_type=truenas_keyring.KeyType.KEYRING,
            description=PAM_TRUENAS_KEYRING_NAME
        )
    except FileNotFoundError:
        return None

    keyrings['truenas_pam'] = pam_keyring
    return pam_keyring


def __get_user_keyring(username):
    if (pam_keyring := __get_truenas_pam_keyring()) is None:
        return None

    try:
        user_keyring = pam_keyring.search(
            key_type=truenas_keyring.KeyType.KEYRING,
            description=username
        )
    except FileNotFoundError:
        return None

    return user_keyring


def __get_lock_key(user_keyring):
    try:
        lock_key = user_keyring.search(
            key_type=truenas_keyring.KeyType.USER,
            description=TALLY_LOCK
        )
    except FileNotFoundError:
        # truenas_pykeyring converts ENOKEY to FileNotFoundError
        return None
    except truenas_keyring.KeyringError as exc:
        if exc.errno == errno.EKEYEXPIRED or exc.errno == errno.EKEYREVOKED:
            # Forcing cpython extension iterate keyring contents forces deletion
            # of expired lock
            user_keyring.list_keyring_contents()
            return None

        raise

    return lock_key


def __get_failure_keyring(user_keyring):
    try:
        faillog_keyring = user_keyring.search(
            key_type=truenas_keyring.KeyType.KEYRING,
            description=FAILLOG
        )
    except FileNotFoundError:
        # truenas_pykeyring converts ENOKEY to FileNotFoundError
        faillog_keyring = None

    return faillog_keyring


def is_tally_locked(username) -> bool:
    """ This function checks for whether the pam_truenas user keyring has a tally_lock key set on it. """
    if (user_keyring := __get_user_keyring(username)) is None:
        # No user keyring / session info. It's not possible for it to be tally locked.
        return False

    lock_key = __get_lock_key(user_keyring)
    return lock_key is not None


def reset_tally(username) -> None:
    """ Reset FAILLOG for the specified username and remove its tally-lock """
    if (user_keyring := __get_user_keyring(username)) is None:
        return

    if (failure_keyring := __get_failure_keyring(username)) is not None:
        # Wipe all failed login attempts from log
        failure_keyring.clear()

    # There is a separate key thats presence indicates the user is
    # tally locked. Remove this as well if it exists.
    if (lock_key := __get_lock_key(user_keyring)) is None:
        return

    # Unlink the locking key from the user keyring.
    user_keyring.unlink_key(lock_key.serial)


def tally_locked_users() -> set[str]:
    """ Create a set of usernames of all users who are currently tally locked. The
    TRUENAS_PAM_KEYRING key descriptions contain the affected user's name. """
    locked_users = set()
    if (pam_keyring := __get_truenas_pam_keyring()) is None:
        return locked_users

    for user_keyring in pam_keyring.iter_keyring_contents():
        try:
            if __get_lock_key(user_keyring):
                locked_users.add(user_keyring.key.description)
        except Exception:
            # This is called in user.query extend context. We can't allow exceptions or logs to be raised here
            # because the code path is really hot.
            pass

    return locked_users
