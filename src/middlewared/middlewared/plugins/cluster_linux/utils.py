import os
import enum


class CTDBConfig(enum.Enum):

    """
    Various configuration settings used to configure ctdb.
    """

    # create/delete or mount/umount requests can
    # take awhile and obviously don't need to be
    # run at the same time
    BASE_LOCK = 'ctdb_'
    MOUNT_UMOUNT_LOCK = BASE_LOCK + 'mount_or_umount_lock'
    CRE_OR_DEL_LOCK = BASE_LOCK + 'ctdb_create_or_delete_lock'

    # ctdb smb related config
    VOL_DB_DIR = '/var/run/ctdb/volatile'
    SMB_BASE = '/var/db/system/samba4'
    PER_DB_DIR = os.path.join(SMB_BASE, 'ctdb_persistent')
    STA_DB_DIR = os.path.join(SMB_BASE, 'ctdb_state')

    # local gluster fuse client mount related config
    LOCAL_MOUNT_BASE = '/cluster'
    CTDB_VOL_NAME = 'ctdb_shared_vol'
    CTDB_LOCAL_MOUNT = os.path.join(LOCAL_MOUNT_BASE, CTDB_VOL_NAME)
    GM_RECOVERY_FILE = os.path.join(CTDB_LOCAL_MOUNT, '.CTDB-lockfile')
    GM_PRI_IP_FILE = os.path.join(CTDB_LOCAL_MOUNT, 'nodes')
    GM_PUB_IP_FILE = os.path.join(CTDB_LOCAL_MOUNT, 'public_addresses')

    # ctdb etc config
    CTDB_ETC = '/etc/ctdb'
    ETC_PRI_IP_FILE = os.path.join(CTDB_ETC, 'nodes')
    ETC_PUB_IP_FILE = os.path.join(CTDB_ETC, 'public_addresses')
