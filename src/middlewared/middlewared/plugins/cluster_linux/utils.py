import os
import enum

from middlewared.plugins.smb import SMBPath


BASE = SMBPath.STATEDIR.platform()
JOB_LOCK = 'ctdb_job_lock'


class CTDBConfig(enum.Enum):

    PRIVATE_IP_FILE = '/etc/ctdb/nodes'
    PUBLIC_IP_FILE = '/etc/ctdb/public_addresses'


class CTDBCluster(enum.Enum):

    """
    Represents the clustered locations
    to store various files used by ctdb.
    It's expected that any file/dir listed
    in this class will be stored on the
    clustered filesystem.
    """

    RECOVERY_FILE = '/cluster/ctdb/.CTDB-lockfile'


class CTDBLocal(enum.Enum):

    """
    Represents the _LOCAL_ directories
    to store various files used by ctdb. These
    do NOT need to be stored on the clusterd
    filesystem.
    """

    # volatile database
    SMB_VOLATILE_DB_DIR = '/var/run/ctdb/volatile/'
    # persistent database
    SMB_PERSISTENT_DB_DIR = os.path.join(BASE, 'ctdb_persistent')
    # state database
    SMB_STATE_DB_DIR = os.path.join(BASE, 'ctdb_state')
