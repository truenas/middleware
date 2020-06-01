import logging
import os
import subprocess
import time

logger = logging.getLogger(__name__)

NETCMD = "/usr/local/bin/net"
PDBCMD = "/usr/local/bin/pdbedit"
SMBPASSWDCMD = "/usr/local/bin/smbpasswd"

TMP_PRIVATEDIR = "/root/private"
TMP_SMBPASSWD = TMP_PRIVATEDIR + "/tmp_smbpasswd"

"""
    Preparations for starting samba. Needs to happen after smb4.conf is generated.
    Goal is to:
    1) Ensure that all required paths exist and are available.
    2) Maintain local or domain SID
    3) Synchronize samba's passdb.tdb with the contents of the freenas-v1.db file.
    4) Validate and regenerate local user group mapping.
"""


def get_config(middleware):
    """
    Set basic configuration
    """
    conf = {}
    conf['systemdataset'] = middleware.call_sync('systemdataset.config')
    if conf['systemdataset']['path'] is None:
        return conf

    conf['cifs'] = middleware.call_sync('smb.config')
    conf['smb_users'] = middleware.call_sync('user.query', [
        ['OR', [
            ('smbhash', '~', r'^.+:.+:[X]{32}:.+$'),
            ('smbhash', '~', r'^.+:.+:[A-F0-9]{32}:.+$'),
        ]]
    ])
    conf['passdb_backend'] = 'tdbsam'
    ldap = middleware.call_sync('ldap.config')
    if ldap['enable'] and ldap['has_samba_schema']:
        conf['passdb_backend'] = 'ldapsam'

    parm_to_test = ['privatedir', 'state directory']
    for parm in parm_to_test:
        conf[parm] = middleware.call_sync('smb.getparm', parm, 'global')

    if not conf['privatedir']:
        conf['privatedir'] = '/var/db/system/samba4/private'
    if not conf['state directory']:
        conf['state directory'] = '/var/db/system/samba4'
    return conf


def hb_command(command, dir_path):
    try:
        command(dir_path)
        return True
    except Exception as e:
        logger.debug(f"Commmand '{command.__name__}' failed on path {dir_path} with ({e})")
        return False


def setup_samba_dirs(middleware, conf):
    statedir = conf['state directory']
    samba_dirs = [
        statedir,
        "/root/samba",
        conf['privatedir'],
        "/var/run/samba",
        "/var/run/samba4",
        "/var/log/samba4"
    ]
    for dir in samba_dirs:
        if not os.path.exists(dir):
            if dir in conf['privatedir']:
                os.mkdir(dir, 0o700)
            else:
                os.mkdir(dir, 0o755)

    if not conf['systemdataset']['is_decrypted']:
        if os.path.islink(statedir):
            os.unlink(statedir)
            os.mkdir(statedir, 0o755)
        return False

    systemdataset_path = conf['systemdataset']['path']

    basename_realpath = os.path.join(systemdataset_path, 'samba4')
    statedir_realpath = os.path.realpath(statedir)

    if os.path.islink(statedir) and not os.path.exists(statedir):
        os.unlink(conf['statedir'])

    if (basename_realpath != statedir_realpath and os.path.exists(statedir)):
        ret = hb_command(os.unlink, statedir)
        if not ret:
            logger.debug("Path still exists. Attemping to rename it")
            olddir = f"{statedir}.{time.strftime('%Y%m%d%H%M%S')}"
            try:
                os.rename(statedir, olddir)
            except Exception as e:
                logger.debug(f"Unable to rename {statedir} to {olddir} ({e})")
                return False

        try:
            logger.debug(f"Attempting to create symlink: {basename_realpath} -> {statedir} ")
            os.symlink(basename_realpath, statedir)
        except Exception as e:
            logger.debug(f"Unable to create symlink: {basename_realpath} -> {statedir} ({e})")
            return False

    if os.path.islink(statedir) and not os.path.exists(statedir_realpath):
        logger.debug(f"statedir detected as link and realpath {statedir_realpath}  does not exist")
        os.unlink(statedir)
        os.mkdir(statedir, 0o755)

    if not os.path.exists(conf['privatedir']):
        logger.debug("privatedir does not exist. Creating it.")
        os.mkdir(conf['privatedir'], 0o700)

    return True


"""
   Code to make ensure that the local / domain SID persists across upgrades, reboots,
   db restores, etc. The SID value is normally randomized, and this can cause
   Samba's group mapping database to become corrupted and users to lose access to
   shares. This situation is most likely to occur in standalone configurations because
   they rely on the group mapping database for access via local groups. Symptoms of this
   are seeing a SID (S-1-5-32-) rather than the group name in File Explorer.
"""


def get_system_SID(sidtype):
    SID = None
    getSID = subprocess.run([NETCMD, "-d", "0", sidtype], check=False, capture_output=True)
    if getSID.returncode != 0:
        logger.debug(f'Command {sidtype} failed with error: {getSID.stderr.decode()}')
        return None

    parts = getSID.stdout.split()

    try:
        SID = parts[5].decode()
    except Exception as e:
        logger.debug(f'The following exception occured while executing {sidtype}: ({e})')
        SID = None

    return SID


