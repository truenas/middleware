import os

# CTDB state directory should be a on per-node persistent filesystem
# This is placed on a filesystem that doesn't persist across upgrades
CTDB_DATA_DIR = '/var/lib/ctdb'
CTDB_RUN_DIR = '/var/run/ctdb'

VOLATILE_DB = os.path.join(CTDB_RUN_DIR, 'volatile')
PERSISTENT_DB = os.path.join(CTDB_DATA_DIR, 'persistent')
STATE_DB = os.path.join(CTDB_DATA_DIR, 'state')
RECLOCK_HELPER_SCRIPT = '/usr/local/libexec/ctdb_ha_reclock.py'
