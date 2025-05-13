ADMIN_UID = 950
ADMIN_GID = 950
MIN_AUTO_XID = 3000  # See NAS-117892 - purpose is to avoid collision with apps uids/gids
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

# TRUENAS_IDMAP_MAX + 1, this is also first ID in range allocated for Incus idmaps
CONTAINER_ROOT_UID = 2147000001

SYNTHETIC_CONTAINER_ROOT = {
    'pw_name': 'truenas_container_unpriv_root',
    'pw_uid': CONTAINER_ROOT_UID,
    'pw_gid': 2147000001,
    'pw_gecos': 'Unprivileged root user for containers',
    'pw_dir': '/var/empty',
    'pw_shell': '/usr/sbin/nologin',
    'grouplist': None,
    'sid': None,
    'source': 'LOCAL',
    'local': True
}
