import enum
import os

from middlewared.schema import Bool, returns
from middlewared.service import (Service, accepts,
                                 private, no_authz_required)
from middlewared.service_exception import CallError
from middlewared.utils.path import CLUSTER_PATH_PREFIX


class FuseConfig(enum.Enum):
    """
    Various configuration settings used for FUSE mounting
    the gluster volumes locally.
    """
    FUSE_PATH_BASE = '/cluster'
    FUSE_PATH_SUBST = CLUSTER_PATH_PREFIX


class CTDBConfig(enum.Enum):
    """
    Various configuration settings used to configure ctdb.
    """

    # locks used by the create/delete/mount/umount methods
    BASE_LOCK = 'ctdb_'
    MOUNT_UMOUNT_LOCK = BASE_LOCK + 'mount_or_umount_lock'
    CRE_OR_DEL_LOCK = BASE_LOCK + 'create_or_delete_lock'
    PRI_LOCK = BASE_LOCK + 'private_ip_lock'
    PUB_LOCK = BASE_LOCK + 'public_ip_lock'

    # local nodes ctdb related config
    SMB_BASE = '/var/db/system/samba4'
    PER_DB_DIR = os.path.join(SMB_BASE, 'ctdb_persistent')
    STA_DB_DIR = os.path.join(SMB_BASE, 'ctdb_state')

    # local nodes volatile ctdb db directory
    # (keep this on tmpfs for drastic performance improvements)
    VOL_DB_DIR = '/var/run/ctdb/volatile'

    # name of the recovery file used by ctdb cluster nodes
    REC_FILE = '.CTDB-lockfile'

    # name of the file that ctdb uses for the "private" ips of the
    # nodes in the cluster
    PRIVATE_IP_FILE = 'nodes'

    # name of the file that ctdb uses for the "public" ips of the
    # nodes in the cluster
    PUBLIC_IP_FILE = 'public_addresses'

    # name of the file that ctdb uses for the "general" portion
    # of the config
    GENERAL_FILE = 'ctdb.conf'

    # local gluster fuse client mount related config
    LEGACY_CTDB_VOL_NAME = 'ctdb_shared_vol'
    CTDB_VOL_INFO_FILE = '/data/ctdb_vol_info'
    CTDB_STATE_DIR = '.clustered_system'

    CLUSTERED_SERVICES = '.clustered_services'

    # ctdb etc config
    CTDB_ETC = '/etc/ctdb'
    ETC_GEN_FILE = os.path.join(CTDB_ETC, GENERAL_FILE)
    ETC_REC_FILE = os.path.join(CTDB_ETC, REC_FILE)
    ETC_PRI_IP_FILE = os.path.join(CTDB_ETC, PRIVATE_IP_FILE)
    ETC_PUB_IP_FILE = os.path.join(CTDB_ETC, PUBLIC_IP_FILE)
    MAX_CLOCKSKEW = 10

    # ctdb event scripts directories
    CTDB_ETC_EVENT_SCRIPT_DIR = os.path.join(CTDB_ETC, 'events/legacy')
    CTDB_USR_EVENT_SCRIPT_DIR = '/usr/share/ctdb/events/legacy/'

    # used in the ctdb.shared.volume.teardown method
    CTDB_FILES_TO_REMOVE = [
        ETC_GEN_FILE,
        ETC_REC_FILE,
        ETC_PRI_IP_FILE,
        ETC_PUB_IP_FILE,
        CTDB_VOL_INFO_FILE,
    ]

    # used in the ctdb.shared.volume.teardown method
    # ctdb daemon will core dump immediately if someone tears down the cluster
    # and then tries to recreate one without rebooting (the contents of this dir are on tmpfs)
    # ctdb, in this scenario, sees that the files aren't empty and then hits an assert
    CTDB_DIRS_TO_REMOVE = [
        '/var/run/ctdb/',
    ]
