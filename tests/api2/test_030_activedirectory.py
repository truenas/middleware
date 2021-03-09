#!/usr/bin/env python3

import os
import json
import sys
import pytest
from pytest_dependency import depends
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import pool_name, ip, hostname, scale, user, password
from functions import GET, POST, PUT, DELETE, SSH_TEST, wait_on_job

try:
    from config import AD_DOMAIN, ADPASSWORD, ADUSERNAME, ADNameServer
except ImportError:
    Reason = 'ADNameServer AD_DOMAIN, ADPASSWORD, or/and ADUSERNAME are missing in config.py"'
    pytestmark = pytest.mark.skip(reason=Reason)
else:
    from auto_config import dev_test
    # comment pytestmark for development testing with --dev-test
    pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

BSDReason = 'BSD_HOST is not setup for SSH_TEST'

try:
    from config import BSD_HOST, BSD_USERNAME, BSD_PASSWORD
    bsd_host_cfg = pytest.mark.skipif(False, reason=BSDReason)
except ImportError:
    bsd_host_cfg = pytest.mark.skipif(True, reason=BSDReason)

OSXReason = 'OSX host configuration is missing in ixautomation.conf'
try:
    from config import OSX_HOST, OSX_USERNAME, OSX_PASSWORD
    osx_host_cfg = pytest.mark.skipif(False, reason=OSXReason)
except ImportError:
    osx_host_cfg = pytest.mark.skipif(True, reason=OSXReason)

ad_data_type = {
    'id': int,
    'domainname': str,
    'bindname': str,
    'bindpw': str,
    'verbose_logging': bool,
    'allow_trusted_doms': bool,
    'use_default_domain': bool,
    'allow_dns_updates': bool,
    'disable_freenas_cache': bool,
    'site': type(None),
    'kerberos_realm': type(None),
    'kerberos_principal': str,
    'createcomputer': str,
    'timeout': int,
    'dns_timeout': int,
    'nss_info': type(None),
    'enable': bool,
    'netbiosname': str,
    'netbiosalias': list
}

ad_object_list = [
    "bindname",
    "domainname",
    "netbiosname",
    "enable"
]

MOUNTPOINT = f"/tmp/ad-{hostname}"
dataset = f"{pool_name}/ad-bsd"
dataset_url = dataset.replace('/', '%2F')
SMB_NAME = "TestShare"
SMB_PATH = f"/mnt/{dataset}"
group = 'root' if scale else 'wheel'


@pytest.mark.dependency(name="ad_01")
def test_01_get_nameserver1(request):
    depends(request, ["pool_04"], scope="session")
    global nameserver1
    results = GET("/network/configuration/")
    assert results.status_code == 200, results.text
    nameserver1 = results.json()['nameserver1']


