from middlewared.plugins.smb_.util_smbconf import generate_smb_conf_dict
from middlewared.utils.directoryservices.constants import DSType

BASE_SMB_CONFIG = {
    'id': 1,
    'netbiosname': 'TESTSERVER',
    'netbiosalias': ['BOB', 'LARRY'],
    'workgroup': 'TESTDOMAIN',
    'description': 'TrueNAS Server',
    'unixcharset': 'UTF-8',
    'syslog': False,
    'aapl_extensions': False,
    'localmaster': False,
    'guest': 'nobody',
    'filemask': '',
    'dirmask': '',
    'smb_options': '',
    'bindip': [],
    'server_sid': 'S-1-5-21-732395397-2008429054-3061640861',
    'ntlmv1_auth': False,
    'enable_smb1': False,
    'admin_group': None,
    'next_rid': 0,
    'multichannel': False,
    'encryption': 'DEFAULT',
    'debug': False
}

SMB_SYSLOG = BASE_SMB_CONFIG | {'syslog': True}
SMB_AAPL = BASE_SMB_CONFIG | {'aapl_extensions': True}
SMB_LOCALMASTER = BASE_SMB_CONFIG | {'localmaster': True}
SMB_GUEST = BASE_SMB_CONFIG | {'guest': 'mike'}
SMB_BINDIP = BASE_SMB_CONFIG | {'bindip': ['192.168.0.250', '192.168.0.251']}
SMB_NTLMV1 = BASE_SMB_CONFIG | {'ntlmv1_auth': True}
SMB_SMB1 = BASE_SMB_CONFIG | {'enable_smb1': True}
SMB_MULTICHANNEL = BASE_SMB_CONFIG | {'multichannel': True}
SMB_OPTIONS = BASE_SMB_CONFIG | {'smb_options': 'canary = bob\n canary2 = bob2 \n #comment\n ;othercomment'}
SMB_ENCRYPTION_NEGOTIATE = BASE_SMB_CONFIG | {'encryption': 'NEGOTIATE'}
SMB_ENCRYPTION_DESIRED = BASE_SMB_CONFIG | {'encryption': 'DESIRED'}
SMB_ENCRYPTION_REQUIRED = BASE_SMB_CONFIG | {'encryption': 'REQUIRED'}
SYSTEM_SECURITY_DEFAULT = {'id': 1, 'enable_fips': False, 'enable_gpos_stig': False}
SYSTEM_SECURITY_GPOS_STIG = {'id': 1, 'enable_fips': True, 'enable_gpos_stig': True}


BASE_SMB_SHARE = {
    'id': 1,
    'purpose': 'LEGACY_SHARE',
    'path': '/mnt/dozer/BASE',
    'path_suffix': '',
    'home': False,
    'name': 'TEST_HOME',
    'comment': 'canary',
    'browsable': True,
    'ro': False,
    'guestok': False,
    'recyclebin': False,
    'hostsallow': [],
    'hostsdeny': [],
    'auxsmbconf': '',
    'aapl_name_manging': False,
    'abe': False,
    'acl': True,
    'durablehandle': True,
    'streams': True,
    'timemachine': False,
    'timemachine_quota': 0,
    'vuid': '',
    'shadowcopy': True,
    'fsrvp': False,
    'enabled': True,
    'afp': False,
    'audit': {
        'enable': False,
        'watch_list': [],
        'ignore_list': []
    },
    'path_local': '/mnt/dozer/BASE',
    'locked': False
}

HOMES_SHARE = BASE_SMB_SHARE | {'path_suffix': '%U', 'home': True}
FSRVP_SHARE = BASE_SMB_SHARE | {'fsrvp': True}
GUEST_SHARE = BASE_SMB_SHARE | {'guestok': True}

