#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
import json
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE, SSH_TEST, wait_on_job
from auto_config import ip, hostname, password, user
from base64 import b64decode
from pytest_dependency import depends

try:
    from config import AD_DOMAIN, ADPASSWORD, ADUSERNAME, ADNameServer
except ImportError:
    Reason = 'ADNameServer AD_DOMAIN, ADPASSWORD, or/and ADUSERNAME are missing in config.py"'
    pytestmark = pytest.mark.skip(reason=Reason)
else:
    from auto_config import dev_test
    # comment pytestmark for development testing with --dev-test
    pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

SAMPLE_KEYTAB = "BQIAAABTAAIAC0hPTUVET00uRlVOABFyZXN0cmljdGVka3JiaG9zdAASdGVzdDQ5LmhvbWVkb20uZnVuAAAAAV8kEroBAAEACDHN3Kv9WKLLAAAAAQAAAAAAAABHAAIAC0hPTUVET00uRlVOABFyZXN0cmljdGVka3JiaG9zdAAGVEVTVDQ5AAAAAV8kEroBAAEACDHN3Kv9WKLLAAAAAQAAAAAAAABTAAIAC0hPTUVET00uRlVOABFyZXN0cmljdGVka3JiaG9zdAASdGVzdDQ5LmhvbWVkb20uZnVuAAAAAV8kEroBAAMACDHN3Kv9WKLLAAAAAQAAAAAAAABHAAIAC0hPTUVET00uRlVOABFyZXN0cmljdGVka3JiaG9zdAAGVEVTVDQ5AAAAAV8kEroBAAMACDHN3Kv9WKLLAAAAAQAAAAAAAABbAAIAC0hPTUVET00uRlVOABFyZXN0cmljdGVka3JiaG9zdAASdGVzdDQ5LmhvbWVkb20uZnVuAAAAAV8kEroBABEAEBDQOH+tKYCuoedQ53WWKFgAAAABAAAAAAAAAE8AAgALSE9NRURPTS5GVU4AEXJlc3RyaWN0ZWRrcmJob3N0AAZURVNUNDkAAAABXyQSugEAEQAQENA4f60pgK6h51DndZYoWAAAAAEAAAAAAAAAawACAAtIT01FRE9NLkZVTgARcmVzdHJpY3RlZGtyYmhvc3QAEnRlc3Q0OS5ob21lZG9tLmZ1bgAAAAFfJBK6AQASACCKZTjTnrjT30jdqAG2QRb/cFyTe9kzfLwhBAm5QnuMiQAAAAEAAAAAAAAAXwACAAtIT01FRE9NLkZVTgARcmVzdHJpY3RlZGtyYmhvc3QABlRFU1Q0OQAAAAFfJBK6AQASACCKZTjTnrjT30jdqAG2QRb/cFyTe9kzfLwhBAm5QnuMiQAAAAEAAAAAAAAAWwACAAtIT01FRE9NLkZVTgARcmVzdHJpY3RlZGtyYmhvc3QAEnRlc3Q0OS5ob21lZG9tLmZ1bgAAAAFfJBK6AQAXABAcyjciCUnM9DmiyiPO4VIaAAAAAQAAAAAAAABPAAIAC0hPTUVET00uRlVOABFyZXN0cmljdGVka3JiaG9zdAAGVEVTVDQ5AAAAAV8kEroBABcAEBzKNyIJScz0OaLKI87hUhoAAAABAAAAAAAAAEYAAgALSE9NRURPTS5GVU4ABGhvc3QAEnRlc3Q0OS5ob21lZG9tLmZ1bgAAAAFfJBK6AQABAAgxzdyr/ViiywAAAAEAAAAAAAAAOgACAAtIT01FRE9NLkZVTgAEaG9zdAAGVEVTVDQ5AAAAAV8kEroBAAEACDHN3Kv9WKLLAAAAAQAAAAAAAABGAAIAC0hPTUVET00uRlVOAARob3N0ABJ0ZXN0NDkuaG9tZWRvbS5mdW4AAAABXyQSugEAAwAIMc3cq/1YossAAAABAAAAAAAAADoAAgALSE9NRURPTS5GVU4ABGhvc3QABlRFU1Q0OQAAAAFfJBK6AQADAAgxzdyr/ViiywAAAAEAAAAAAAAATgACAAtIT01FRE9NLkZVTgAEaG9zdAASdGVzdDQ5LmhvbWVkb20uZnVuAAAAAV8kEroBABEAEBDQOH+tKYCuoedQ53WWKFgAAAABAAAAAAAAAEIAAgALSE9NRURPTS5GVU4ABGhvc3QABlRFU1Q0OQAAAAFfJBK6AQARABAQ0Dh/rSmArqHnUOd1lihYAAAAAQAAAAAAAABeAAIAC0hPTUVET00uRlVOAARob3N0ABJ0ZXN0NDkuaG9tZWRvbS5mdW4AAAABXyQSugEAEgAgimU40564099I3agBtkEW/3Bck3vZM3y8IQQJuUJ7jIkAAAABAAAAAAAAAFIAAgALSE9NRURPTS5GVU4ABGhvc3QABlRFU1Q0OQAAAAFfJBK6AQASACCKZTjTnrjT30jdqAG2QRb/cFyTe9kzfLwhBAm5QnuMiQAAAAEAAAAAAAAATgACAAtIT01FRE9NLkZVTgAEaG9zdAASdGVzdDQ5LmhvbWVkb20uZnVuAAAAAV8kEroBABcAEBzKNyIJScz0OaLKI87hUhoAAAABAAAAAAAAAEIAAgALSE9NRURPTS5GVU4ABGhvc3QABlRFU1Q0OQAAAAFfJBK6AQAXABAcyjciCUnM9DmiyiPO4VIaAAAAAQAAAAAAAAA1AAEAC0hPTUVET00uRlVOAAdURVNUNDkkAAAAAV8kEroBAAEACDHN3Kv9WKLLAAAAAQAAAAAAAAA1AAEAC0hPTUVET00uRlVOAAdURVNUNDkkAAAAAV8kEroBAAMACDHN3Kv9WKLLAAAAAQAAAAAAAAA9AAEAC0hPTUVET00uRlVOAAdURVNUNDkkAAAAAV8kEroBABEAEBDQOH+tKYCuoedQ53WWKFgAAAABAAAAAAAAAE0AAQALSE9NRURPTS5GVU4AB1RFU1Q0OSQAAAABXyQSugEAEgAgimU40564099I3agBtkEW/3Bck3vZM3y8IQQJuUJ7jIkAAAABAAAAAAAAAD0AAQALSE9NRURPTS5GVU4AB1RFU1Q0OSQAAAABXyQSugEAFwAQHMo3IglJzPQ5osojzuFSGgAAAAEAAAAA"

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
WORKGROUP = None
nameserver1 = None
nameserver2 = None

