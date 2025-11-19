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

from truenas_pam_faillog import PamFaillog


try:
    pam_log = PamFaillog()
except Exception:
    # This is handling for our github runner. In a containerized environment
    # we can't access the kernel keyring so faillog will be unavailable.
    pam_log = None


def is_tally_locked(username) -> bool:
    """ This function checks for whether the pam_truenas user keyring has a tally_lock key set on it. """
    return pam_log.is_tally_locked(username)


def reset_tally(username) -> None:
    """ Reset FAILLOG for the specified username and remove its tally-lock """
    return pam_log.reset_tally(username)


def tally_locked_users() -> set[str]:
    """ Create a set of usernames of all users who are currently tally locked. The
    TRUENAS_PAM_KEYRING key descriptions contain the affected user's name. """
    return pam_log.tally_locked_users()
