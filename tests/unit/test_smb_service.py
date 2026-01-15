from middlewared.plugins.smb_.util_smbconf import generate_smb_conf_dict
from middlewared.utils.directoryservices.constants import DSType
from middlewared.utils.smb import TRUESEARCH_ES_PATH

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
    'search_protocols': [],
    'stateful_failover': False,
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
DEFAULT_SHARE_OPTIONS = {'aapl_name_mangling': False}

BASE_SMB_SHARE = {
    'id': 1,
    'purpose': 'DEFAULT_SHARE',
    'path': '/mnt/dozer/BASE',
    'name': 'TEST_HOME',
    'enabled': True,
    'comment': 'canary',
    'readonly': False,
    'browsable': True,
    'access_based_share_enumeration': False,
    'locked': False,
    'audit': {
        'enable': False,
        'watch_list': [],
        'ignore_list': []
    },
    'options': DEFAULT_SHARE_OPTIONS
}

LEGACY_OPTIONS = {
    'path_suffix': None,
    'hostsallow': [],
    'hostsdeny': [],
    'guestok': False,
    'streams': True,
    'durablehandle': True,
    'shadowcopy': True,
    'fsrvp': False,
    'home': False,
    'acl': True,
    'afp': False,
    'timemachine': False,
    'recyclebin': False,
    'timemachine_quota': 0,
    'aapl_name_mangling': False,
    'vuid': None,
    'auxsmbconf': ''
}

HOMES_SHARE = BASE_SMB_SHARE | {'purpose': 'LEGACY_SHARE', 'options': LEGACY_OPTIONS | {'path_suffix': '%U', 'home': True}}
FSRVP_SHARE = BASE_SMB_SHARE | {'purpose': 'LEGACY_SHARE', 'options': LEGACY_OPTIONS | {'fsrvp': True}}
GUEST_SHARE = BASE_SMB_SHARE | {'purpose': 'LEGACY_SHARE', 'options': LEGACY_OPTIONS | {'guestok': True}}

BASE_AD_IDMAP = {
    'builtin': {'range_low': 90000001, 'range_high': 100000000},
    'idmap_domain': {
        'name': 'TESTDOMAIN',
        'idmap_backend': 'RID',
        'range_low': 100000001,
        'range_high': 200000000
    }
}

ADDITIONAL_AD_DOMAIN = {
    'name': 'BOBDOM',
    'range_low': 200000001,
    'range_high': 300000000,
    'idmap_backend': 'RID',
}

BASE_AD_CONFIG = {
    'id': 1,
    'service_type': 'ACTIVEDIRECTORY',
    'credential': {
        'credential_type': 'KERBEROS_PRINCIPAL',
        'principal': 'TESTSERVER$@TESTDOMAIN.IXSYSTEMS.COM'
    },
    'enable': True,
    'enable_account_cache': True,
    'enable_dns_updates': True,
    'timeout': 10,
    'kerberos_realm': 'TESTDOMAIN.IXSYSTEMS.COM',
    'configuration': {
        'hostname': 'TESTSERVER',
        'domain': 'TESTDOMAIN.IXSYSTEMS.COM',
        'idmap': BASE_AD_IDMAP,
        'site': None,
        'computer_account_ou': None,
        'use_default_domain': False,
        'enable_trusted_domains': False,
        'trusted_domains': []
    }
}
TRUSTED_DOMS = BASE_AD_CONFIG | {'configuration': BASE_AD_CONFIG['configuration'] | {
    'enable_trusted_domains': True,
    'trusted_domains': [ADDITIONAL_AD_DOMAIN]
}}
USE_DEFAULT_DOM = BASE_AD_CONFIG | {'configuration': BASE_AD_CONFIG['configuration'] | {
    'use_default_domain': True,
}}
DISABLE_ENUM = BASE_AD_CONFIG | {'enable_account_cache': False}