BASE_IDMAP = [
    {
        'id': 1,
        'name': 'DS_TYPE_ACTIVEDIRECTORY',
        'dns_domain_name': None,
        'range_low': 100000001,
        'range_high': 200000000,
        'idmap_backend': 'RID',
        'options': {},
        'certificate': None
    },
    {
        'id': 2,
        'name': 'DS_TYPE_LDAP',
        'dns_domain_name': None,
        'range_low': 10000,
        'range_high': 90000000,
        'idmap_backend': 'LDAP',
        'options': {
            'ldap_base_dn': '',
            'ldap_user_dn': '',
            'ldap_url': '',
            'ssl': 'OFF'
        },
        'certificate': None
    },
    {
        'id': 5,
        'name': 'DS_TYPE_DEFAULT_DOMAIN',
        'dns_domain_name': None,
        'range_low': 90000001,
        'range_high': 100000000,
        'idmap_backend': 'TDB',
        'options': {},
        'certificate': None
    }
]

ADDITIONAL_DOMAIN = {
    'id': 6,
    'name': 'BOBDOM',
    'dns_domain_name': None,
    'range_low': 200000001,
    'range_high': 300000000,
    'idmap_backend': 'RID',
    'options': {},
    'certificate': None
}

AUTORID_DOMAIN = {
    'id': 1,
    'name': 'DS_TYPE_ACTIVEDIRECTORY',
    'dns_domain_name': None,
    'range_low': 10000,
    'range_high': 200000000,
    'idmap_backend': 'AUTORID',
    'options': {
        'rangesize': 100000,
        'readonly': False,
        'ignore_builtin': False,
    },
    'certificate': None
}

BASE_AD_CONFIG = {
    'id': 1,
    'domainname': 'TESTDOMAIN.IXSYSTEMS.COM',
    'bindname': '',
    'verbose_logging': False,
    'allow_trusted_doms': False,
    'use_default_domain': False,
    'allow_dns_updates': True,
    'disable_freenas_cache': False,
    'restrict_pam': False,
    'site': None,
    'timeout': 60,
    'dns_timeout': 10,
    'nss_info': 'TEMPLATE',
    'enable': True,
    'kerberos_principal': 'TESTSERVER$@TESTDOMAIN.IXSYSTEMS.COM',
    'create_computer': None,
    'kerberos_realm': 1,
    'netbiosname': 'TESTSERVER',
    'netbiosalias': [],
}
TRUSTED_DOMS = BASE_AD_CONFIG | {'allow_trusted_doms': True}
USE_DEFAULT_DOM = BASE_AD_CONFIG | {'use_default_domain': True}
DISABLE_ENUM = BASE_AD_CONFIG | {'disable_freenas_cache': True}

BASE_IPA_CONFIG = {
    'id': 1,
    'hostname': ['ipatest1.testdom.test'],
    'basedn': 'dc=testdom,dc=test',
    'binddn': 'uid=ipaadmin,cn=users,cn=accounts,dc=testdom,dc=test',
    'bindpw': '',
    'anonbind': False,
    'ssl': 'ON', 'timeout': 30,
    'dns_timeout': 5,
    'has_samba_schema': False,
    'auxiliary_parameters': '',
    'schema': 'RFC2307',
    'enable': True,
    'kerberos_principal': 'host/awalkertest5.tn.ixsystems.net@TN.IXSYSTEMS.NET',
    'validate_certificates': True,
    'disable_freenas_cache': False,
    'server_type': 'FREEIPA',
    'certificate': None,
    'kerberos_realm': 1,
    'cert_name': None,
    'uri_list': ['ldaps://ipatest1.testdom.test:636'],
    'ipa_config': {
        'realm': 'TESTDOM.TEST',
        'domain': 'testdom.test',
        'basedn': 'dc=testdom,dc=test',
        'host': 'awalkertest5.testdom.test',
        'target_server': 'ipatest1.testdom.test',
        'username': 'ipaadmin'
    },
    'ipa_domain': {
        'netbios_name': 'TN',
        'domain_sid': 'S-1-5-21-157882827-213361071-3806343854',
        'domain_name': 'testdom.test',
        'range_id_min': 925000000,
        'range_id_max': 925199999
    }
}

BIND_IP_CHOICES = {"192.168.0.250": "192.168.0.250"}