@pytest.mark.dependency(name="ad_02")
def test_02_set_nameserver_for_ad(request):
    depends(request, ["pool_04", "ad_01"], scope="session")
    global payload
    payload = {
        "nameserver1": ADNameServer,
    }
    global results
    results = PUT("/network/configuration/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_03_get_activedirectory_data(request):
    depends(request, ["pool_04", "ad_01", "ad_02"], scope="session")
    global results
    results = GET('/activedirectory/')
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', list(ad_data_type.keys()))
def test_04_verify_activedirectory_data_type_of_the_object_value_of_(request, data):
    assert isinstance(results.json()[data], ad_data_type[data]), results.text


def test_05_get_activedirectory_state(request):
    depends(request, ["pool_04", "ad_01", "ad_02"], scope="session")
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'DISABLED', results.text


def test_06_get_activedirectory_started_before_starting_activedirectory(request):
    depends(request, ["pool_04", "ad_01", "ad_02"], scope="session")
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is False, results.text


def test_07_creating_ad_dataset_for_smb(request):
    depends(request, ["pool_04", "ad_01", "ad_02"], scope="session")
    results = POST("/pool/dataset/", {"name": dataset})
    assert results.status_code == 200, results.text


def test_08_Changing_permissions_on_dataset(request):
    depends(request, ["pool_04", "ad_01", "ad_02"], scope="session")
    global job_id
    results = POST(f'/pool/dataset/id/{dataset_url}/permission/', {
        'acl': [],
        'mode': '777',
        'user': 'root',
        'group': group
    })
    assert results.status_code == 200, results.text
    job_id = results.json()


def test_09_verify_the_job_id_is_successfull(request):
    depends(request, ["pool_04", "ad_01", "ad_02"], scope="session")
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


@pytest.mark.dependency(name="ad_10")
def test_10_enabling_activedirectory(request):
    depends(request, ["pool_04", "ad_01", "ad_02"], scope="session")
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


def test_11_verify_job_id_is_successfull(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_12_verify_activedirectory_do_not_leak_password_in_middleware_log(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10", "ssh_password"], scope="session")
    cmd = f"""grep -R "{ADPASSWORD}" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_13_get_activedirectory_state(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    global results
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'HEALTHY', results.text


def test_14_get_activedirectory_started(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


def test_15_get_activedirectory_data(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    global results
    results = GET('/activedirectory/')
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', ad_object_list)
def test_16_verify_activedirectory_data_of_(request, data):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    if data == 'domainname':
        assert results.json()[data].lower() == payload[data], results.text
    else:
        assert results.json()[data] == payload[data], results.text


@pytest.mark.dependency(name="kerberos_verified")
def test_17_kerberos_keytab_verify(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10", "ssh_password"], scope="session")
    cmd = 'midclt call kerberos.keytab.kerberos_principal_choices'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    if results['result'] is True:
        kt = json.loads(results['output'].strip())
        assert len(kt) != 0, results['output']


def test_18_kerberos_restart_verify(request):
    """
    This tests our ability to re-kinit using our machine account.
    """
    depends(request, ["kerberos_verified", "ssh_password"], scope="session")
    cmd = 'rm /etc/krb5.keytab'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    cmd = 'midclt call kerberos.stop'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    cmd = 'midclt call kerberos.start'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    cmd = 'midclt call kerberos.keytab.kerberos_principal_choices'
    results = SSH_TEST(cmd, user, password, ip)
    kt = json.loads(results['output'].strip())
    assert results['result'] is True, results['output']
    if results['result'] is True:
        assert len(kt) != 0, results['output']

    cmd = 'midclt call kerberos._klist_test'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['output'].strip() == 'True'


def test_19_setting_up_smb(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    global payload, results
    payload = {
        "description": "Test FreeNAS Server",
        "guest": "nobody",
        "enable_smb1": True
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', ["description", "guest"])
def test_20_verify_the_value_of_put_smb_object_value_of_(request, data):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    assert results.json()[data] == payload[data], results.text


def test_21_get_smb_data(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    global results
    results = GET("/smb/")
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', ["description", "guest"])
def test_22_verify_the_value_of_get_smb_object_(request, data):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    assert results.json()[data] == payload[data], results.text


def test_23_creating_a_smb_share_on_smb_path(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    global payload, results, smb_id
    payload = {
        "comment": "My Test SMB Share",
        "path": SMB_PATH,
        "name": SMB_NAME,
        "guestok": True,
        "streams": True
    }
    results = POST("/sharing/smb/", payload)
    assert results.status_code == 200, results.text
    smb_id = results.json()['id']


@pytest.mark.parametrize('data', ["comment", "path", "name", "guestok"])
def test_24_verify_the_value_of_the_created_sharing_smb_object_(request, data):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    assert results.json()[data] == payload[data], results.text


def test_25_get_sharing_smb_from_id(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    global results
    results = GET(f"/sharing/smb/id/{smb_id}/")
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', ["comment", "path", "name", "guestok"])
def test_26_verify_the_value_of_get_sharing_smb_object_(request, data):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    assert results.json()[data] == payload[data], results.text


def test_27_enable_cifs_service(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = PUT("/service/id/cifs/", {"enable": True})
    assert results.status_code == 200, results.text


def test_28_checking_to_see_if_clif_service_is_enabled(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] is True, results.text


def test_29_starting_cifs_service(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    payload = {"service": "cifs"}
    results = POST("/service/restart/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_30_checking_to_see_if_nfs_service_is_running(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "RUNNING", results.text


@bsd_host_cfg
def test_31_creating_smb_mountpoint(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = SSH_TEST('mkdir -p "%s" && sync' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_32_store_AD_credentials_in_a_file_for_mount_smbfs(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    cmd = f'echo "[{ip}:{ADUSERNAME.upper()}]" > ~/.nsmbrc && '
    cmd += f'echo "password={ADPASSWORD}" >> ~/.nsmbrc'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@pytest.mark.timeout(10)
def test_33_mounting_SMB(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    cmd = f'mount_smbfs -N -I {ip} -W AD01 -U {ADUSERNAME} ' \
        f'"//{ADUSERNAME}@{ip}/{SMB_NAME}" "{MOUNTPOINT}"'

    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_34_creating_SMB_file(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = SSH_TEST('touch "%s/testfile"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_35_moving_SMB_file(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_36_copying_SMB_file(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_37_deleting_SMB_file_1_2(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = SSH_TEST('rm "%s/testfile"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_38_deleting_SMB_file_2_2(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = SSH_TEST('rm "%s/testfile2"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_39_unmounting_SMB(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = SSH_TEST('umount "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


# Delete tests
@bsd_host_cfg
def test_40_removing_SMB_mountpoint(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


def test_41_leave_activedirectory(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    global payload, results
    payload = {
        "username": ADUSERNAME,
        "password": ADPASSWORD
    }
    results = POST("/activedirectory/leave/", payload)
    assert results.status_code == 200, results.text


def test_42_verify_activedirectory_leave_do_not_leak_password_in_middleware_log(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10", "ssh_password"], scope="session")
    cmd = f"""grep -R "{ADPASSWORD}" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_43_get_activedirectory_state(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'DISABLED', results.text


def test_44_get_activedirectory_started_after_leaving_AD(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is False, results.text


def test_45_re_enable_activedirectory(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    global payload, results, job_id
    payload = {
        "bindpw": ADPASSWORD,
        "bindname": ADUSERNAME,
        "domainname": AD_DOMAIN,
        "netbiosname": hostname,
        "enable": True
    }
    results = PUT("/activedirectory/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()['job_id']


def test_46_verify_job_id_is_successfull(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_47_verify_activedirectory_do_not_leak_password_in_middleware_log(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10", "ssh_password"], scope="session")
    cmd = f"""grep -R "{ADPASSWORD}" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_48_get_activedirectory_state(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    global results
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'HEALTHY', results.text


def test_49_get_activedirectory_started(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


def test_50_get_activedirectory_data(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    global results
    results = GET('/activedirectory/')
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', ad_object_list)
def test_51_verify_activedirectory_data_of_(request, data):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    if data == 'domainname':
        assert results.json()[data].lower() == payload[data], results.text
    else:
        assert results.json()[data] == payload[data], results.text


# Testing OSX
# Mount share on OSX system and create a test file
@osx_host_cfg
def test_52_Create_mount_point_for_SMB_on_OSX_system(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = SSH_TEST('mkdir -p "%s"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
@pytest.mark.timeout(10)
def test_53_Mount_SMB_share_on_OSX_system(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    cmd = 'mount -t smbfs "smb://%s:' % ADUSERNAME
    cmd += '%s@%s/%s" "%s"' % (ADPASSWORD, ip, SMB_NAME, MOUNTPOINT)
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_54_Create_file_on_SMB_share_via_OSX_to_test_permissions(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = SSH_TEST('touch "%s/testfile.txt"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Move test file to a new location on the SMB share
@osx_host_cfg
def test_55_Moving_SMB_test_file_into_a_new_directory(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    cmd = 'mkdir -p "%s/tmp" && ' % MOUNTPOINT
    cmd += 'mv "%s/testfile.txt" ' % MOUNTPOINT
    cmd += '"%s/tmp/testfile.txt"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete test file and test directory from SMB share
@osx_host_cfg
def test_56_Deleting_test_file_and_directory_from_SMB_share(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    cmd = 'rm -f "%s/tmp/testfile.txt" && ' % MOUNTPOINT
    cmd += 'rmdir "%s/tmp"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_57_Verifying_that_test_file_directory_successfully_removed(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    cmd = 'find -- "%s/" -prune -type d -empty | grep -q .' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Clean up mounted SMB share
@osx_host_cfg
def test_58_Unmount_SMB_share(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = SSH_TEST('umount -f "%s"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete tests
@osx_host_cfg
def test_59_Removing_SMB_mountpoint(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# put all code to disable and delete under here
def test_60_disable_activedirectory(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    global payload, results
    payload = {
        "enable": False
    }
    results = PUT("/activedirectory/", payload)
    assert results.status_code == 200, results.text


def test_61_get_activedirectory_state(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'DISABLED', results.text


def test_62_get_activedirectory_started_after_disabling_AD(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is False, results.text


def test_63_re_enable_activedirectory(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    global payload, results, job_id
    payload = {
        "enable": True
    }
    results = PUT("/activedirectory/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()['job_id']


def test_64_verify_job_id_is_successfull(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_65_get_activedirectory_state(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    global results
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'HEALTHY', results.text


def test_66_get_activedirectory_started(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


def test_67_leave_activedirectory(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    global payload, results
    payload = {
        "username": ADUSERNAME,
        "password": ADPASSWORD
    }
    results = POST("/activedirectory/leave/", payload)
    assert results.status_code == 200, results.text


def test_68_verify_activedirectory_leave_do_not_leak_password_in_middleware_log(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10", "ssh_password"], scope="session")
    cmd = f"""grep -R "{ADPASSWORD}" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_69_get_activedirectory_state(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'DISABLED', results.text


def test_70_get_activedirectory_started_after_living(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is False, results.text


def test_71_disable_cifs_service_at_boot(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = PUT("/service/id/cifs/", {"enable": False})
    assert results.status_code == 200, results.text


def test_72_checking_to_see_if_clif_service_is_enabled_at_boot(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] is False, results.text


def test_73_stoping_clif_service(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    payload = {"service": "cifs"}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_74_checking_if_cifs_is_stop(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = GET("/service?service=cifs")
    assert results.json()[0]['state'] == "STOPPED", results.text


def test_75_destroying_ad_dataset_for_smb(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text


def test_76_configure_setting_domain_hostname_and_dns(request):
    depends(request, ["pool_04", "ad_01", "ad_02", "ad_10"], scope="session")
    global payload
    payload = {
        "nameserver1": nameserver1,
    }
    global results
    results = PUT("/network/configuration/", payload)
    assert results.status_code == 200, results.text
