import os
import sys
import time

import pytest

from middlewared.test.integration.assets.pool import dataset

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import make_ws_request
from functions import PUT, POST, GET, DELETE, SSH_TEST, wait_on_job
from auto_config import pool_name, ip, hostname, password, user
from calendar import timegm
from contextlib import contextmanager
from base64 import b64decode
from protocols import nfs_share
from pytest_dependency import depends
from middlewared.test.integration.assets.directory_service import active_directory

try:
    from config import AD_DOMAIN, ADPASSWORD, ADUSERNAME, ADNameServer, AD_COMPUTER_OU
    pytestmark = pytest.mark.ds
except ImportError:
    Reason = 'ADNameServer AD_DOMAIN, ADPASSWORD, or/and ADUSERNAME are missing in config.py"'
    pytestmark = pytest.mark.skip(reason=Reason)

SAMPLE_KEYTAB = "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"

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
    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'etc.generate',
        'params': ['nfsd'],
    })
    error = res.get('error')
    assert error is None, str(error)


def check_export_sec(expected):
    regenerate_exports()
    results = SSH_TEST('cat /etc/exports', user, password, ip)
    assert results['result'] is True, results['stderr']
    exports_config = results['stdout'].strip()
    sec = get_export_sec(exports_config)
    assert sec == expected, exports_config


def parse_krb5_conf(fn, split=None, state=None):
    results = SSH_TEST('cat /etc/krb5.conf', user, password, ip)
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
    payload = {
        "name": ktname,
        "file": SAMPLE_KEYTAB
    }
    results = POST("/kerberos/keytab/", payload)
    assert results.status_code == 200, results.text
    kt_id = results.json()['id']

    try:
        yield results.json()
    finally:
        results = DELETE(f'/kerberos/keytab/id/{kt_id}')
        assert results.status_code == 200, results.text

    results = GET(f'/kerberos/keytab/?name={ktname}')
    assert results.status_code == 200, results.text
    assert len(results.json()) == 0, results.text


@contextmanager
def add_kerberos_realm(realm_name):
    results = POST("/kerberos/realm/",{
        'realm': realm_name,
    })
    assert results.status_code == 200, results.text
    realm_id = results.json()['id']

    try:
        yield results.json()
    finally:
        results = DELETE(f'/kerberos/realm/id/{realm_id}')
        assert results.status_code == 200, results.text


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


def test_02_kerberos_keytab_and_realm(do_ad_connection):
    def krb5conf_parser(krb5conf_lines, idx, entry, state):
        if entry.lstrip() == f"kdc = {SAMPLEDOM_REALM['kdc'][0]}":
            assert krb5conf_lines[idx + 1].lstrip() == f"kdc = {SAMPLEDOM_REALM['kdc'][1]}"
            assert krb5conf_lines[idx + 2].lstrip() == f"kdc = {SAMPLEDOM_REALM['kdc'][2]}"
            state['has_kdc'] = True

        if entry.lstrip() == f"admin_server = {' '.join(SAMPLEDOM_REALM['admin_server'])}":
            state['has_admin_server'] = True

        if entry.lstrip() == f"kpasswd_server = {' '.join(SAMPLEDOM_REALM['kpasswd_server'])}":
            state['has_kpasswd_server'] = True


    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text

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
    results = GET('/kerberos/keytab/?name=AD_MACHINE_ACCOUNT')
    assert results.status_code == 200, results.text
    assert len(results.json()) == 1, results.text
    assert results.json()[0]['file'] != "", "AD_MACHINE_ACCOUNT file empty"
    errstr = ""
    try:
        b64decode(results.json()[0]['file'])
    except Exception as e:
        errstr = e.args[0]

        assert errstr == "", f"b64decode of keytab failed with: {errstr}"

    """
    kerberos_principal_choices lists unique keytab principals in
    the system keytab. AD_MACHINE_ACCOUNT should add more than
    one principal.
    """
    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.keytab.kerberos_principal_choices',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)

    orig_kt_len = len(res['result'])
    assert orig_kt_len != 0, res['result']

    """
    kerberos._klist_test performs a platform-independent verification
    of kerberos ticket.
    """
    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos._klist_test',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)
    assert res['result'] is True

    """
    Test uploading b64encoded sample kerberos keytab included
    at top of this file. In the next series of tests we will
    upload, validate that it was uploaded, and verify that the
    keytab is read back correctly.
    """
    with add_kerberos_keytab("KT2") as new_keytab:
        results = GET('/kerberos/keytab/?name=KT2')
        assert results.status_code == 200, results.text
        assert len(results.json()) == 1, results.text
        assert results.json()[0]['file'] != "", "second keytab file empty"
        errstr = ""
        try:
             b64decode(results.json()[0]['file'])
        except Exception as e:
             errstr = e.args[0]

        assert errstr == "", f"b64decode of keytab failed with: {errstr}"
        assert results.json()[0]['file'] == SAMPLE_KEYTAB, results.text

    """
    AD Join should automatically add a kerberos realm
    for the AD domain.
    """
    results = GET(f'/kerberos/realm/?realm={AD_DOMAIN.upper()}')
    assert results.status_code == 200, results.text
    assert len(results.json()) == 1, results.text

    with add_kerberos_realm(SAMPLEDOM_NAME) as new_realm:
        payload = SAMPLEDOM_REALM.copy()
        payload.pop("realm")
        results = PUT(f"/kerberos/realm/id/{new_realm['id']}/", payload)
        assert results.status_code == 200, results.text

        results = GET(f'/kerberos/realm/?realm={SAMPLEDOM_NAME}')
        assert results.status_code == 200, results.text
        assert len(results.json()) == 1, results.text

        res = results.json()[0].copy()
        res.pop("id")
        assert res == SAMPLEDOM_REALM, results.json()

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

    results = GET(f'/kerberos/realm/?realm={SAMPLEDOM_NAME}')
    assert results.status_code == 200, results.text
    assert len(results.json()) == 0, results.text