BASE_IPA_CONFIG = {
    'id': 1,
    'service_type': 'IPA',
    'credential': {
        'credential_type': 'KERBEROS_PRINCIPAL',
        'principal': 'host/awalkertest5.tn.ixsystems.net@TN.IXSYSTEMS.NET'
    },
    'enable': True,
    'enable_account_cache': True,
    'enable_dns_updates': True,
    'timeout': 10,
    'kerberos_realm': 'TESTDOM.TEST',
    'configuration': {
        'target_server': 'ipatest1.testdom.test',
        'hostname': 'awalkertest5',
        'domain': 'testdom.test',
        'basedn': 'dc=testdom,dc=test',
        'smb_domain': {
            'name': 'TN',
            'idmap_backend': 'SSS',
            'range_low': 925000000,
            'range_high': 925199999,
            'domain_name': 'testdom.test',
            'domain_sid': 'S-1-5-21-157882827-213361071-3806343854',
        },
        'validate_certificates': True
    }
}

DISABLED_DS_CONFIG = {
    'id': 1,
    'service_type': None,
    'credential': None,
    'enable': False,
    'enable_account_cache': True,
    'enable_dns_updates': True,
    'timeout': 10,
    'kerberos_realm': None,
    'configuration': None,
}

BIND_IP_CHOICES = {"192.168.0.250": "192.168.0.250"}


