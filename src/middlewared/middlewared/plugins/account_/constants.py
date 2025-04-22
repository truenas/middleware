from middlewared.utils.nss.pwd import pwd_struct

ADMIN_UID = 950
ADMIN_GID = 950
SKEL_PATH = '/etc/skel/'  # TODO evaluate whether this is still needed

# TrueNAS historically used /nonexistent as the default home directory for new
# users. The nonexistent directory has caused problems when
# 1) an admin chooses to create it from shell
# 2) PAM checks for home directory existence
# And so this default has been deprecated in favor of using /var/empty
# which is an empty and immutable directory.
LEGACY_DEFAULT_HOME_PATH = '/nonexistent'
DEFAULT_HOME_PATH = '/var/empty'
DEFAULT_HOME_PATHS = (DEFAULT_HOME_PATH, LEGACY_DEFAULT_HOME_PATH)
MIDDLEWARE_PAM_SERVICE = '/etc/pam.d/middleware'
MIDDLEWARE_PAM_API_KEY_SERVICE = '/etc/pam.d/middleware-api-key'

USERNS_IDMAP_DIRECT = -1
USERNS_IDMAP_NONE = 0

# Apart from a few exceptions we don't want admins making random
# interactive users members of builtin groups. These groups usually
# have enhanced privileges to the server and group membership can expose
# unexpected security issues.
ALLOWED_BUILTIN_GIDS = {
    14,  # ftp -- required for FTP access
    544,  # builtin_administrators
    545,  # builtin_users
    568,  # apps
    951,  # truenas_readonly_administrators
    952,  # truenas_sharing_administrators
}

SYNTHENTIC_CONTAINER_ROOT = pwd_struct(
    'truenas_container_unpriv_root',
    2147000001,
    2147000001,
    'Unprivileged root user for containers',
    '/var/empty',
    '/usr/sbin/nologin',
    'LOCAL'
)
