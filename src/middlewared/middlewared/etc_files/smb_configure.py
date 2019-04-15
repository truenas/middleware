import logging
import os
import time

from middlewared.utils import run

logger = logging.getLogger(__name__)

NETCMD = "/usr/local/bin/net"
PDBCMD = "/usr/local/bin/pdbedit"
SMBPASSWDCMD = "/usr/local/bin/smbpasswd"
TPCMD = "/usr/local/bin/testparm"

TMP_PRIVATEDIR = "/root/private"
TMP_SMBPASSWD = TMP_PRIVATEDIR + "/tmp_smbpasswd"

"""
    Preparations for starting samba. Needs to happen after smb4.conf is generated.
    Goal is to:
    1) Ensure that all required paths exist and are available.
    2) Maintain local or domain SID
    3) Validate and regenerate passdb.tdb if needed. Since entries are automatically
       added as users are added in the UI, the primary situations where this is needed
       are during HA failover and during boot.
    4) Validate and regenerate local user group mapping.
"""


async def get_smb4conf_parm(parm):
    tp = await run([TPCMD, "-s", f"--parameter-name={parm}"], check=False)
    if tp.returncode != 0:
        logger.debug(f'Command {TPCMD} for parameter {parm} failed with error: {tp.stderr.decode()}')
        return False
    parm_value = tp.stdout.decode().rstrip()

    return parm_value


async def get_config(middleware):
    conf = {}
    conf['systemdataset'] = await middleware.call('systemdataset.config')
    # If the system dataset hasn't finished importing yet, exit quickly so that we don't perform unnecessary db operations.
    if conf['systemdataset']['path'] is None:
        return conf

    conf['cifs'] = await middleware.call('smb.config')
    conf['smb_users'] = await middleware.call('user.query', [
        ['OR', [
            ('smbhash', '~', r'^.+:.+:[X]{32}:.+$'),
            ('smbhash', '~', r'^.+:.+:[A-F0-9]{32}:.+$'),
        ]]
    ])
    conf['role'] = 'file_server'

    parm_to_test = ['privatedir', 'state directory']
    for parm in parm_to_test:
        conf[parm] = await get_smb4conf_parm(parm)

    if not conf['privatedir']:
        conf['privatedir'] = '/var/db/system/samba4/private'
    if not conf['state directory']:
        conf['state directory'] = '/var/db/system/samba4'
    logger.debug(conf)
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


async def get_system_SID(sidtype):
    SID = None
    getSID = await run([NETCMD, "-d", "0", sidtype])
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


async def set_database_SID(middleware, config, SID):
    ret = False
    try:
        await middleware.call('datastore.update', 'services.cifs', config['cifs']['id'], {'cifs_SID': SID})
        ret = True
    except Exception as e:
        logger.debug(f'The following exception occured while setting database SID: ({e})')

    return ret


async def set_system_SID(sidtype, SID):
    if not SID:
        return False

    setSID = await run([NETCMD, "-d", "0", sidtype, SID])
    if setSID.returncode != 0:
        logger.debug(f'Command {sidtype} failed with error: {setSID.stderr.decode()}')
        return False

    return True


async def set_SID(middleware, config):
    get_sid_func = "getlocalsid"
    set_sid_func = "setlocalsid"

    database_SID = config['cifs']['cifs_SID']
    system_SID = await get_system_SID(get_sid_func)

    if database_SID == system_SID:
        return True

    if database_SID:
        if not await set_system_SID(set_sid_func, database_SID):
            logger.debug(f'Unable to set set SID to {database_SID}')
            return False
    else:
        if not system_SID:
            logger.debug('Unable to determine system and database SIDs')
            return False

        if not await set_database_SID(middleware, config, system_SID):
            logger.debug(f'Unable to set database SID to {system_SID}')

"""
    Import local users into Samba's passdb.tdb file. Current behavior is to:
    1) dump the contents of users smbhash to a tempory file,
    2) import it as a legacy smbpasswd file,
    3) remove the temporary file
    4) disable users that are locked or have password disabled in the GUI

    .users_imported sentinel file is no longer used. Instead compare the user
    count in passdb.tdb with the list of smb users the in freenas-v1.db file.
"""


async def count_passdb_users():
    pdb_list = await run([PDBCMD, '-d', '0', '-L'])
    if pdb_list.returncode != 0:
        logger.debug('pdbedit -L command failed. Could not obtain count of users in passdb.tdb')
        return 0

    usercount = len(pdb_list.stdout.decode().splitlines())
    return usercount


async def write_legacy_smbpasswd(middleware, conf):
    if not os.path.exists(TMP_PRIVATEDIR):
        os.mkdir(TMP_PRIVATEDIR, 0o700)

    with open(TMP_SMBPASSWD, "w") as f:
        for user in conf['smb_users']:
            f.write(user['smbhash'] + '\n')

    return True


async def disable_passdb_users(smb_users):
    for user in smb_users:
        if user['locked'] or user['password_disabled']:
            flags = '-d'
        else:
            flags = '-e'

        set_pdb_flags = await run([SMBPASSWDCMD, flags, user["username"]], check=False)
        if set_pdb_flags.returncode != 0:
            logger.debug(f'failed to set flags {flags} for user {user["username"]} in passdb.tdb with error: {set_pdb_flags.stderr.decode()}')
            return False

    return True