job_id = None
dom_id = None
job_status = None


@pytest.mark.dependency(name="GOT_DNS")
def test_01_get_nameserver1_and_nameserver2():
    global nameserver1
    results = GET("/network/configuration/")
    assert results.status_code == 200, results.text
    nameserver1 = results.json()['nameserver1']


@pytest.mark.dependency(name="SET_DNS")
def test_02_set_nameserver_for_ad(request):
    depends(request, ["GOT_DNS"])
    global payload
    payload = {
        "nameserver1": ADNameServer,
    }
    global results
    results = PUT("/network/configuration/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


@pytest.mark.dependency(name="AD_ENABLED")
def test_03_enabling_activedirectory(request):
    depends(request, ["SET_DNS"])
    global payload, results, job_id
    payload = {
        "bindpw": ADPASSWORD,
        "bindname": ADUSERNAME,
        "domainname": AD_DOMAIN,
        "netbiosname": hostname,
        "dns_timeout": 15,
        "verbose_logging": True,
        "enable": True
    }
    results = PUT("/activedirectory/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()['job_id']


@pytest.mark.dependency(name="JOINED_AD")
def test_04_verify_the_job_id_is_successful(request):
    depends(request, ["AD_ENABLED"])
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_05_verify_activedirectory_do_not_leak_password_in_middleware_log(request):
    depends(request, ["AD_ENABLED", "ssh_password"], scope="session")
    cmd = f"""grep -R "{ADPASSWORD}" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


@pytest.mark.dependency(name="AD_IS_HEALTHY")
def test_06_get_activedirectory_state(request):
    """
    Issue no-effect operation on DC's netlogon share to
    verify that domain join is alive.
    """
    depends(request, ["JOINED_AD"])
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text


@pytest.mark.dependency(name="AD_MACHINE_ACCOUNT_ADDED")
def test_07_check_ad_machine_account_added(request):
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
    depends(request, ["AD_IS_HEALTHY"])
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


def test_08_system_keytab_verify(request):
    """
    kerberos_principal_choices lists unique keytab principals in
    the system keytab. AD_MACHINE_ACCOUNT should add more than
    one principal.
    """
    depends(request, ["AD_MACHINE_ACCOUNT_ADDED", "ssh_password"], scope="session")
    global orig_kt_len
    cmd = 'midclt call kerberos.keytab.kerberos_principal_choices'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    if results['result'] is True:
        orig_kt_len = len(json.loads(results['output'].strip()))
        assert orig_kt_len != 0, results['output']


@pytest.mark.dependency(name="KRB5_IS_HEALTHY")
def test_09_ticket_verify(request):
    """
    kerberos._klist_test performs a platform-independent verification
    of kerberos ticket.
    """
    depends(request, ["AD_MACHINE_ACCOUNT_ADDED", "ssh_password"], scope="session")
    cmd = 'midclt call kerberos._klist_test'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['output'].strip() == 'True'


@pytest.mark.dependency(name="SECOND_KEYTAB")
def test_10_add_second_keytab_to_server(request):
    """
    Test uploading b64encoded sample kerberos keytab included
    at top of this file. In the next series of tests we will
    upload, validate that it was uploaded, and verify that the
    keytab is read back correctly.
    """
    global kt_id
    depends(request, ["AD_MACHINE_ACCOUNT_ADDED"])
    payload = {
        "name": "KT2",
        "file": SAMPLE_KEYTAB
    }
    results = POST("/kerberos/keytab/", payload)
    assert results.status_code == 200, results.text
    kt_id = results.json()['id']


def test_11_second_keytab_added(request):
    depends(request, ["SECOND_KEYTAB"])
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


def test_12_second_keytab_system_keytab_verify(request):
    """
    kerberos_principal_choices lists unique keytab principals in
    the system keytab. AD_MACHINE_ACCOUNT should add more than
    one principal.
    """
    depends(request, ["SECOND_KEYTAB", "ssh_password"], scope="session")
    cmd = 'midclt call kerberos.keytab.kerberos_principal_choices'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    if results['result'] is True:
        new_kt_len = len(json.loads(results['output'].strip()))
        assert new_kt_len > orig_kt_len, results['output']


def test_13_delete_second_keytab(request):
    depends(request, ["SECOND_KEYTAB"])
    results = DELETE(f'/kerberos/keytab/id/{kt_id}')
    assert results.status_code == 200, results.text

    # double-check that it was actually deleted
    results = GET('/kerberos/keytab/?name=KT2')
    assert results.status_code == 200, results.text
    assert len(results.json()) == 0, results.text


def test_14_kerberos_realm_added(request):
    """
    AD Join should automatically add a kerberos realm
    for the AD domain.
    """
    depends(request, ["KRB5_IS_HEALTHY"])
    results = GET(f'/kerberos/realm/?realm={AD_DOMAIN.upper()}')
    assert results.status_code == 200, results.text
    assert len(results.json()) == 1, results.text


@pytest.mark.dependency(name="SECOND_REALM")
def test_15_add_second_kerberos_realm(request):
    depends(request, ["KRB5_IS_HEALTHY"])
    global realm_id
    payload = {
        "realm": SAMPLEDOM_NAME,
    }
    results = POST("/kerberos/realm/", payload)
    assert results.status_code == 200, results.text
    realm_id = results.json()['id']


def test_16_second_realm_update(request):
    depends(request, ["SECOND_REALM"])
    payload = SAMPLEDOM_REALM.copy()
    payload.pop("realm")
    results = PUT(f"/kerberos/realm/id/{realm_id}/", payload)
    assert results.status_code == 200, results.text


def test_17_second_realm_update_verify(request):
    depends(request, ["SECOND_REALM"])
    results = GET(f'/kerberos/realm/?realm={SAMPLEDOM_NAME}')
    assert results.status_code == 200, results.text
    assert len(results.json()) == 1, results.text
    if results.json():
        res = results.json()[0].copy()
        res.pop("id")
        assert res == SAMPLEDOM_REALM, results.json()


def test_18_second_realm_krb5_conf_verify(request):
    """
    kerberos_principal_choices lists unique keytab principals in
    the system keytab. AD_MACHINE_ACCOUNT should add more than
    one principal.
    """
    depends(request, ["SECOND_REALM", "ssh_password"], scope="session")
    has_kdc = False
    has_admin_server = False
    has_kpasswd_server = False
    cmd = 'cat /etc/krb5.conf'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    if results['result'] is True:
        for entry in results['output'].splitlines():
            if entry.lstrip() == f"kdc = {' '.join(SAMPLEDOM_REALM['kdc'])}":
                has_kdc = True

            if entry.lstrip() == f"admin_server = {' '.join(SAMPLEDOM_REALM['admin_server'])}":
                has_admin_server = True

            if entry.lstrip() == f"kpasswd_server = {' '.join(SAMPLEDOM_REALM['kpasswd_server'])}":
                has_kpasswd_server = True

    assert has_kdc is True, results['output']
    assert has_admin_server is True, results['output']
    assert has_kpasswd_server is True, results['output']


def test_19_second_realm_delete(request):
    depends(request, ["SECOND_REALM"])
    results = DELETE(f'/kerberos/realm/id/{realm_id}')
    assert results.status_code == 200, results.text

    # double-check that it was actually deleted
    results = GET(f'/kerberos/realm/?realm={SAMPLEDOM_NAME}')
    assert results.status_code == 200, results.text
    assert len(results.json()) == 0, results.text


def test_20_base_krb5_pam_override(request):
    """
    Test of more complex auxiliary parameter parsing that allows
    users to override our defaults.
    """
    depends(request, ["KRB5_IS_HEALTHY"])
    results = PUT("/kerberos/", {"appdefaults_aux": APPDEFAULTS_PAM_OVERRIDE})
    assert results.status_code == 200, results.text


def test_21_base_krb5_pam_verify(request):
    depends(request, ["KRB5_IS_HEALTHY", "ssh_password"], scope="session")
    has_forwardable = False
    has_ticket_lifetime = False

    cmd = 'cat /etc/krb5.conf'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    if not results['result'] is True:
        return

    # First split krb5.conf into sections
    for sec in results['output'].split('['):
        if not sec.startswith("appdefaults"):
            continue

        for entry in sec.splitlines():
            if entry.lstrip().startswith('}'):
                break

            if entry.strip() == "forwardable = false":
                has_forwardable = True

            if entry.strip() == "ticket_lifetime = 36000":
                has_ticket_lifetime = True

    assert has_forwardable is True, results['output']
    assert has_ticket_lifetime is True, results['output']


def test_22_base_krb5_appdefaults_add(request):
    depends(request, ["KRB5_IS_HEALTHY"])
    results = PUT("/kerberos/", {"appdefaults_aux": "encrypt = true"})
    assert results.status_code == 200, results.text


def test_23_base_krb5_appdefaults_verify(request):
    depends(request, ["KRB5_IS_HEALTHY", "ssh_password"], scope="session")
    has_aux = False

    cmd = 'cat /etc/krb5.conf'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    if not results['result'] is True:
        return

    # First split krb5.conf into sections
    for sec in results['output'].split('['):
        if not sec.startswith("appdefaults"):
            continue

        pam_closed = False
        for entry in sec.splitlines():
            if not pam_closed:
                pam_closed = entry.lstrip().startswith('}')
                continue

            if entry.strip() == "encrypt = true":
                has_aux = True
                break

    assert has_aux is True, results['output']


def test_24_base_krb5_libdefaults_add(request):
    depends(request, ["KRB5_IS_HEALTHY"])
    results = PUT("/kerberos/", {"libdefaults_aux": "scan_interfaces = true"})
    assert results.status_code == 200, results.text


def test_25_base_krb5_libdefaults_verify(request):
    depends(request, ["KRB5_IS_HEALTHY", "ssh_password"], scope="session")
    has_aux = False

    cmd = 'cat /etc/krb5.conf'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    if not results['result'] is True:
        return

    # First split krb5.conf into sections
    for sec in results['output'].split('['):
        if not sec.startswith("libdefaults"):
            continue

        for entry in sec.splitlines():
            if entry.strip() == "scan_interfaces = true":
                has_aux = True
                break

    assert has_aux is True, results['output']


def test_26_base_krb5_base_reset_aux(request):
    depends(request, ["KRB5_IS_HEALTHY"])
    results = PUT("/kerberos/", {"appdefaults_aux": "", "libdefaults_aux": ""})
    assert results.status_code == 200, results.text


def test_27_modify_base_krb5_appdefaults_aux_knownfail(request):
    depends(request, ["KRB5_IS_HEALTHY"])
    results = PUT("/kerberos/", {"appdefaults_aux": "canary = true"})
    assert results.status_code == 422, results.text


def test_28_modify_base_krb5_libdefaults_aux_knownfail(request):
    depends(request, ["KRB5_IS_HEALTHY"])
    results = PUT("/kerberos/", {"libdefaults_aux": "canary = true"})
    assert results.status_code == 422, results.text


def test_29_verify_no_nfs_principals(request):
    depends(request, ["KRB5_IS_HEALTHY", "ssh_password"], scope="session")
    cmd = 'midclt call kerberos.keytab.has_nfs_principal'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == 'False'


def test_30_check_nfs_exports_sec(request):
    """
    First NFS exports check. In this situation we are joined to
    AD and therefore have a keytab. We do not at this point have
    an NFS SPN entry. Expected security with v4 is:
    "V4: / -sec=sys"
    """
    depends(request, ["KRB5_IS_HEALTHY", "ssh_password"], scope="session")
    payload = {"v4": True}
    results = PUT("/nfs/", payload)
    assert results.status_code == 200, results.text

    cmd = 'midclt call etc.generate nfsd'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    expected_sec = "V4: / -sec=sys"
    cmd = f'grep "{expected_sec}" /etc/exports'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == expected_sec, results['output']


@pytest.mark.dependency(name="V4_KRB_ENABLED")
def test_31_enable_krb5_nfs4(request):
    depends(request, ["KRB5_IS_HEALTHY"])
    payload = {"v4_krb": True}
    results = PUT("/nfs/", payload)
    assert results.status_code == 200, results.text


def test_32_add_krb_spn(request):
    """
    Force AD plugin to add NFS spns for further testing.
    This should still be possible because the initial domain
    join involved obtaining a kerberos ticket with elevated
    privileges.
    """
    depends(request, ["V4_KRB_ENABLED", "ssh_password"], scope="session")
    cmd = 'midclt call activedirectory.add_nfs_spn'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_33_verify_has_nfs_principals(request):
    depends(request, ["V4_KRB_ENABLED", "ssh_password"], scope="session")
    cmd = 'midclt call kerberos.keytab.has_nfs_principal'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == 'True'


def test_34_verify_ad_nfs_parameters(request):
    depends(request, ["V4_KRB_ENABLED", "ssh_password"], scope="session")
    cmd = 'midclt call smb.getparm "winbind use default domain" GLOBAL'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    if not results['result']:
        return
    assert results['output'].strip() == "True"


def test_35_check_nfs_exports_sec(request):
    """
    Second NFS exports check. We now have an NFS SPN entry
    Expected security with is:
    "V4: / -sec=krb5:krb5i:krb5p"
    """
    depends(request, ["ssh_password"], scope="session")
    cmd = 'midclt call etc.generate nfsd'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    expected_sec = "V4: / -sec=krb5:krb5i:krb5p"
    cmd = f'grep "{expected_sec}" /etc/exports'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == expected_sec, results['output']


def test_36_disable_krb5_nfs4(request):
    """
    v4_krb_enabled should still be True after this
    disabling v4_krb because we still have an nfs
    service principal in our keytab.
    """
    depends(request, ["V4_KRB_ENABLED"])
    payload = {"v4_krb": False}
    results = PUT("/nfs/", payload)
    assert results.status_code == 200, results.text
    v4_krb_enabled = results.json()['v4_krb_enabled']
    assert v4_krb_enabled is True, results.text


def test_37_check_nfs_exports_sec(request):
    """
    Second NFS exports check. We now have an NFS SPN entry
    but v4_krb is disabled.
    Expected security with is:
    "V4: / -sec=sys:krb5:krb5i:krb5p"
    """
    cmd = 'midclt call etc.generate nfsd'
    depends(request, ["ssh_password"], scope="session")
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    expected_sec = "V4: / -sec=sys:krb5:krb5i:krb5p"
    cmd = f'grep "{expected_sec}" /etc/exports'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == expected_sec, results['output']


def test_38_cleanup_nfs_settings(request):
    payload = {"v4": False}
    results = PUT("/nfs/", payload)
    assert results.status_code == 200, results.text


def test_39_leave_activedirectory(request):
    depends(request, ["JOINED_AD"])
    global payload, results
    payload = {
        "username": ADUSERNAME,
        "password": ADPASSWORD
    }
    results = POST("/activedirectory/leave/", payload)
    assert results.status_code == 200, results.text


def test_40_verify_activedirectory_live_do_not_leak_password_in_middleware_log(request):
    depends(request, ["AD_ENABLED", "ssh_password"], scope="session")
    cmd = f"""grep -R "{ADPASSWORD}" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_41_remove_site(request):
    depends(request, ["JOINED_AD"])
    payload = {"site": None, "use_default_domain": False}
    results = PUT("/activedirectory/", payload)
    assert results.status_code == 200, results.text


def test_42_reset_dns(request):
    depends(request, ["SET_DNS"])
    global payload
    payload = {
        "nameserver1": nameserver1,
    }
    global results
    results = PUT("/network/configuration/", payload)
    assert results.status_code == 200, results.text


def test_43_verify_v4_krb_enabled_is_false(request):
    depends(request, ["V4_KRB_ENABLED"])
    results = GET("/nfs")
    assert results.status_code == 200, results.text
    v4_krb_enabled = results.json()['v4_krb_enabled']
    assert v4_krb_enabled is False, results.text


def test_44_check_ad_machine_account_deleted_after_ad_leave(request):
    depends(request, ["AD_IS_HEALTHY"])
    results = GET('/kerberos/keytab/?name=AD_MACHINE_ACCOUNT')
    assert results.status_code == 200, results.text
    assert len(results.json()) == 0
