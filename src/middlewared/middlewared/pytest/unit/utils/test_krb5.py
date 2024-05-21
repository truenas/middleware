import base64
import jsonschema
import os
import pytest

from middlewared.utils.directoryservices import krb5_constants, krb5, krb5_conf


SAMPLE_KEYTAB = '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'

SAMPLE_CCACHE = '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'

KEYTAB_NAME = 'krb5.keytab'
CCACHE_NAME = 'krb5cc_0'

APPDEFAULTS_AUX = """
pam = {
    renew_lifetime = 86400
}
"""

REALMS = [
    {
        'id': 1,
        'realm': 'AD02.TN.IXSYSTEMS.NET',
        'kdc': ['10.238.238.2', '10.238.238.3'],
        'admin_server': ['10.238.238.2'],
        'kpasswd_server': ['10.238.238.2'],
    },
    {
        'id': 2,
        'realm': 'AD03.TN.IXSYSTEMS.NET',
        'kdc': [],
        'admin_server': [],
        'kpasswd_server': [],
    },
]


@pytest.fixture(scope="function")
def kerberos_data_dir(tmpdir):
    with open(os.path.join(tmpdir, KEYTAB_NAME), 'wb') as f:
        f.write(base64.b64decode(SAMPLE_KEYTAB))
        f.flush()

    with open(os.path.join(tmpdir, CCACHE_NAME), 'wb') as f:
        f.write(base64.b64decode(SAMPLE_CCACHE))
        f.flush()

    return tmpdir


def test__ktutil_list_impl(kerberos_data_dir):
    """
    Validate that parser for kerberos keytab works and provides expected entries
    """
    entries = krb5.ktutil_list_impl(os.path.join(kerberos_data_dir, KEYTAB_NAME))
    assert len(entries) != 0
    slots = []
    jsonschema.validate(entries, krb5.KTUTIL_LIST_OUTPUT_SCHEMA)
    for entry in entries:
        assert entry['slot'] not in slots
        slots.append(entry['slot'])

        if entry['etype'] in (
            krb5_constants.KRB_ETYPE.AES256_CTS_HMAC_SHA1_96.value,
            krb5_constants.KRB_ETYPE.AES128_CTS_HMAC_SHA1_96.value,
        ):
            assert entry['etype_deprecated'] is False, str(entry)
        else:
            assert entry['etype_deprecated'] is True, str(entry)


def test__keytab_extraction(kerberos_data_dir):
    """
    Validate that we can pass query-filters to `extract_from_keytab`
    with expected results
    """
    data = krb5.extract_from_keytab(
        os.path.join(kerberos_data_dir, KEYTAB_NAME),
        [['etype_deprecated', '=', False]]
    )
    new_kt_path = os.path.join(kerberos_data_dir, 'new_kt')
    with open(new_kt_path, 'wb') as f:
        f.write(data)
        f.flush()

    entries = krb5.ktutil_list_impl(new_kt_path)
    jsonschema.validate(entries, krb5.KTUTIL_LIST_OUTPUT_SCHEMA)
    for entry in entries:
        assert entry['etype_deprecated'] is False, str(entry)


def test__keytab_services(kerberos_data_dir):
    """
    This validates that we are properly retrieving a list of service names
    from a given keytab
    """
    svcs = krb5.keytab_services(os.path.join(kerberos_data_dir, KEYTAB_NAME))
    assert set(svcs) == set(['restrictedkrbhost', 'host'])


def test__klist_impl(kerberos_data_dir):
    """
    This validates that we can read and parse a given kerberos ccache file
    """
    ccache_path = os.path.join(kerberos_data_dir, CCACHE_NAME)
    klist = krb5.klist_impl(ccache_path)
    jsonschema.validate(klist, krb5.KLIST_OUTPUT_SCHEMA)

    assert klist['default_principal'] == 'TESTWPQIM603V7$@AD02.TN.IXSYSTEMS.NET'

    assert klist['ticket_cache'].get('type') == 'FILE'
    assert klist['ticket_cache'].get('name') == ccache_path

    assert len(klist['tickets']) == 1

    tkt = klist['tickets'][0]

    assert len(tkt['flags']) != 0


@pytest.mark.parametrize('params,expected,success', [
    ('dns_canonicalize_hostname = true', {'dns_canonicalize_hostname': 'true'}, True),
    ('canonicalize = true', {'canonicalize': 'true'}, True),
    ('admin_server = canary', None, False),  # invalid entry
    ('rdns = canary', None, False),  # wrong type for boolean value
    ('permitted_enctypes = aes256-cts-hmac-sha1-96', {'permitted_enctypes': 'aes256-cts-hmac-sha1-96'}, True),
    ('permitted_enctypes = canary', None, False),  # not a valid encryption type
])
def test__krb5conf_libdefaults_aux_parser(params, expected, success):
    data = {}

    if success:
        krb5_conf.parse_krb_aux_params(
            krb5_conf.KRB5ConfSection.LIBDEFAULTS,
            data,
            params
        )
        assert data == expected

    else:
        with pytest.raises(ValueError):
            krb5_conf.parse_krb_aux_params(
                krb5_conf.KRB5ConfSection.LIBDEFAULTS,
                data,
                params
            )


@pytest.mark.parametrize('params,expected,success', [
    ('renew_lifetime = 86400', {'renew_lifetime': '86400'}, True),
    ('canonicalize = true', None, False),
    (APPDEFAULTS_AUX, {'pam': {'renew_lifetime': '86400'}}, True),
])
def test__krb5conf_appdefaults_aux_parser(params, expected, success):
    data = {}

    if success:
        krb5_conf.parse_krb_aux_params(
            krb5_conf.KRB5ConfSection.APPDEFAULTS,
            data,
            params
        )
        assert data == expected

    else:
        with pytest.raises(ValueError):
            krb5_conf.parse_krb_aux_params(
                krb5_conf.KRB5ConfSection.APPDEFAULTS,
                data,
                params
            )