def test_03_kerberos_krbconf(do_ad_connection):
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

        pam_closed = False
        for entry in sec.splitlines():
            if state['section'] == 'appdefaults' and not pam_closed:
                pam_closed = entry.lstrip().startswith('}')
                continue

            if entry.strip() == state['to_check']:
                state['found'] = True
                break

    """
    Test of more complex auxiliary parameter parsing that allows
    users to override our defaults.
    """
    results = PUT("/kerberos/", {"appdefaults_aux": APPDEFAULTS_PAM_OVERRIDE})
    assert results.status_code == 200, results.text

    iter_state = {
        'has_forwardable': False,
        'has_ticket_lifetime': False
    }

    output = parse_krb5_conf(parser_1, split='[', state=iter_state)

    assert iter_state['has_forwardable'] is True, output
    assert iter_state['has_ticket_lifetime'] is True, output

    results = PUT("/kerberos/", {"appdefaults_aux": "encrypt = true"})
    assert results.status_code == 200, results.text

    iter_state = {
        'section': 'appdefaults',
        'found': False,
        'to_check': 'encrypt = true'
    }

    output = parse_krb5_conf(parse_section, split='[', state=iter_state)
    assert iter_state['found'] is True, output

    results = PUT("/kerberos/", {"libdefaults_aux": "scan_interfaces = true"})
    assert results.status_code == 200, results.text

    iter_state = {
        'section': 'libdefaults',
        'found': False,
        'to_check': 'scan_interfaces = true'
    }
    output = parse_krb5_conf(parse_section, split='[', state=iter_state)
    assert iter_state['found'] is True, output

    # reset to defaults
    results = PUT("/kerberos/", {"appdefaults_aux": "", "libdefaults_aux": ""})
    assert results.status_code == 200, results.text

    # check that parser raises validation errors
    results = PUT("/kerberos/", {"appdefaults_aux": "canary = true"})
    assert results.status_code == 422, results.text

    results = PUT("/kerberos/", {"libdefaults_aux": "canary = true"})
    assert results.status_code == 422, results.text