def test__base_smb():
    conf = generate_smb_conf_dict(
        DISABLED_DS_CONFIG, BASE_SMB_CONFIG, [],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
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
    assert conf['idmap config * : range'] == '90000001 - 90010001'
    assert conf['server smb encrypt'] == 'default'
    assert conf['directory mask'] == '0775'
    assert conf['create mask'] == '0664'
    assert conf['zfs_core:zfs_integrity_streams'] is False
    assert conf['zfs_core:zfs_block_cloning'] is False


def test__base_smb_enterprise():
    conf = generate_smb_conf_dict(
        DISABLED_DS_CONFIG, BASE_SMB_CONFIG, [],
        BIND_IP_CHOICES, True, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['zfs_core:zfs_integrity_streams'] is True
    assert conf['zfs_core:zfs_block_cloning'] is True


def test__syslog():
    conf = generate_smb_conf_dict(
        DISABLED_DS_CONFIG, SMB_SYSLOG, [],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['logging'] == ('syslog@1 file')


def test__localmaster():
    conf = generate_smb_conf_dict(
        DISABLED_DS_CONFIG, SMB_LOCALMASTER, [],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['local master'] is True


def test__guestaccount():
    conf = generate_smb_conf_dict(
        DISABLED_DS_CONFIG, SMB_GUEST, [],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['guest account'] == 'mike'


def test__bindip():
    conf = generate_smb_conf_dict(
        DISABLED_DS_CONFIG, SMB_BINDIP, [],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
    )
    assert set(conf['interfaces'].split(' ')) == set(['192.168.0.250', '127.0.0.1'])


def test__ntlmv1auth():
    conf = generate_smb_conf_dict(
        DISABLED_DS_CONFIG, SMB_NTLMV1, [],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['ntlm auth'] is True


def test__smb1_enable():
    conf = generate_smb_conf_dict(
        DISABLED_DS_CONFIG, SMB_SMB1, [],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['server min protocol'] == 'NT1'


def test__smb_options():
    conf = generate_smb_conf_dict(
        DISABLED_DS_CONFIG, SMB_OPTIONS, [],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['canary'] == 'bob'
    assert conf['canary2'] == 'bob2'


def test__multichannel():
    conf = generate_smb_conf_dict(
        DISABLED_DS_CONFIG, SMB_MULTICHANNEL, [],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['server multichannel support'] is True


def test__homes_share():
    conf = generate_smb_conf_dict(
        DISABLED_DS_CONFIG, BASE_SMB_CONFIG, [HOMES_SHARE],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
    )
    assert 'obey pam restrictions' in conf
    assert conf['obey pam restrictions'] is True


def test__guest_share():
    conf = generate_smb_conf_dict(
        DISABLED_DS_CONFIG, BASE_SMB_CONFIG, [GUEST_SHARE],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['restrict anonymous'] == 0


def test__fsrvp_share():
    conf = generate_smb_conf_dict(
        DISABLED_DS_CONFIG, BASE_SMB_CONFIG, [FSRVP_SHARE],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['rpc_daemon:fssd'] == 'fork'
    assert conf['fss:prune stale'] is True


def test__ad_base():
    conf = generate_smb_conf_dict(
        BASE_AD_CONFIG,
        BASE_SMB_CONFIG, [],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
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
    assert 'idmap config TESTDOMAIN : backend' in conf, str([x for x in conf.keys() if x.startswith('idmap')])
    assert conf['idmap config TESTDOMAIN : backend'] == 'rid'
    assert conf['idmap config TESTDOMAIN : range'] == '100000001 - 200000000'


def test__ad_homes_share():
    conf = generate_smb_conf_dict(
        BASE_AD_CONFIG,
        BASE_SMB_CONFIG, [HOMES_SHARE],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
    )
    assert 'obey pam restrictions' in conf
    assert conf['obey pam restrictions'] is True

    assert 'template homedir' in conf
    assert conf['template homedir'] == '/mnt/dozer/BASE/%D/%U'


def test__ad_enumeration():
    conf = generate_smb_conf_dict(
        DISABLE_ENUM,
        BASE_SMB_CONFIG, [],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['winbind enum users'] is False
    assert conf['winbind enum groups'] is False


def test__ad_trusted_doms():
    conf = generate_smb_conf_dict(
        TRUSTED_DOMS,
        BASE_SMB_CONFIG, [],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['allow trusted domains'] is True


def test__ad_default_domain():
    conf = generate_smb_conf_dict(
        USE_DEFAULT_DOM,
        BASE_SMB_CONFIG, [],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['winbind use default domain'] is True


def test__ad_additional_domain():
    conf = generate_smb_conf_dict(
        TRUSTED_DOMS,
        BASE_SMB_CONFIG, [],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['idmap config BOBDOM : backend'] == 'rid'
    assert conf['idmap config BOBDOM : range'] == '200000001 - 300000000'


def test__encryption_negotiate():
    conf = generate_smb_conf_dict(
        DISABLED_DS_CONFIG, SMB_ENCRYPTION_NEGOTIATE, [],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['server smb encrypt'] == 'if_required'


def test__encryption_desired():
    conf = generate_smb_conf_dict(
        DISABLED_DS_CONFIG, SMB_ENCRYPTION_DESIRED, [],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['server smb encrypt'] == 'desired'


def test__encryption_required():
    conf = generate_smb_conf_dict(
        DISABLED_DS_CONFIG, SMB_ENCRYPTION_REQUIRED, [],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['server smb encrypt'] == 'required'


def test__ipa_base():
    conf = generate_smb_conf_dict(
        BASE_IPA_CONFIG,
        BASE_SMB_CONFIG, [],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
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
        DISABLED_DS_CONFIG, BASE_SMB_CONFIG, [],
        BIND_IP_CHOICES, True, SYSTEM_SECURITY_GPOS_STIG
    )
    assert conf['client use kerberos'] == 'required'
    assert conf['ntlm auth'] == 'disabled'


def test__search_protocols_protocols_none():
    conf = generate_smb_conf_dict(
        DISABLED_DS_CONFIG, BASE_SMB_CONFIG, [],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['rpc_daemon:mdssd'] == 'disabled'
    assert conf['rpc_server:mdssvc'] == 'disabled'


def test_search_protocols_spotlight():
    conf = generate_smb_conf_dict(
        DISABLED_DS_CONFIG, BASE_SMB_CONFIG | {'search_protocols': ['SPOTLIGHT']}, [],
        BIND_IP_CHOICES, False, SYSTEM_SECURITY_DEFAULT
    )
    assert conf['spotlight backend'] == 'elasticsearch'
    assert conf['elasticsearch:address'] == TRUESEARCH_ES_PATH
    assert conf['spotlight'] is True
    assert 'rpc_daemon:mdssd' not in conf
    assert 'rpc_server:mdssvc' not in conf
