import os
import enum

from logging import getLogger
from middlewared.utils import filter_list
from middlewared.utils.directoryservices.constants import DSType
from middlewared.utils.directoryservices.krb5_constants import SAMBA_KEYTAB_DIR
from middlewared.utils.filesystem.acl import FS_ACL_Type, path_get_acltype
from middlewared.utils.io import get_io_uring_enabled
from middlewared.utils.path import FSLocation, path_location
from middlewared.plugins.account import DEFAULT_HOME_PATH
from middlewared.plugins.smb_.constants import SMBEncryption, SMBPath, SMBSharePreset
from middlewared.plugins.smb_.utils import apply_presets, smb_strip_comments
from middlewared.plugins.smb_.util_param import AUX_PARAM_BLACKLIST

LOGGER = getLogger(__name__)

# These maps are used to implement SFM mappings
FRUIT_CATIA_MAPS = (
    "0x01:0xf001,0x02:0xf002,0x03:0xf003,0x04:0xf004",
    "0x05:0xf005,0x06:0xf006,0x07:0xf007,0x08:0xf008",
    "0x09:0xf009,0x0a:0xf00a,0x0b:0xf00b,0x0c:0xf00c",
    "0x0d:0xf00d,0x0e:0xf00e,0x0f:0xf00f,0x10:0xf010",
    "0x11:0xf011,0x12:0xf012,0x13:0xf013,0x14:0xf014",
    "0x15:0xf015,0x16:0xf016,0x17:0xf017,0x18:0xf018",
    "0x19:0xf019,0x1a:0xf01a,0x1b:0xf01b,0x1c:0xf01c",
    "0x1d:0xf01d,0x1e:0xf01e,0x1f:0xf01f",
    "0x22:0xf020,0x2a:0xf021,0x3a:0xf022,0x3c:0xf023",
    "0x3e:0xf024,0x3f:0xf025,0x5c:0xf026,0x7c:0xf027"
)

AD_KEYTAB_PARAMS = (
    f"{SAMBA_KEYTAB_DIR}/krb5.keytab0:account_name:sync_kvno:machine_password",
    f"{SAMBA_KEYTAB_DIR}/krb5.keytab1:sync_spns:sync_kvno:machine_password",
    f"{SAMBA_KEYTAB_DIR}/krb5.keytab2:spn_prefixes=nfs:sync_kvno:machine_password"
)

EXCLUDED_IDMAP_ITEMS = frozenset(['name', 'range_low', 'range_high', 'idmap_backend', 'sssd_compat'])


class TrueNASVfsObjects(enum.StrEnum):
    # Ordering here determines order in which objects entered into
    # SMB configuration, which has functional impact on SMB server
    TRUENAS_AUDIT = 'truenas_audit'
    CATIA = 'catia'
    FRUIT = 'fruit'
    STREAMS_XATTR = 'streams_xattr'
    SHADOW_COPY_ZFS = 'shadow_copy_zfs'
    ACL_XATTR = 'acl_xattr'
    IXNAS = 'ixnas'
    WINMSA = 'winmsa'
    RECYCLE = 'recycle'
    ZFS_CORE = 'zfs_core'
    IO_URING = 'io_uring'
    WORM = 'worm'
    TMPROTECT = 'tmprotect'
    ZFS_FSRVP = 'zfs_fsrvp'


def __order_vfs_objects(vfs_objects: set, fruit_enabled: bool, purpose: str):
    vfs_objects_ordered = []

    if fruit_enabled:
        # vfs_fruit must be globally enabled
        vfs_objects.add(TrueNASVfsObjects.FRUIT)

    if TrueNASVfsObjects.FRUIT in vfs_objects:
        # vfs_fruit requires streams_xattr
        vfs_objects.add(TrueNASVfsObjects.STREAMS_XATTR)

    if purpose == 'WORM_DROPBOX':
        vfs_objects.add(TrueNASVfsObjects.WORM)

    elif purpose == 'ENHANCED_TIMEMACHINE':
        vfs_objects.add(TrueNASVfsObjects.TMPROTECT)

    for obj in TrueNASVfsObjects:
        if obj in vfs_objects:
            vfs_objects_ordered.append(obj)

    return vfs_objects_ordered


