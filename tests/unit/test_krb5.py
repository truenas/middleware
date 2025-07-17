import base64
import jsonschema
import os
import pytest

from contextlib import contextmanager
from middlewared.service_exception import CallError
from middlewared.utils.directoryservices import krb5_constants, krb5, krb5_conf


# Base64-encoded kerberos keytab from reference system
SAMPLE_KEYTAB = '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'  # noqa

SAMPLE_KEYTAB2 = "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"  # noqa

# Base64-encoded kerberos ccache file from reference system
SAMPLE_CCACHE = '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'  # noqa


# Below KEYTAB_LIST_OUTPUT should match SAMPLE_KEYTAB above
# if the keytab is replaced, then this output should also be replaced
KEYTAB_LIST_OUTPUT = """Keytab name: FILE:/tmp/test_kt
KVNO Timestamp         Principal
---- ----------------- --------------------------------------------------------
   1 07/31/20 05:46:50 restrictedkrbhost/test49.homedom.fun@HOMEDOM.FUN (DEPRECATED:des-cbc-crc) 
   1 07/31/20 05:46:50 restrictedkrbhost/TEST49@HOMEDOM.FUN (DEPRECATED:des-cbc-crc) 
   1 07/31/20 05:46:50 restrictedkrbhost/test49.homedom.fun@HOMEDOM.FUN (DEPRECATED:des-cbc-md5) 
   1 07/31/20 05:46:50 restrictedkrbhost/TEST49@HOMEDOM.FUN (DEPRECATED:des-cbc-md5) 
   1 07/31/20 05:46:50 restrictedkrbhost/test49.homedom.fun@HOMEDOM.FUN (aes128-cts-hmac-sha1-96) 
   1 07/31/20 05:46:50 restrictedkrbhost/TEST49@HOMEDOM.FUN (aes128-cts-hmac-sha1-96) 
   1 07/31/20 05:46:50 restrictedkrbhost/test49.homedom.fun@HOMEDOM.FUN (aes256-cts-hmac-sha1-96) 
   1 07/31/20 05:46:50 restrictedkrbhost/TEST49@HOMEDOM.FUN (aes256-cts-hmac-sha1-96) 
   1 07/31/20 05:46:50 restrictedkrbhost/test49.homedom.fun@HOMEDOM.FUN (DEPRECATED:arcfour-hmac) 
   1 07/31/20 05:46:50 restrictedkrbhost/TEST49@HOMEDOM.FUN (DEPRECATED:arcfour-hmac) 
   1 07/31/20 05:46:50 host/test49.homedom.fun@HOMEDOM.FUN (DEPRECATED:des-cbc-crc) 
   1 07/31/20 05:46:50 host/TEST49@HOMEDOM.FUN (DEPRECATED:des-cbc-crc) 
   1 07/31/20 05:46:50 host/test49.homedom.fun@HOMEDOM.FUN (DEPRECATED:des-cbc-md5) 
   1 07/31/20 05:46:50 host/TEST49@HOMEDOM.FUN (DEPRECATED:des-cbc-md5) 
   1 07/31/20 05:46:50 host/test49.homedom.fun@HOMEDOM.FUN (aes128-cts-hmac-sha1-96) 
   1 07/31/20 05:46:50 host/TEST49@HOMEDOM.FUN (aes128-cts-hmac-sha1-96) 
   1 07/31/20 05:46:50 host/test49.homedom.fun@HOMEDOM.FUN (aes256-cts-hmac-sha1-96) 
   1 07/31/20 05:46:50 host/TEST49@HOMEDOM.FUN (aes256-cts-hmac-sha1-96) 
   1 07/31/20 05:46:50 host/test49.homedom.fun@HOMEDOM.FUN (DEPRECATED:arcfour-hmac) 
   1 07/31/20 05:46:50 host/TEST49@HOMEDOM.FUN (DEPRECATED:arcfour-hmac) 
   1 07/31/20 05:46:50 TEST49$@HOMEDOM.FUN (DEPRECATED:des-cbc-crc) 
   1 07/31/20 05:46:50 TEST49$@HOMEDOM.FUN (DEPRECATED:des-cbc-md5) 
   1 07/31/20 05:46:50 TEST49$@HOMEDOM.FUN (aes128-cts-hmac-sha1-96) 
   1 07/31/20 05:46:50 TEST49$@HOMEDOM.FUN (aes256-cts-hmac-sha1-96) 
   1 07/31/20 05:46:50 TEST49$@HOMEDOM.FUN (DEPRECATED:arcfour-hmac)"""  # noqa


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
        'primary_kdc': '10.238.238.2',
        'kdc': ['10.238.238.2', '10.238.238.3'],
        'admin_server': ['10.238.238.2'],
        'kpasswd_server': ['10.238.238.2'],
    },
    {
        'id': 2,
        'realm': 'AD03.TN.IXSYSTEMS.NET',
        'primary_kdc': None,
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

    # The schema for what entries / types are expected for valid keytab entries
    # returned from `ktutil_list_impl` is defined in the
    # KTUTIL_LIST_OUTPUT_SCHEMA
    #
    # If for some reason, the output for this method is changed, then the
    # aforementioned schema _must_ also be changed or this test will fail.
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


def test__keytab_parser(kerberos_data_dir):
    entries = krb5.ktutil_list_impl(os.path.join(kerberos_data_dir, KEYTAB_NAME))
    data_to_parse = KEYTAB_LIST_OUTPUT.splitlines()[3:]
    assert len(entries) == len(data_to_parse)

    assert entries == krb5.parse_keytab(data_to_parse)


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


def test__check_ticket(kerberos_data_dir):
    """
    We use gssapi library to perform basic validation of kerberos tickets
    The ccache file we write as part of this test is valid and expired
    so we check that it raises the expected error if exceptions are
    requested otherwise check that it returns False. Tests of valid
    tickets occur during full CI test runs.
    """
    ccache_path = os.path.join(kerberos_data_dir, CCACHE_NAME)

    # first validate boolean-only response
    assert krb5.gss_get_current_cred(ccache_path, False) is None

    with pytest.raises(CallError) as ce:
        krb5.gss_get_current_cred(ccache_path)

    assert ce.value.errmsg == 'Kerberos ticket is expired'


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
                    key = key.strip()

                    match key:
                        case 'kdc' | 'admin_server' | 'kpasswd_server':
                            assert val.strip() in this[key]
                        case 'primary_kdc':
                            assert val.strip() == this[key]
                        case _:
                            raise ValueError(f'{key}: unexpected key in realm config')

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


@contextmanager
def __list_keytab(path: str, data: bytes):
    with open(path, 'wb') as f:
        f.write(data)
        f.flush()

    try:
        entries = krb5.ktutil_list_impl(path)

        # pop out date since ktutil changes the value
        for entry in entries:
            entry.pop('date')

        yield entries

    finally:
        os.unlink(path)


def test__concactenate_keytab(kerberos_data_dir):
    sample_kt = base64.b64decode(SAMPLE_KEYTAB)
    sample_kt2 = base64.b64decode(SAMPLE_KEYTAB2)

    # actual keytab should succeed. Start with single
    new_kt = krb5.concatenate_keytab_data([sample_kt])
    len_sample = 0

    # verify has basically same entries
    with __list_keytab(os.path.join(kerberos_data_dir, 'kt1'), sample_kt) as kt1:
        len_sample = len(kt1)

        with __list_keytab(os.path.join(kerberos_data_dir, 'kt2'), new_kt) as kt2:
            assert kt1 == kt2

    # keytab garbage should fail
    with pytest.raises(RuntimeError):
        assert krb5.concatenate_keytab_data([sample_kt, b'CANARY'])

    # verify concatenated entries have correct count
    new_kt = krb5.concatenate_keytab_data([sample_kt, sample_kt2])
    with __list_keytab(os.path.join(kerberos_data_dir, 'kt3'), new_kt) as kt3:
        with __list_keytab(os.path.join(kerberos_data_dir, 'kt4'), sample_kt2) as kt4:
            assert len(kt3) == len(kt4) + len_sample