def test__base_smb():
    conf = generate_smb_conf_dict(
        None, None, BASE_SMB_CONFIG, [],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['netbios name'] == 'TESTSERVER'
    assert conf['netbios aliases'] == 'BOB LARRY'
    assert conf['workgroup'] == 'TESTDOMAIN'
    assert conf['server string'] == 'TrueNAS Server'
    assert conf['obey pam restrictions'] is False
    assert conf['restrict anonymous'] == 2
    assert conf['guest account'] == 'nobody'
    assert conf['local master'] is False
    assert conf['ntlm auth'] is False
    assert 'server min protocol' not in conf
    assert conf['server multichannel support'] is False
    assert conf['idmap config * : backend'] == 'tdb'
    assert conf['idmap config * : range'] == '90000001 - 100000000'
    assert conf['server smb encrypt'] == 'default'
    assert conf['directory mask'] == '0775'
    assert conf['create mask'] == '0664'
    assert conf['zfs_core:zfs_integrity_streams'] is False
    assert conf['zfs_core:zfs_block_cloning'] is False


def test__base_smb_enterprise():
    conf = generate_smb_conf_dict(
        None, None, BASE_SMB_CONFIG, [],
        BIND_IP_CHOICES, BASE_IDMAP, True, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['zfs_core:zfs_integrity_streams'] is True
    assert conf['zfs_core:zfs_block_cloning'] is True


def test__syslog():
    conf = generate_smb_conf_dict(
        None, None, SMB_SYSLOG, [],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['logging'] == ('syslog@1 file')


def test__localmaster():
    conf = generate_smb_conf_dict(
        None, None, SMB_LOCALMASTER, [],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['local master'] is True


def test__guestaccount():
    conf = generate_smb_conf_dict(
        None, None, SMB_GUEST, [],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['guest account'] == 'mike'


def test__bindip():
    conf = generate_smb_conf_dict(
        None, None, SMB_BINDIP, [],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert set(conf['interfaces'].split(' ')) == set(['192.168.0.250', '127.0.0.1'])


def test__ntlmv1auth():
    conf = generate_smb_conf_dict(
        None, None, SMB_NTLMV1, [],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['ntlm auth'] is True


def test__smb1_enable():
    conf = generate_smb_conf_dict(
        None, None, SMB_SMB1, [],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['server min protocol'] == 'NT1'


def test__smb_options():
    conf = generate_smb_conf_dict(
        None, None, SMB_OPTIONS, [],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['canary'] == 'bob'
    assert conf['canary2'] == 'bob2'


def test__multichannel():
    conf = generate_smb_conf_dict(
        None, None, SMB_MULTICHANNEL, [],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['server multichannel support'] is True


def test__homes_share():
    conf = generate_smb_conf_dict(
        None, None, BASE_SMB_CONFIG, [HOMES_SHARE],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert 'obey pam restrictions' in conf
    assert conf['obey pam restrictions'] is True


def test__guest_share():
    conf = generate_smb_conf_dict(
        None, None, BASE_SMB_CONFIG, [GUEST_SHARE],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['restrict anonymous'] == 0


def test__fsrvp_share():
    conf = generate_smb_conf_dict(
        None, None, BASE_SMB_CONFIG, [FSRVP_SHARE],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['rpc_daemon:fssd'] == 'fork'
    assert conf['fss:prune stale'] is True


def test__ad_base():
    conf = generate_smb_conf_dict(
        DSType.AD, BASE_AD_CONFIG,
        BASE_SMB_CONFIG, [],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['realm'] == 'TESTDOMAIN.IXSYSTEMS.COM'
    assert conf['winbind use default domain'] is False
    assert conf['allow trusted domains'] is False
    assert conf['template homedir'] == '/var/empty'
    assert conf['winbind enum users'] is True
    assert conf['winbind enum groups'] is True
    assert conf['local master'] is False
    assert conf['domain master'] is False
    assert conf['idmap config * : backend'] == 'tdb'
    assert conf['idmap config * : range'] == '90000001 - 100000000'
    assert conf['idmap config TESTDOMAIN : backend'] == 'rid'
    assert conf['idmap config TESTDOMAIN : range'] == '100000001 - 200000000'


def test__ad_homes_share():
    conf = generate_smb_conf_dict(
        DSType.AD, BASE_AD_CONFIG,
        BASE_SMB_CONFIG, [HOMES_SHARE],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert 'obey pam restrictions' in conf
    assert conf['obey pam restrictions'] is True

    assert 'template homedir' in conf
    assert conf['template homedir'] == '/mnt/dozer/BASE/%D/%U'


def test__ad_enumeration():
    conf = generate_smb_conf_dict(
        DSType.AD, DISABLE_ENUM,
        BASE_SMB_CONFIG, [],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['winbind enum users'] is False
    assert conf['winbind enum groups'] is False


def test__ad_trusted_doms():
    conf = generate_smb_conf_dict(
        DSType.AD, TRUSTED_DOMS,
        BASE_SMB_CONFIG, [],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['allow trusted domains'] is True


def test__ad_default_domain():
    conf = generate_smb_conf_dict(
        DSType.AD, USE_DEFAULT_DOM,
        BASE_SMB_CONFIG, [],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['winbind use default domain'] is True


def test__ad_additional_domain():
    conf = generate_smb_conf_dict(
        DSType.AD, TRUSTED_DOMS,
        BASE_SMB_CONFIG, [],
        BIND_IP_CHOICES, BASE_IDMAP + [ADDITIONAL_DOMAIN], False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['idmap config BOBDOM : backend'] == 'rid'
    assert conf['idmap config BOBDOM : range'] == '200000001 - 300000000'


def test__ad_autorid():
    conf = generate_smb_conf_dict(
        DSType.AD, BASE_AD_CONFIG,
        BASE_SMB_CONFIG, [],
        BIND_IP_CHOICES, [AUTORID_DOMAIN, BASE_IDMAP[1], BASE_IDMAP[2]],
        False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['idmap config * : backend'] == 'autorid'
    assert conf['idmap config * : range'] == '10000 - 200000000'


def test__encryption_negotiate():
    conf = generate_smb_conf_dict(
        None, None, SMB_ENCRYPTION_NEGOTIATE, [],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['server smb encrypt'] == 'if_required'


def test__encryption_desired():
    conf = generate_smb_conf_dict(
        None, None, SMB_ENCRYPTION_DESIRED, [],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['server smb encrypt'] == 'desired'


def test__encryption_required():
    conf = generate_smb_conf_dict(
        None, None, SMB_ENCRYPTION_REQUIRED, [],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['server smb encrypt'] == 'required'


def test__ipa_base():
    conf = generate_smb_conf_dict(
        DSType.IPA, BASE_IPA_CONFIG,
        BASE_SMB_CONFIG, [],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['workgroup'] == 'TN'
    assert conf['server role'] == 'member server'
    assert conf['kerberos method'] == 'dedicated keytab'
    assert conf['dedicated keytab file'] == 'FILE:/etc/ipa/smb.keytab'
    assert conf['realm'] == 'TESTDOM.TEST'
    assert conf['idmap config TN : backend'] == 'sss'
    assert conf['idmap config TN : range'] == '925000000 - 925199999'


def test__enable_stig():
    conf = generate_smb_conf_dict(
        None, None, BASE_SMB_CONFIG, [],
        BIND_IP_CHOICES, BASE_IDMAP, True, SYSTEM_SECURITY_GPOS_STIG
    )
    assert conf['client use kerberos'] == 'required'
    assert conf['ntlm auth'] == 'disabled'


def test__multiprotocol_share_leases():
    conf = generate_smb_conf_dict(
        None, None, BASE_SMB_CONFIG, [BASE_SMB_SHARE | {'purpose': 'MULTI_PROTOCOL_NFS'}],
        BIND_IP_CHOICES, BASE_IDMAP, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['smb2 leases'] is False