def __parse_share_fs_acl(share_path: str, vfs_objects: set) -> None:
    """
    Add required VFS objects based on ZFS acltype to vfs_objects
    set.

    Raises:
       FileNotFoundError - share path doesn't exist (possibly locked)
       TypeError - really unexpected breakage in enum
       NotImplementedError - ACLs disabled at ZFS level
    """
    if path_location(share_path) is FSLocation.EXTERNAL:
        # This isn't a local filesystem path and so don't
        # try to read ACL type.
        return

    match (acltype := path_get_acltype(share_path)):
        case FS_ACL_Type.POSIX1E:
            vfs_objects.add(TrueNASVfsObjects.ACL_XATTR)
        case FS_ACL_Type.NFS4:
            vfs_objects.add(TrueNASVfsObjects.IXNAS)
        case FS_ACL_Type.DISABLED:
            raise NotImplementedError
        case _:
            raise TypeError(f'{acltype}: unknown ACL type')


def __transform_share_path(ds_type: DSType, share_config: dict, config_out: dict) -> None:
    path = share_config['path']

    if path_location(path) is FSLocation.EXTERNAL:
        config_out.update({
            'msdfs root': True,
            'msdfs proxy': path[len('EXTERNAL:'):],
            'path': '/var/empty'
        })
        return

    if share_config['home'] and not share_config['path_suffix']:
        if ds_type is DSType.AD:
            share_config['path_suffix'] = '%D/%U'
        else:
            share_config['path_suffix'] = '%U'

    if share_config['path_suffix']:
        path = os.path.join(path, share_config['path_suffix'])

    config_out['path'] = path


def generate_smb_share_conf_dict(
    ds_type: DSType,
    share_config_in: dict,
    smb_service_config: dict,
    io_uring_enabled: bool = True
) -> dict:
    # apply any presets to the config here
    share_config = apply_presets(share_config_in)
    fruit_enabled = smb_service_config['aapl_extensions']
    vfs_objects = set([TrueNASVfsObjects.ZFS_CORE])

    if io_uring_enabled:
        vfs_objects.add(TrueNASVfsObjects.IO_URING)

    config_out = {
        'hosts allow': share_config['hostsallow'],
        'hosts deny': share_config['hostsdeny'],
        'access based share enum': share_config['abe'],
        'readonly': share_config['ro'],
        'available': share_config['enabled'] and not share_config['locked'],
        'guest ok': share_config['guestok'],
        'nt acl support': share_config['acl'],
        'smbd max xattr size': 2097152,
        'fruit:metadata': 'stream',
        'fruit:resource': 'stream',
        'comment': share_config['comment'],
        'browseable': share_config['browsable'],
    }

    __transform_share_path(ds_type, share_config, config_out)

    if share_config['streams']:
        vfs_objects.add(TrueNASVfsObjects.STREAMS_XATTR)

    if share_config['recyclebin']:
        vfs_objects.add(TrueNASVfsObjects.RECYCLE)
        config_out.update({
            'recycle:repository': '.recycle/%D/%U' if ds_type is DSType.AD else '.recycle/%U',
            'recycle:keeptree': True,
            'recycle:versions': True,
            'recycle:touch': True,
            'recycle:directory_mode': '0777',
            'recycle:subdir_mode': '0700'
        })

    if share_config['shadowcopy']:
        vfs_objects.add(TrueNASVfsObjects.SHADOW_COPY_ZFS)

    if share_config['fsrvp']:
        vfs_objects.add(TrueNASVfsObjects.ZFS_FSRVP)

    if share_config['durablehandle']:
        config_out['posix locking'] = False

    if share_config['timemachine']:
        config_out['fruit:time machine'] = True

        if share_config['timemachine_quota']:
            config_out['fruit:time machine max size'] = share_config['timemachine_quota']

    if share_config['acl']:
        # Add vfs object for our ACL type
        try:
            __parse_share_fs_acl(share_config['path'], vfs_objects)
        except NotImplementedError:
            # User has disabled ACLs at ZFS level but not in SMB config
            # We'll disable NT ACL support proactively
            config_out['nt acl support'] = False

    if share_config['aapl_name_mangling']:
        # Apply SFM mangling to share. This takes different form depending
        # on whether fruit is enabled. The end result is the same.
        vfs_objects.add(TrueNASVfsObjects.CATIA)

        if fruit_enabled:
            config_out.update({
                'fruit:encoding': 'native',
                'mangled names': False
            })
        else:
            config_out.update({
                'catia:mappings': ','.join(FRUIT_CATIA_MAPS),
                'mangled names': False
            })

    if share_config['afp']:
        # Parameters for compatibility with how data was written by Netatalk
        vfs_objects.add(TrueNASVfsObjects.FRUIT)
        vfs_objects.add(TrueNASVfsObjects.CATIA)
        config_out.update({
            'fruit:encoding': 'native',
            'fruit:metadata': 'netatalk',
            'fruit:resource': 'file',
            'streams_xattr:prefix': 'user.',
            'streams_xattr:store_stream_type': False,
            'streams_xattr:xattr_compat': True
        })

    if share_config['audit']['enable']:
        vfs_objects.add(TrueNASVfsObjects.TRUENAS_AUDIT)
        for key in ('watch_list', 'ignore_list'):
            if not share_config['audit'][key]:
                continue

            config_out[f'truenas_audit:{key}'] = share_config['audit'][key]

    ordered_vfs_objects = __order_vfs_objects(vfs_objects, fruit_enabled, share_config['purpose'])
    config_out['vfs objects'] = ordered_vfs_objects

    # Some presets contain aux parameters. Set them proior to aux parameter processing
    if share_config['purpose'] not in ('NO_PRESET', 'DEFAULT_SHARE'):
        preset_params = SMBSharePreset[share_config['purpose']].value['params']
        for param in preset_params['auxsmbconf'].splitlines():
            auxparam, val = param.split('=', 1)
            config_out[auxparam.strip()] = val.strip()

    # Apply auxiliary parameters
    for param in smb_strip_comments(share_config['auxsmbconf']).splitlines():
        if not param.strip():
            # user has inserted an empty line
            continue

        auxparam, value = param.split('=', 1)
        auxparam = auxparam.strip()
        value = value.strip()

        # User may have inserted garbage in a previous release or have manually
        # modified sqlite database
        if auxparam in AUX_PARAM_BLACKLIST:
            continue

        config_out[auxparam] = value

    return config_out


