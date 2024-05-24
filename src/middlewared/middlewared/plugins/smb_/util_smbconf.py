import os

from logging import getLogger
from middlewared.utils import filter_list
from middlewared.plugins.account import DEFAULT_HOME_PATH
from middlewared.plugins.smb_.constants import LOGLEVEL_MAP, SMBPath
from middlewared.utils.directoryservices.constants import DSType

LOGGER = getLogger(__name__)


def generate_smb_conf_dict(
    enabled_ds,
    ds_config,
    smb_service_config,
    smb_shares,
    smb_bind_choices,
    idmap_settings
):
    guest_enabled = any(filter_list(smb_shares, [['guestok', '=', True]]))
    fsrvp_enabled = any(filter_list(smb_shares, [['fsrvp', '=', True]]))
    ad_enabled = ipa_enabled = ad_idmap = None

    match enabled_ds:
        case DSType.AD.value:
            ad_enabled = True
            ad_idmap = filter_list(
                idmap_settings,
                [('name', '=', 'DS_TYPE_ACTIVEDIRECTORY')],
                {'get': True}
            )
        case DSType.IPA.value:
            ipa_enabled = True
        case DSType.LDAP.value | None:
            pass
        case _:
            raise ValueError(
                f'{ds_state["name"]}: Unknown directory service'
            )

    home_share = filter_list(smb_shares, [['home', '=', True]])
    if home_share:
        if ad_enabled:
            home_path_suffix = '%D/%U'
        elif not home_share[0]['path_suffix']:
            home_path_suffix = '%U'
        else:
            home_path_suffix = home_share[0]['path_suffix']

        home_path = os.path.join(home_share[0]['path'], home_path_suffix)
    else:
        home_path = DEFAULT_HOME_PATH

    loglevelint = int(LOGLEVEL_MAP.inv.get(smb_service_config['loglevel'], 1))

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
        'restrict anonymous': 0 if guest_enabled else 2,
        'winbind request timeout': 60 if ad_enabled else 2,
        'passdb backend': f'tdbsam:{SMBPath.PASSDB_DIR.value[0]}/passdb.tdb',
        'workgroup': smb_service_config['workgroup'],
        'netbios name': smb_service_config['netbiosname_local'],
        'netbios aliases': ' '.join(smb_service_config['netbiosalias']),
        'guest account': smb_service_config['guest'] if smb_service_config['guest'] else 'nobody',
        'obey pam restrictions': any(home_share),
        'create mask': smb_service_config['filemask'] or '0744',
        'directory mask': smb_service_config['dirmask'] or '0755',
        'ntlm auth': smb_service_config['ntlmv1_auth'],
        'server multichannel support': smb_service_config['multichannel'],
        'unix charset': smb_service_config['unixcharset'],
        'local master': smb_service_config['localmaster'],
        'server string': smb_service_config['description'],
        'log level': loglevelint,
        'logging': 'file',
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
    if ad_enabled:
        ac = ds_config
        smbconf.update({
            'server role': 'member server',
            'kerberos method': 'secrets and keytab',
            'security': 'ADS',
            'local master': False,
            'domain master': False,
            'preferred master': False,
            'winbind cache time': 7200,
            'winbind max domain connections': 10,
            'winbind use default domain': ac['use_default_domain'],
            'client ldap sasl wrapping': 'seal',
            'template shell': '/bin/sh',
            'allow trusted domains': ac['allow_trusted_doms'],
            'realm': ac['domainname'],
            'ads dns update': False,
            'winbind nss info': ac['nss_info'].lower(),
            'template homedir': home_path,
            'winbind enum users': ac['enumerate'],
            'winbind enum groups': ac['enumerate'],
        })

    """
    Only try to set up IPA configuration if we have an explicitly
    configured kerberos realm. The following parameters are based on what is
    performed when admin runs command ipa-client-samba-install
    """
    if ipa_enabled and ds_config['kerberos_realm']:
        smbconf.update({
            'server role': 'member server',
            'kerberos method': 'dedicated keytab',
            'dedicated keytab file': 'FILE:/etc/smb.keytab',
            'workgroup': ds_config['domain_info']['netbios_name'],
            'realm': ds_config['kerberos_realm']['krb_realm']
        })

    """
    The following part generates the smb.conf parameters from our idmap plugin
    settings. This is primarily relevant for case where TrueNAS is joined to
    an Active Directory domain.
    """
    for i in idmap_settings:
        match i['name']:
            case 'DS_TYPE_DEFAULT_DOMAIN':
                if ad_idmap and ad_idmap['idmap_backend'] == 'AUTORID':
                    continue

                domain = '*'
            case 'DS_TYPE_ACTIVEDIRECTORY':
                if not ad_enabled:
                    continue
                if i['idmap_backend'] == 'AUTORID':
                    domain = '*'
                else:
                    domain = smb_service_config['workgroup']
            case 'DS_TYPE_LDAP':
                # TODO: in future we will have migration remove this
                # from the idmap table
                continue
            case _:
                domain = i['name']

        idmap_prefix = f'idmap config {domain} :'
        smbconf.update({
            f'{idmap_prefix} backend': i['idmap_backend'].lower(),
            f'{idmap_prefix} range': f'{i["range_low"]} - {i["range_high"]}',
        })

        for k, v in i['options'].items():
            backend_parameter = 'realm' if k == 'cn_realm' else k
            match k:
                case 'ldap_server':
                    value = 'ad' if v == 'AD' else 'stand-alone'
                case 'ldap_url':
                    value = f'{"ldaps://" if i["options"]["ssl"]  == "ON" else "ldap://"}{v}'
                case 'ssl':
                    continue
                case _:
                    value = v

            smbconf.update({f'{idmap_prefix} {backend_parameter}': value})

    if ipa_enabled:
        # Separately configure idmap settings for our IPA domain since
        # this are not user-configurable on the NAS (provided by IPA server).
        domain_short = ds_config['domain_info']['netbios_name']
        range_low = ds_config['domain_info']['range_id_min']
        range_high = ds_config['domain_info']['range_id_max']
        smbconf.update({
            f'idmap config {domain_short} : backend' : 'sss',
            f'idmap config {domain_short} : range' : f'{range_low} - {range_high}'
        })

    for e in smb_service_config['smb_options'].splitlines():
        # Add relevant auxiliary parameters
        entry = e.strip()
        if entry.startswith(('#', ';')) or '=' not in entry:
            continue

        param, value = entry.split('=', 1)
        smbconf[param.strip()] = value.strip()

    smbconf.update({
        'registry shares': True,
        'include': 'registry',
    })
    return smbconf