def test_04_kerberos_nfs4(do_ad_connection):
    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.keytab.has_nfs_principal',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)
    assert res['result'] is False

    with dataset('AD_NFS') as ds:
        with nfs_share(f'/mnt/{ds}', options={'comment': 'KRB Test Share'}) as share:
            payload = {"protocols": ["NFSV3", "NFSV4"]}
            results = PUT("/nfs/", payload)
            assert results.status_code == 200, results.text

            """
            First NFS exports check. In this situation we are joined to
            AD and therefore have a keytab. We do not at this point have
            an NFS SPN entry. Expected security with v4 is:
            "V4: / -sec=sys"
            """
            check_export_sec('sec=sys')

            payload = {"v4_krb": True}
            results = PUT("/nfs/", payload)
            assert results.status_code == 200, results.text

            """
            Force AD plugin to add NFS spns for further testing.
            This should still be possible because the initial domain
            join involved obtaining a kerberos ticket with elevated
            privileges.
            """
            results = GET("/smb/")
            assert results.status_code == 200, results.text
            netbios_name = results.json()['netbiosname_local']

            res = make_ws_request(ip, {
                'msg': 'method',
                'method': 'activedirectory.add_nfs_spn',
                'params': [netbios_name, AD_DOMAIN],
            })
            error = res.get('error')
            assert error is None, str(error)

            job_id = res['result']
            job_status = wait_on_job(job_id, 180)
            assert job_status['state'] == 'SUCCESS', str(job_status['results'])

            res = make_ws_request(ip, {
                'msg': 'method',
                'method': 'kerberos.keytab.has_nfs_principal',
                'params': [],
            })
            error = res.get('error')
            assert error is None, str(error)
            assert res['result'] is True

            res = make_ws_request(ip, {
                'msg': 'method',
                'method': 'smb.getparm',
                'params': ['winbind use default domain', 'GLOBAL'],
            })
            error = res.get('error')
            assert error is None, str(error)
            assert res['result'] == 'true'

            """
            Second NFS exports check. We now have an NFS SPN entry
            Expected security with is:
            "V4: / -sec=krb5:krb5i:krb5p"
            """
            check_export_sec('sec=krb5:krb5i:krb5p')

            """
            v4_krb_enabled should still be True after this
            disabling v4_krb because we still have an nfs
            service principal in our keytab.
            """
            payload = {"v4_krb": False}
            results = PUT("/nfs/", payload)
            assert results.status_code == 200, results.text
            v4_krb_enabled = results.json()['v4_krb_enabled']
            assert v4_krb_enabled is True, results.text

            """
            Third NFS exports check. We now have an NFS SPN entry
            but v4_krb is disabled.
            Expected security with is:
            "V4: / -sec=sys:krb5:krb5i:krb5p"
            """
            check_export_sec('sec=sys:krb5:krb5i:krb5p')


def test_05_verify_nfs_krb_disabled(request):
    """
    This test checks that we no longer are flagged as having
    v4_krb_enabled now that we are not joined to AD.
    """
    results = GET("/nfs")
    assert results.status_code == 200, results.text
    v4_krb_enabled = results.json()['v4_krb_enabled']
    assert v4_krb_enabled is False, results.text


def test_06_kerberos_ticket_management(do_ad_connection):
    depends(do_ad_connection[0], ["SET_DNS"])

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.klist',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)

    klist_out = res['result']
    assert klist_out['default_principal'].startswith(hostname.upper()), str(klist_out)
    assert klist_out['ticket_cache']['type'] == 'FILE'
    assert klist_out['ticket_cache']['name'] == 'SYSTEM'
    assert len(klist_out['tickets']) != 0

    to_check = None
    for tkt in klist_out['tickets']:
        if tkt['server'].startswith('krbtgt'):
            to_check = tkt

    assert to_check is not None, str(klist_out)
    assert 'RENEWABLE' in to_check['flags']

    results = GET('/core/get_jobs/?method=kerberos.wait_for_renewal')
    assert results.status_code == 200, results.text
    assert len(results.json()) != 0, results.text

    renewal_job = results.json()[0]
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
    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.get_cred',
        'params': [{
            'dstype': 'DS_TYPE_ACTIVEDIRECTORY',
            'conf': {
                'domainname': AD_DOMAIN,
                'kerberos_principal': f'{hostname.upper()}$@{AD_DOMAIN.upper()}'
            }
        }],
    })
    error = res.get('error')
    assert error is None, str(error)
    cred = res['result']

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'activedirectory.domain_info',
        'params': [AD_DOMAIN]
    })
    error = res.get('error')
    assert error is None, str(error)
    kdc = res['result']['KDC server']

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.do_kinit',
        'params': [{
            'krb5_cred': cred,
            'kinit-options': {
                'kdc_override': {'domain': AD_DOMAIN.upper(), 'kdc': kdc},
                'lifetime': 10
            }
        }],
    })
    error = res.get('error')
    assert error is None, str(error)

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.klist',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)

    klist2_out = res['result']
    assert klist2_out['default_principal'].startswith(hostname.upper())
    assert klist2_out['ticket_cache']['type'] == 'FILE'
    assert klist2_out['ticket_cache']['name'] == 'SYSTEM'
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
    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.renew',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.klist',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)

    klist3_out = res['result']
    assert klist3_out['default_principal'].startswith(hostname.upper())
    assert klist3_out['ticket_cache']['type'] == 'FILE'
    assert klist3_out['ticket_cache']['name'] == 'SYSTEM'
    assert len(klist3_out['tickets']) != 0

    to_check3 = None
    for tkt in klist3_out['tickets']:
        if tkt['server'].startswith('krbtgt'):
            to_check3 = tkt

    assert to_check3 is not None, str(klist3_out)
    assert to_check3['expires'] != to_check2['expires']
    assert 'RENEWABLE' in to_check3['flags']


def test_44_check_ad_machine_account_deleted_after_ad_leave(request):
    results = GET('/kerberos/keytab/?name=AD_MACHINE_ACCOUNT')
    assert results.status_code == 200, results.text
    assert len(results.json()) == 0
