import os
import sys
import time

import pytest

from middlewared.test.integration.assets.pool import dataset

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import SSH_TEST
from auto_config import hostname, password, user
from calendar import timegm
from contextlib import contextmanager
from base64 import b64decode
from protocols import nfs_share
from pytest_dependency import depends
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.utils import call
from middlewared.test.integration.assets.directory_service import active_directory

try:
    from config import AD_DOMAIN, ADPASSWORD, ADUSERNAME, ADNameServer, AD_COMPUTER_OU
except ImportError:
    Reason = 'ADNameServer AD_DOMAIN, ADPASSWORD, or/and ADUSERNAME are missing in config.py"'
    pytestmark = pytest.mark.skip(reason=Reason)

SAMPLE_KEYTAB = "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"  # noqa

SAMPLEDOM_NAME = "CANARY.FUN"
SAMPLEDOM_REALM = {
    "realm": SAMPLEDOM_NAME,
    "kdc": ["169.254.100.1", "169.254.100.2", "169.254.100.3"],
    "admin_server": ["169.254.100.10", "169.254.100.11", "169.254.100.12"],
    "kpasswd_server": ["169.254.100.20", "169.254.100.21", "169.254.100.22"],
}


APPDEFAULTS_PAM_OVERRIDE = """
pam = {
    forwardable = false
    ticket_lifetime = 36000
}
"""


def get_export_sec(exports_config):
    sec_entry = None
    for entry in exports_config.splitlines():
        if not entry.startswith("\t"):
            continue

        line = entry.strip().split("(")[1]
        sec_entry = line.split(",")[0]
        break

    return sec_entry


def regenerate_exports():
    # NFS service isn't running for these tests
    # and so exports aren't updated. Force the update.
    call('etc.generate', 'nfsd')


def check_export_sec(expected):
    regenerate_exports()
    results = SSH_TEST('cat /etc/exports', user, password)
    assert results['result'] is True, results['stderr']
    exports_config = results['stdout'].strip()
    sec = get_export_sec(exports_config)
    assert sec == expected, exports_config


def parse_krb5_conf(fn, split=None, state=None):
    results = SSH_TEST('cat /etc/krb5.conf', user, password)
    assert results['result'] is True, results['output']

    if split:
        krb5conf_lines = results['stdout'].split(split)
    else:
        krb5conf_lines = results['stdout'].splitlines()

    for idx, entry in enumerate(krb5conf_lines):
        fn(krb5conf_lines, idx, entry, state)

    return results['output']


@contextmanager
def add_kerberos_keytab(ktname):
    kt = call('kerberos.keytab.create', {
        "name": ktname,
        "file": SAMPLE_KEYTAB
    })
    try:
        yield kt
    finally:
        call('kerberos.keytab.delete', kt['id'])


@contextmanager
def add_kerberos_realm(realm_name):
    realm = call('kerberos.realm.create', {
        'realm': realm_name,
    })
    try:
        yield realm
    finally:
        call('kerberos.realm.delete', realm['id'])


@pytest.fixture(scope="function")
def do_ad_connection(request):
    with active_directory(
        AD_DOMAIN,
        ADUSERNAME,
        ADPASSWORD,
        netbiosname=hostname,
        createcomputer=AD_COMPUTER_OU,
    ) as ad:
        yield (request, ad)


