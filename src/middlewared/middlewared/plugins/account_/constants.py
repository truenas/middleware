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
