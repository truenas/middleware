import os
import enum


class FuseConfig(enum.Enum):
    """
    Various configuration settings used for FUSE mounting
    the gluster volumes locally.
    """
    FUSE_PATH_BASE = '/cluster'


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
    LOCAL_MOUNT_BASE = FuseConfig.FUSE_PATH_BASE.value
    CTDB_VOL_NAME = 'ctdb_shared_vol'
    CTDB_LOCAL_MOUNT = os.path.join(LOCAL_MOUNT_BASE, CTDB_VOL_NAME)
    GM_RECOVERY_FILE = os.path.join(CTDB_LOCAL_MOUNT, REC_FILE)
    GM_PRI_IP_FILE = os.path.join(CTDB_LOCAL_MOUNT, PRIVATE_IP_FILE)
    GM_PUB_IP_FILE = os.path.join(CTDB_LOCAL_MOUNT, PUBLIC_IP_FILE)

    # ctdb etc config
    CTDB_ETC = '/etc/ctdb'
    ETC_GEN_FILE = os.path.join(CTDB_ETC, GENERAL_FILE)
    ETC_REC_FILE = os.path.join(CTDB_ETC, REC_FILE)
    ETC_PRI_IP_FILE = os.path.join(CTDB_ETC, PRIVATE_IP_FILE)
    ETC_PUB_IP_FILE = os.path.join(CTDB_ETC, PUBLIC_IP_FILE)