def test_kerberos_keytab_and_realm(do_ad_connection):

    def krb5conf_parser(krb5conf_lines, idx, entry, state):
        if entry.lstrip() == f"kdc = {SAMPLEDOM_REALM['kdc'][0]}":
            assert krb5conf_lines[idx + 1].lstrip() == f"kdc = {SAMPLEDOM_REALM['kdc'][1]}"
            assert krb5conf_lines[idx + 2].lstrip() == f"kdc = {SAMPLEDOM_REALM['kdc'][2]}"
            state['has_kdc'] = True

        if entry.lstrip() == f"admin_server = {SAMPLEDOM_REALM['admin_server'][0]}":
            assert krb5conf_lines[idx + 1].lstrip() == f"admin_server = {SAMPLEDOM_REALM['admin_server'][1]}"
            assert krb5conf_lines[idx + 2].lstrip() == f"admin_server = {SAMPLEDOM_REALM['admin_server'][2]}"
            state['has_admin_server'] = True

        if entry.lstrip() == f"kpasswd_server = {SAMPLEDOM_REALM['kpasswd_server'][0]}":
            assert krb5conf_lines[idx + 1].lstrip() == f"kpasswd_server = {SAMPLEDOM_REALM['kpasswd_server'][1]}"
            assert krb5conf_lines[idx + 2].lstrip() == f"kpasswd_server = {SAMPLEDOM_REALM['kpasswd_server'][2]}"
            state['has_kpasswd_server'] = True

    call('directoryservices.status')['status'] == 'HEALTHY'
    """
    The keytab in this case is a b64encoded keytab file.
    AD_MACHINE_ACCOUNT is automatically generated during domain
    join and uploaded into our configuration database. This
    test checks for its presence and that it's validly b64 encoded.
    The process of decoding and adding to system keytab is tested
    in later kerberos tests. "kerberos.start" will decode, write
    to system keytab, and kinit. So in this case, proper function
    can be determined by printing contents of system keytab and
    verifying that we were able to get a kerberos ticket.
    """
    kt = call('kerberos.keytab.query', [['name', '=', 'AD_MACHINE_ACCOUNT']], {'get': True})
    b64decode(kt['file'])

    """
    kerberos_principal_choices lists unique keytab principals in
    the system keytab. AD_MACHINE_ACCOUNT should add more than
    one principal.
    """
    orig_kt = call('kerberos.keytab.kerberos_principal_choices')
    assert orig_kt != []

    """
    kerberos.check_ticket performs a platform-independent verification
    of kerberos ticket.
    """
    call('kerberos.check_ticket')

    """
    Test uploading b64encoded sample kerberos keytab included
    at top of this file. In the next series of tests we will
    upload, validate that it was uploaded, and verify that the
    keytab is read back correctly.
    """
    with add_kerberos_keytab('KT2'):
        kt2 = call('kerberos.keytab.query', [['name', '=', 'KT2']], {'get': True})
        b64decode(kt2['file'])
        assert kt2['file'] == SAMPLE_KEYTAB

    """
    AD Join should automatically add a kerberos realm
    for the AD domain.
    """
    call('kerberos.realm.query', [['realm', '=', AD_DOMAIN.upper()]], {'get': True})

    with add_kerberos_realm(SAMPLEDOM_NAME) as new_realm:
        payload = SAMPLEDOM_REALM.copy()
        payload.pop("realm")
        call('kerberos.realm.update', new_realm['id'], payload)

        r = call('kerberos.realm.query', [['realm', '=', SAMPLEDOM_NAME]], {'get': True})
        r.pop('id')
        assert r == SAMPLEDOM_REALM

        # Verify realms properly added to krb5.conf
        iter_state = {
            'has_kdc': False,
            'has_admin_server': False,
            'has_kpasswd_server': False
        }
        output = parse_krb5_conf(krb5conf_parser, state=iter_state)

        assert iter_state['has_kdc'] is True, output
        assert iter_state['has_admin_server'] is True, output
        assert iter_state['has_kpasswd_server'] is True, output

    assert len(call('kerberos.realm.query', [['realm', '=', SAMPLEDOM_NAME]])) == 0


def test_kerberos_krbconf(do_ad_connection):
    def parser_1(unused, idx, sec, state):
        if not sec.startswith("appdefaults"):
            return

        for entry in sec.splitlines():
            if entry.lstrip().startswith('}'):
                break

            if entry.strip() == "forwardable = false":
                state['has_forwardable'] = True

            if entry.strip() == "ticket_lifetime = 36000":
                state['has_ticket_lifetime'] = True

    def parse_section(unused, idx, sec, state):
        if not sec.startswith(state['section']):
            return

        for entry in sec.splitlines():
            if entry.strip() == state['to_check']:
                state['found'] = True
                break

    """
    Test of more complex auxiliary parameter parsing that allows
    users to override our defaults.
    """

    call('kerberos.update', {'appdefaults_aux': APPDEFAULTS_PAM_OVERRIDE})

    iter_state = {
        'has_forwardable': False,
        'has_ticket_lifetime': False
    }

    output = parse_krb5_conf(parser_1, split='[', state=iter_state)

    assert iter_state['has_forwardable'] is True, output
    assert iter_state['has_ticket_lifetime'] is True, output

    call('kerberos.update', {'appdefaults_aux': 'encrypt = true'})

    iter_state = {
        'section': 'appdefaults',
        'found': False,
        'to_check': 'encrypt = true'
    }

    output = parse_krb5_conf(parse_section, split='[', state=iter_state)
    assert iter_state['found'] is True, output

    call('kerberos.update', {'libdefaults_aux': 'rdns = true'})

    iter_state = {
        'section': 'libdefaults',
        'found': False,
        'to_check': 'rdns = true'
    }
    output = parse_krb5_conf(parse_section, split='[', state=iter_state)
    assert iter_state['found'] is True, output


def test_invalid_aux():
    call('kerberos.update', {'appdefaults_aux': '', 'libdefaults_aux': ''})

    # check that parser raises validation errors
    with pytest.raises(ValidationErrors):
        call('kerberos.update', {'appdefaults_aux': 'canary = true'})

    with pytest.raises(ValidationErrors):
        call('kerberos.update', {'libdefaults_aux': 'canary = true'})