def validate_realms_section(data):
    """
    data will consist of approximately following:

    \tAD02.TN.IXSYSTEMS.NET = {\n
    \t\tdefault_domain = AD02.TN.IXSYSTEMS.NET\n
    \t\tkdc = ip1 ip2 ip3\n
    \t\tadmin_server = ip1\n
    \t\tkpasswd_server = ip1 ip2 ip3\n
    """
    def validate_realm(idx, realm):
        this = REALMS[idx]
        lidx = 0
        for line in realm.splitlines():
            if not line.strip():
                continue

            match lidx:
                case 0:
                    assert line.startswith(f'\t{this["realm"]} =')
                case 1:
                    assert line.strip() == f'default_domain = {this["realm"]}', str(realm)
                case _:
                    data = line.split('=')
                    assert len(data) == 2, realm
                    key, val = data
                    assert this[key.strip()] == val.strip().split()

            lidx += 1

    for idx, realm in enumerate(data.split('}')):
        if not realm.strip():
            continue

        validate_realm(idx, realm)


def validate_domain_realms_section(data):
    """
    data will consist of approximately following:

    \tad02.tn.ixsystems.net = AD02.TN.IXSYSTEMS.NET\n
    \t.ad02.tn.ixsystems.net = AD02.TN.IXSYSTEMS.NET\n
    \tAD02.TN.IXSYSTEMS.NET = AD02.TN.IXSYSTEMS.NET\n
    \t.AD02.TN.IXSYSTEMS.NET = AD02.TN.IXSYSTEMS.NET\n
    """
    realm_idx = 0

    for idx, line in enumerate(data.splitlines()):
        relative_idx = idx % 4
        if idx and relative_idx == 0:
            realm_idx += 1

        realm_name = REALMS[realm_idx]['realm']

        match relative_idx:
            case 0:
                assert line.strip() == f'{realm_name.lower()} = {realm_name}'
            case 1:
                assert line.strip() == f'.{realm_name.lower()} = {realm_name}'
            case 2:
                assert line.strip() == f'{realm_name.upper()} = {realm_name}'
            case 3:
                assert line.strip() == f'.{realm_name.upper()} = {realm_name}'


def test__krb5conf_realm():
    """
    Verify that a list of kerberos realms is stored properly
    within a KRB5Conf object
    """
    kconf = krb5_conf.KRB5Conf()

    kconf.add_realms(REALMS)

    stored_realms = kconf.realms
    for realm in REALMS:
        assert realm['realm'] in stored_realms

        stored = stored_realms[realm['realm']]
        assert stored['realm'] == realm['realm']
        assert stored['admin_server'] == realm['admin_server']
        assert stored['kpasswd_server'] == realm['kpasswd_server']
        assert stored['kdc'] == realm['kdc']

    # Convert our stored kerberos realm configuration into krb5.conf
    # data via `generate()` method and validate it's what we expect.
    for section in kconf.generate().split('\n\n'):
        if not section.startswith(('[realms]', '[domain_realms]')):
            continue

        section_name, data = section.split('\n', 1)
        match section_name:
            case '[realms]':
                validate_realms_section(data)
            case '[domain_realms]':
                validate_domain_realms_section(data)
            case _:
                raise ValueError(f'{section_name}: unexpected entry')


def test__krb5conf_libdefaults():
    """
    Validate generating krb5.conf with libdefault configured via
    config dict and auxiliary parameter blob
    """
    kconf = krb5_conf.KRB5Conf()
    kconf.add_libdefaults(
        {'canonicalize': 'true'},
        'rdns = false\npermitted_enctypes = aes256-cts-hmac-sha1-96'
    )

    for section in kconf.generate().split('\n\n'):
        if not section.startswith('[libdefaults]'):
            continue

        section_name, data = section.split('\n', 1)

        for line in data.splitlines():
            if not line.strip():
                continue

            key, value = line.strip().split('=')

            match key.strip():
                case 'canonicalize':
                    assert value.strip() == 'true'
                case 'rdns':
                    assert value.strip() == 'false'
                case 'permitted_enctypes':
                    assert value.strip() == 'aes256-cts-hmac-sha1-96'
                case _:
                    raise ValueError(f'{key}: unexpected libdefault parameter')


def test__krb5conf_appdefaults():
    """
    Validate generating krb5.conf with libdefault configured via
    config dict and auxiliary parameter blob
    """
    kconf = krb5_conf.KRB5Conf()
    kconf.add_appdefaults(
        {'renew_lifetime': '86400'},
        'forwardable = true\nproxiable = false'
    )

    for section in kconf.generate().split('\n\n'):
        if not section.startswith('[appdefaults]'):
            continue

        section_name, data = section.split('\n', 1)

        for line in data.splitlines():
            if not line.strip():
                continue

            key, value = line.strip().split('=')

            match key.strip():
                case 'renew_lifetime':
                    assert value.strip() == '86400'
                case 'forwardable':
                    assert value.strip() == 'true'
                case 'proxiable':
                    assert value.strip() == 'false'
                case _:
                    raise ValueError(f'{key}: unexpected libdefault parameter')


def test__write_krb5_conf(kerberos_data_dir):
    kconf = krb5_conf.KRB5Conf()
    kconf.add_realms(REALMS)
    kconf.add_libdefaults({'default_realm': 'AD02.TN.IXSYSTEMS.NET'})

    data = kconf.generate()

    path = os.path.join(kerberos_data_dir, 'test_krb5.conf')
    kconf.write(path)

    with open(path, 'r') as f:
        assert f.read() == data