def generate_smb_conf_dict(
    ds_config: dict | None,
    smb_service_config: dict,
    smb_shares: list,
    smb_bind_choices: dict,
    is_enterprise: bool,
    security_config: dict[str, bool]
):
    guest_enabled = any(filter_list(smb_shares, [['guestok', '=', True]]))
    fsrvp_enabled = any(filter_list(smb_shares, [['fsrvp', '=', True]]))
    if ds_config['service_type']:
        ds_type = DSType(ds_config['service_type'])
    else:
        ds_type = None

    home_share = filter_list(smb_shares, [['home', '=', True]])
    if home_share:
        if ds_type is DSType.AD:
            home_path_suffix = '%D/%U'
        elif not home_share[0]['path_suffix']:
            home_path_suffix = '%U'
        else:
            home_path_suffix = home_share[0]['path_suffix']

        home_path = os.path.join(home_share[0]['path'], home_path_suffix)
    else:
        home_path = DEFAULT_HOME_PATH

    loglevelint = 10 if smb_service_config['debug'] else 1

    for key in ('filemask', 'dirmask'):
        if smb_service_config[key] == 'DEFAULT':
            smb_service_config[key] = None

    """
    First set up our legacy / default SMB parameters. Several are related to
    making sure that we don't have printing support enabled.

    fruit:nfs_aces
    fruit:zero_file_id
    ------------------
    are set to ensure that vfs_fruit will always have appropriate configuration.
    nfs_aces allows clients to chmod via special ACL entries. This reacts
    poorly with rich ACL models.
    vfs_fruit has option to set the file ID to zero, which causes client to
    fallback to algorithically generated file ids by hashing file name rather
    than using server-provided ones. This is not handled properly by all
    MacOS client versions and a hash collision can lead to data corruption.

    restrict anonymous
    ------------------
    We default to disabling anonymous IPC$ access. This is mostly in response
    to being flagged by security scanners. We have to re-enable if server guest
    access is enabled.

    winbind request timeout
    ------------------
    The nsswitch is only loaded once for the life of a running process on Linux
    and so winbind will always be present. In case of standalone server we want
    to reduce the risk that unhealthy winbind state would cause hangs in NSS
    for middlewared.

    passdb backend
    ------------------
    The passdb backend is stored in non-default path in order to prevent open
    handles from affecting system dataset operations. This is safe because we
    regenerate the passdb.tdb file on reboot.

    obey pam restrictions
    ------------------
    This is currently only required for case where user homes share is in use
    because we rely on pam_mkhomedir to auto-generate the path.

    It introduces a potential failure mode where pam_session() failure will
    lead to inability access SMB shares, and so at some point we should remove
    the pam_mkhomedir dependency.
    """
    smbconf = {
        'disable spoolss': True,
        'dns proxy': False,
        'load printers': False,
        'max log size': 5120,
        'printcap': '/dev/null',
        'bind interfaces only': True,
        'fruit:nfs_aces': False,
        'fruit:zero_file_id': False,
        'rpc_daemon:mdssd': 'disabled',
        'rpc_server:mdssvc': 'disabled',
        'restrict anonymous': 0 if guest_enabled else 2,
        'winbind request timeout': 60 if ds_type is DSType.AD else 2,
        'passdb backend': f'tdbsam:{SMBPath.PASSDB_DIR.value[0]}/passdb.tdb',
        'workgroup': smb_service_config['workgroup'],
        'netbios name': smb_service_config['netbiosname'],
        'netbios aliases': ' '.join(smb_service_config['netbiosalias']),
        'guest account': smb_service_config['guest'] if smb_service_config['guest'] else 'nobody',
        'obey pam restrictions': any(home_share),
        'create mask': smb_service_config['filemask'] or '0664',
        'directory mask': smb_service_config['dirmask'] or '0775',
        'ntlm auth': smb_service_config['ntlmv1_auth'],
        'server multichannel support': smb_service_config['multichannel'],
        'unix charset': smb_service_config['unixcharset'],
        'local master': smb_service_config['localmaster'],
        'server string': smb_service_config['description'],
        'log level': loglevelint,
        'logging': 'file',
        'server smb encrypt': SMBEncryption[smb_service_config['encryption']].value,
    }

    """
    When guest access is enabled on _any_ SMB share we have to change the
    behavior of when the server maps to the guest account. `Bad User` here means
    that attempts to authenticate as a user that does not exist on the server
    will be automatically mapped to the guest account. This can lead to unexpected
    access denied errors, but many legacy users depend on this functionality and
    so we canot remove it.
    """
    if guest_enabled:
        smbconf['map to guest'] = 'Bad User'

    """
    If fsrvp is enabled on any share, then we need to have samba fork off an
    fssd daemon to handle snapshot management requests.
    """
    if fsrvp_enabled:
        smbconf.update({
            'rpc_daemon:fssd': 'fork',
            'fss:prune stale': True,
        })

    if smb_service_config['enable_smb1']:
        smbconf['server min protocol'] = 'NT1'

    if smb_service_config['syslog']:
        smbconf['logging'] = f'syslog@{min(3, loglevelint)} file'

    if smb_bindips := smb_service_config['bindip']:
        allowed_ips = set(smb_bind_choices.values())
        if (rejected := set(smb_bindips) - allowed_ips):
            LOGGER.warning(
                '%s: IP address(es) are no longer in use and should be removed '
                'from SMB configuration.', rejected
            )

        if (final_ips := allowed_ips & set(smb_bindips)):
            smbconf['interfaces'] = ' '.join(final_ips | {'127.0.0.1'})
        else:
            # We need to generate SMB configuration to prevent breaking
            # winbindd
            LOGGER.error('No specified SMB bind IP addresses are available')
            smbconf['interfaces'] = '127.0.0.1'

    """
    The following are our default Active Directory related parameters

    winbindd max domain connections
    ------------------
    Winbindd defaults to a single connection per domain controller. Real
    life testing in enterprise environments indicated that this was
    often a bottleneck on busy servers. Ten has been default since FreeNAS
    11.2 and we have yet to see cases where it needs to scale higher.


    allow trusted domains
    ------------------
    We disable support for trusted domains by default due to need to configure
    idmap backends for them. There is separate validation when the field is
    enabled in the AD plugin to check that user has properly configured idmap
    settings. If idmap settings are not configured, then SID mappings are
    written to the default idmap backend (which is a TDB file on the system
    dataset). This is not desirable because the insertion for a domain is
    first-come-first-serve (not consistent between servers).


    winbind enum users
    winbind enum groups
    ------------------
    These are defaulted to being on to preserve legacy behavior and meet user
    expectations based on long histories of howto guides online. They affect
    whether AD users / groups will appear when full lists of users / groups
    via getpwent / getgrent. It does not impact getpwnam and getgrnam.
    """
    if ds_type is DSType.AD:
        smbconf.update({
            'server role': 'member server',
            'kerberos method': 'secrets only',
            'sync machine password to keytab': ' '.join(AD_KEYTAB_PARAMS),
            'security': 'ADS',
            'local master': False,
            'domain master': False,
            'preferred master': False,
            'winbind cache time': 7200,
            'winbind max domain connections': 10,
            'winbind use default domain': ds_config['configuration']['use_default_domain'],
            'client ldap sasl wrapping': 'seal',
            'template shell': '/bin/sh',
            'allow trusted domains': ds_config['configuration']['enable_trusted_domains'],
            'realm': ds_config['configuration']['domain'],
            'template homedir': home_path,
            'winbind enum users': ds_config['enable_account_cache'],
            'winbind enum groups': ds_config['enable_account_cache'],
        })

        idmap = ds_config['configuration']['idmap']['idmap_domain']
        if ds_config['configuration']['idmap']['idmap_domain']['idmap_backend'] == 'AUTORID':
            idmap_prefix = 'idmap config * :'
        else:
            builtin = ds_config['configuration']['idmap']['builtin']
            idmap_prefix = f'idmap config {idmap["name"]}'

            smbconf.update({
                'idmap config * : backend': 'tdb',
                'idmap config * : range': f'{builtin["range_low"]} - {builtin["range_high"]}'
            })

        smbconf.update({
            f'{idmap_prefix} : backend': idmap['idmap_backend'].lower(),
            f'{idmap_prefix} : range': f'{idmap["range_low"]} - {idmap["range_high"]}',
        })
        for key, value in idmap.items():
            if key in EXCLUDED_IDMAP_ITEMS:
                continue

            smbconf[f'{idmap_prefix} : {key}'] = value

        # Set trusted domains in the configuration. This has no impact if
        # enable_trusted_domains is False and so we don't need another check
        for idmap in ds_config['configuration']['trusted_domains']:
            idmap_prefix = f'idmap config {idmap["name"]} :'
            # Set basic parameters
            smbconf.update({
                f'{idmap_prefix} backend': idmap['idmap_backend'].lower(),
                f'{idmap_prefix} range': f'{idmap["range_low"]} - {idmap["range_high"]}',
            })

            # Set other configuration options
            for key, value in idmap.items():
                if key in EXCLUDED_IDMAP_ITEMS:
                    continue

                smbconf[f'{idmap_prefix} {key}'] = value

            if idmap['idmap_backend'] == 'RFC2307':
                smbconf[f'{idmap_prefix} ldap_server'] = 'stand-alone'

    """
    The following parameters are based on what is performed when admin runs
    command ipa-client-samba-install.

    NOTE1: This requires us to have joined IPA domain through middleware
    because we need to store the password associated with the SMB keytab in
    samba's secrets.tdb file.

    NOTE2: There is some chance that the IPA domain will not have SMB information
    and in this situation we will omit from our smb.conf.
    """
    if ds_type is DSType.IPA and ds_config['configuration']['smb_domain']:
        # IPA SMB config is stored in remote IPA server and so we don't let
        # users override the config. If this is a problem it should be fixed on
        # the other end.
        domain_short = ds_config['configuration']['smb_domain']['name']
        range_low = ds_config['configuration']['smb_domain']['range_low']
        range_high = ds_config['configuration']['smb_domain']['range_high']
        domain_name = ds_config['configuration']['smb_domain']['domain_name']

        smbconf.update({
            'server role': 'member server',
            'kerberos method': 'dedicated keytab',
            'dedicated keytab file': 'FILE:/etc/ipa/smb.keytab',
            'workgroup': domain_short,
            'realm': domain_name,
            f'idmap config {domain_short} : backend': 'sss',
            f'idmap config {domain_short} : range': f'{range_low} - {range_high}',
        })

    for e in smb_service_config['smb_options'].splitlines():
        # Add relevant auxiliary parameters
        entry = e.strip()
        if entry.startswith(('#', ';')) or '=' not in entry:
            continue

        param, value = entry.split('=', 1)
        smbconf[param.strip()] = value.strip()

    # Ordering here is relevant. Do not permit smb_options to override required
    # settings for the STIG.
    if security_config['enable_gpos_stig']:
        smbconf.update({
            'client use kerberos': 'required',
            'ntlm auth': 'disabled'
        })

    # The following parameters must come after processing includes in order to
    # prevent auxiliary parameters from overriding them
    smbconf.update({
        'zfs_core:zfs_integrity_streams': is_enterprise,
        'zfs_core:zfs_block_cloning': is_enterprise,
        'registry shares': True,
        'include': 'registry',
        'SHARES': {}
    })

    io_uring_enabled = get_io_uring_enabled()

    for share in smb_shares:
        try:
            share_conf = generate_smb_share_conf_dict(ds_type, share, smb_service_config, io_uring_enabled)
        except FileNotFoundError:
            # Share path doesn't exist, exclude from config
            continue
        share_name = share['name'] if not share['home'] else 'homes'
        smbconf['SHARES'][share_name] = share_conf

    return smbconf