def test_kerberos_nfs4(do_ad_connection):
    assert call('kerberos.keytab.has_nfs_principal') is True

    with dataset('AD_NFS') as ds:
        with nfs_share(f'/mnt/{ds}', options={'comment': 'KRB Test Share'}):
            call('nfs.update', {"protocols": ["NFSV3", "NFSV4"]})

            """
            First NFS exports check. In this situation we are joined to
            AD and therefore have a keytab with NFS entry

            Expected security is:
            "V4: / -sec=sys:krb5:krb5i:krb5p"
            """
            check_export_sec('sec=sys:krb5:krb5i:krb5p')

            call('nfs.update', {"v4_krb": True})

            """
            Second NFS exports check. We now have an NFS SPN entry
            Expected security is:
            "V4: / -sec=krb5:krb5i:krb5p"
            """
            check_export_sec('sec=krb5:krb5i:krb5p')

            """
            v4_krb_enabled should still be True after this
            disabling v4_krb because we still have an nfs
            service principal in our keytab.
            """
            data = call('nfs.update', {'v4_krb': False})
            assert data['v4_krb_enabled'] is True, str(data)

            """
            Third NFS exports check. We now have an NFS SPN entry
            but v4_krb is disabled.
            Expected security is:
            "V4: / -sec=sys:krb5:krb5i:krb5p"
            """
            check_export_sec('sec=sys:krb5:krb5i:krb5p')


def test_verify_nfs_krb_disabled():
    """
    This test checks that we no longer are flagged as having
    v4_krb_enabled now that we are not joined to AD.
    """
    assert call('nfs.config')['v4_krb_enabled'] is False


def test_kerberos_ticket_management(do_ad_connection):
    klist_out = call('kerberos.klist')
    assert klist_out['default_principal'].startswith(hostname.upper()), str(klist_out)
    assert klist_out['ticket_cache']['type'] == 'FILE'
    assert klist_out['ticket_cache']['name'] == '/var/run/middleware/krb5cc_0'
    assert len(klist_out['tickets']) != 0

    to_check = None
    for tkt in klist_out['tickets']:
        if tkt['server'].startswith('krbtgt'):
            to_check = tkt

    assert to_check is not None, str(klist_out)
    assert 'RENEWABLE' in to_check['flags']

    renewal_job = call('core.get_jobs', [['method', '=', 'kerberos.wait_for_renewal']], {'get': True})
    time_string = renewal_job['description'].split(':', 1)[1]
    timestamp = timegm(time.strptime(time_string, " %m/%d/%y %H:%M:%S %Z"))
    assert tkt['expires'] == timestamp, str({"time": time_string, "ticket": tkt})

    """
    Now we forcibly set a short-lived kerberos ticket using
    our kerberos principal and then call `kerberos.renew` to renew it

    Since we're doing this in an enviroment where sysvol replication may be
    slower than our tests, we need to insert a KDC override to have us only
    talk to the KDC we used to initially join AD.
    """
    cred = call('kerberos.get_cred',  {
        'dstype': 'DS_TYPE_ACTIVEDIRECTORY',
        'conf': {
            'domainname': AD_DOMAIN,
            'kerberos_principal': f'{hostname.upper()}$@{AD_DOMAIN.upper()}'
        }
    })

    call('kerberos.do_kinit', {
        'krb5_cred': cred,
        'kinit-options': {
            'kdc_override': {'domain': AD_DOMAIN.upper(), 'kdc': ADNameServer},
            'lifetime': 10
        }
    })

    klist2_out = call('kerberos.klist')
    assert klist2_out['default_principal'].startswith(hostname.upper())
    assert klist2_out['ticket_cache']['type'] == 'FILE'
    assert klist2_out['ticket_cache']['name'] == '/var/run/middleware/krb5cc_0'
    assert len(klist2_out['tickets']) != 0

    to_check2 = None
    for tkt in klist2_out['tickets']:
        if tkt['server'].startswith('krbtgt'):
            to_check2 = tkt

    assert to_check2 is not None, str(klist2_out)
    assert to_check2['expires'] != to_check['expires']
    assert 'RENEWABLE' in to_check2['flags']

    """
    kerberos.renew should detect the remaining life on ticket is less
    than our safe margin and automatically renew it.
    """
    call('kerberos.renew')
    klist3_out = call('kerberos.klist')
    assert klist3_out['default_principal'].startswith(hostname.upper())
    assert klist3_out['ticket_cache']['type'] == 'FILE'
    assert klist3_out['ticket_cache']['name'] == '/var/run/middleware/krb5cc_0'
    assert len(klist3_out['tickets']) != 0

    to_check3 = None
    for tkt in klist3_out['tickets']:
        if tkt['server'].startswith('krbtgt'):
            to_check3 = tkt

    assert to_check3 is not None, str(klist3_out)
    assert to_check3['expires'] != to_check2['expires']
    assert 'RENEWABLE' in to_check3['flags']


def test_check_ad_machine_account_deleted_after_ad_leave(request):
    assert len(call('kerberos.keytab.query')) == 0