def set_database_SID(middleware, config, SID):
    ret = False
    try:
        middleware.call_sync('datastore.update', 'services.cifs', config['cifs']['id'], {'cifs_SID': SID})
        ret = True
    except Exception as e:
        logger.debug(f'The following exception occured while setting database SID: ({e})')

    return ret


def set_system_SID(sidtype, SID):
    if not SID:
        return False

    setSID = subprocess.run([NETCMD, "-d", "0", sidtype, SID], check=False, capture_output=True)
    if setSID.returncode != 0:
        logger.debug(f'Command {sidtype} failed with error: {setSID.stderr.decode()}')
        return False

    return True


def set_SID(middleware, config):
    get_sid_func = "getlocalsid"
    set_sid_func = "setlocalsid"

    database_SID = config['cifs']['cifs_SID']
    system_SID = get_system_SID(get_sid_func)

    if database_SID == system_SID:
        return True

    if database_SID:
        if not set_system_SID(set_sid_func, database_SID):
            logger.debug(f'Unable to set set SID to {database_SID}')
            return False
    else:
        if not system_SID:
            logger.debug('Unable to determine system and database SIDs')
            return False

        if not set_database_SID(middleware, config, system_SID):
            logger.debug(f'Unable to set database SID to {system_SID}')


"""
    The Windows Security Identifier (SID) is a unique value of variable length.
    Example: S-1-5-21-3623811015-3361044348-30300820-1013
    In the context of Samba group mappings, the group SID can be broken up as follows:
    S       1                     5                   [subauthorities]     [Relative Identifier (RID)]
       SID REVISION           AUTHORITY            (uniquely identifies   (uniquely identifies the object
          LEVEL          (SECURITY_NT_AUTHORITY)   the domain/comptuer)    within context of the domain/computer)

    Samba internally sets up a local machine SID that can be viewed via "net getlocalsid". User and
    Group SIDs are generated by appending a RID value to the local machine SID. There are some situations
    where we may lose the local machine SID value (older versions of FreeNAS had bugs). This results in a new
    local machine SID being generated and the SID values in the group_mapping.tdb file getting out of sync. In
    this case, we will make best effort to fix the issue (up to deleting the group_mapping.tdb file and regenerating
    it).
"""


def get_domain_sid_from_group_sid(group_sid):
    group_sid_components = group_sid.split("-")

    try:
        rid_component = len(group_sid_components) - 1
        group_sid_components.pop(rid_component)
    except Exception as e:
        logger.debug(f'Failed to calculate domain SID from {group_sid}: ({e})')
        return None

    domain_SID = "-".join(group_sid_components)
    return str(domain_SID)


def fixsid(middleware, conf, groupmap):
    well_known_SID_prefix = "S-1-5-32"
    db_SID = str(conf['cifs']['cifs_SID'])
    group_SID = None
    groupmap_SID = None
    domain_SID = get_system_SID("getlocalsid")
    ret = True
    for group in groupmap:
        group_SID = str(group['SID'])
        if well_known_SID_prefix not in group_SID:
            domain_SID = get_domain_sid_from_group_sid(group_SID)
            if groupmap_SID is not None and groupmap_SID != domain_SID:
                logger.debug(f"Groupmap table contains more than one unique domain SIDs ({groupmap_SID}) and ({domain_SID})")
                logger.debug('Inconsistent entries in group_mapping.tdb. Situation uncorrectable. Removing corrupted tdb file.')
                os.unlink(f"{conf['state directory']}/group_mapping.tdb")
                return False
            else:
                groupmap_SID = domain_SID

    if db_SID != domain_SID:
        logger.debug(f"Domain SID in group_mapping.tdb ({domain_SID}) is not SID in nas config ({db_SID}). Updating db")
        ret = set_database_SID(middleware, conf, domain_SID)
        if not ret:
            return ret
        ret = set_system_SID("setlocalsid", domain_SID)

    return ret


def validate_group_mappings(middleware, conf):
    users = {}
    users.update({x['username']: x for x in conf["smb_users"]})
    groupmap = middleware.call_sync('smb.groupmap_list')
    if groupmap:
        sids_fixed = fixsid(middleware, conf, groupmap.values())
        if not sids_fixed:
            groupmap = {}

    groups = [g["group"] for g in middleware.call_sync("group.query", [("builtin", "=", False)])]
    for g in groups:
        if users.get(g):
            continue

        if not groupmap.get(g):
            middleware.call_sync('smb.groupmap_add', g)


def render(service, middleware):
    conf = {}
    conf = get_config(middleware)
    if conf['systemdataset']['path'] is None:
        logger.debug("systemdataset.config returned 'None' as dataset path. Possible zpool import in progress. Exiting configure.")
        return

    ret = setup_samba_dirs(middleware, conf)

    if not ret:
        logger.debug("Failed to configure samba directories")
        return

    set_SID(middleware, conf)
    """
    If LDAP is enabled with samba schema, then remote LDAP server provides SAM and group mapping.
    Trying to initialize the passdb backend here will fail.
    """
    if conf['passdb_backend'] == "tdbsam":
        middleware.call_sync('smb.synchronize_passdb')
        validate_group_mappings(middleware, conf)
        middleware.call_sync('smb.check_rid_conflict')
        middleware.call_sync('admonitor.start')