async def import_local_users(middleware, conf):
    passdb_file = f"{conf['privatedir']}/passdb.tdb"
    passdb_usercount = await count_passdb_users()
    if len(conf['smb_users']) == passdb_usercount:
        logger.debug('User count in config file and passdb is identical. Bypassing import')
        return True

    ret = await write_legacy_smbpasswd(middleware, conf)

    if os.path.exists(passdb_file):
        logger.debug('Removing out-of-sync passdb.tdb file')
        os.unlink(passdb_file)

    pdb_import = await run([PDBCMD, '-d', '0',
                           '-i', f'smbpasswd:{TMP_SMBPASSWD}'],
                           check=False)

    os.unlink(TMP_SMBPASSWD)
    if pdb_import.returncode != 0:
        logger.debug(f'Import of temp smbpasswd file failed with error: {pdb_import.stderr.decode()}')
        return False

    ret = await disable_passdb_users(conf['smb_users'])
    if not ret:
        return False

"""
    Validate contents of group_mapping.tdb, which maps local Unix groups to Windows group
    SIDs. This file should:
    1) contain no duplicate or inconsistent entries
    2) contain no group names that are identical to usernames

    To do: add validation of SID values in the tdb file.
"""


async def groupmap_add(config, unixgroup, ntgroup):
    gm_add = await run(
        [NETCMD, '-d', '0', 'groupmap', 'add', f'unixgroup={unixgroup}', f'ntgroup={ntgroup}'],
        check=False
    )

    if gm_add.returncode != 0:
        logger.debug(f'Failed to map {unixgroup} to nt group {ntgroup}: {gm_add.stderr.decode()}')
        return False

    return True


async def is_disallowed_group(middleware, conf, groupmap, group):
    disallowed_list = ['USERS', 'ADMINISTRATORS']
    for user in conf['smb_users']:
        disallowed_list.append(user['username'].upper())
    for gm in groupmap:
        disallowed_list.append(gm['unixgroup'].upper())

    if group.upper() in disallowed_list:
        return True

    return False


async def get_groups(middleware):
    _groups = {}
    groups = await middleware.call('group.query', [('builtin', '=', False)])
    for g in groups:
        key = str(g['group'])
        _groups[key] = []
        members = await middleware.call('user.query', [["id", "in", g["users"]]])

        for m in members:
            _groups[key].append(str(m['username']))

    return _groups

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


async def get_domain_sid_from_group_sid(group_sid):
    group_sid_components = group_sid.split("-")

    try:
        rid_component = len(group_sid_components) - 1
        group_sid_components.pop(rid_component)
    except Exception as e:
        logger.debug(f'Failed to calculate domain SID from {group_sid}: ({e})')
        return None

    domain_SID = "-".join(group_sid_components)
    return str(domain_SID)


async def fixsid(middleware, conf, groupmap):
    well_known_SID_prefix = "S-1-5-32"
    db_SID = str(conf['cifs']['cifs_SID'])
    group_SID = None
    groupmap_SID = None
    domain_SID = await get_system_SID("getlocalsid")
    ret = True
    for group in groupmap:
        group_SID = str(group['SID'])
        if well_known_SID_prefix not in group_SID:
            domain_SID = await get_domain_sid_from_group_sid(group_SID)
            if groupmap_SID is not None and groupmap_SID is not domain_SID:
                logger.debug(f"Groupmap table contains more than one unique domain SIDs ({group_SID}) and ({domain_SID})")
                logger.debug('Inconsistent entries in group_mapping.tdb. Situation uncorrectable. Removing corrupted tdb file.')
                os.unlink(f"{conf['state directory']}/group_mapping.tdb")
                return False
            else:
                groupmap_SID = domain_SID

    if db_SID != domain_SID:
        logger.debug(f"Domain SID in group_mapping.tdb ({domain_SID}) is not SID in nas config ({db_SID}). Updating db")
        ret = await set_database_SID(middleware, conf, domain_SID)
        if not ret:
            return ret
        ret = await set_system_SID("setlocalsid", domain_SID)

    return ret


async def validate_group_mappings(middleware, conf):
    groupmap = await middleware.call('notifier.groupmap_list')
    if groupmap:
        sids_fixed = await fixsid(middleware, conf, groupmap)
        if not sids_fixed:
            groupmap = []
    groups = await get_groups(middleware)
    for g in groups:
        if not await is_disallowed_group(middleware, conf, groupmap, g):
            ret = await groupmap_add(conf, g, g)
            if not ret:
                logger.debug(f'Failed to generate group mapping for {g}')


async def render(service, middleware):
    conf = {}
    conf = await get_config(middleware)
    if conf['systemdataset']['path'] is None:
        logger.debug("systemdataset.config returned 'None' as dataset path. Possible zpool import in progress. Exiting configure.")
        return

    ret = await middleware.run_in_thread(setup_samba_dirs, middleware, conf)

    if not ret:
        logger.debug("Failed to configure samba directories")
        return

    await set_SID(middleware, conf)
    if conf['role'] == "file_server":
        await import_local_users(middleware, conf)
        await validate_group_mappings(middleware, conf)

