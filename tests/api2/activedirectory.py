#!/usr/bin/env python3

import os
import sys
import pytest
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import pool_name, user, password, ip, hostname
from functions import GET, POST, PUT, DELETE, SSH_TEST, ping_host, wait_on_job

ad_data_type = {
    'id': int,
    'domainname': str,
    'bindname': str,
    'bindpw': str,
    'ssl': str,
    'certificate': type(None),
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
    'ldap_sasl_wrapping': str,
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

MOUNTPOINT = f"/tmp/ad-test"
dataset = f"{pool_name}/ad-bsd"
dataset_url = dataset.replace('/', '%2F')
SMB_NAME = "TestShare"
SMB_PATH = f"/mnt/{dataset}"
VOL_GROUP = "wheel"

BSDReason = 'BSD host configuration is missing in ixautomation.conf'
OSXReason = 'OSX host configuration is missing in ixautomation.conf'

ad_host_up = False
try:
    from config import AD_DOMAIN, ADPASSWORD, ADUSERNAME, ADNameServer
    ad_host_up = ping_host(AD_DOMAIN, 5)
    Reason = f'{AD_DOMAIN} is down'
    skip_ad_test = pytest.mark.skipif(ad_host_up is False, reason=Reason)
except ImportError:
    Reason = 'ADNameServer AD_DOMAIN, ADPASSWORD, or/and ADUSERNAME are missing in config.py"'
    skip_ad_test = pytest.mark.skip(reason=Reason)


try:
    from config import BSD_HOST, BSD_USERNAME, BSD_PASSWORD
    bsd_host_cfg = pytest.mark.skipif(False, reason=BSDReason)
except ImportError:
    bsd_host_cfg = pytest.mark.skipif(True, reason=BSDReason)


try:
    from config import OSX_HOST, OSX_USERNAME, OSX_PASSWORD
    osx_host_cfg = pytest.mark.skipif(False, reason=OSXReason)
except ImportError:
    osx_host_cfg = pytest.mark.skipif(True, reason=OSXReason)


@skip_ad_test
def test_01_get_nameserver1_and_nameserver2():
    global nameserver1, nameserver2
    results = GET("/network/configuration/")
    assert results.status_code == 200, results.text
    nameserver1 = results.json()['nameserver1']
    nameserver2 = results.json()['nameserver2']


@skip_ad_test
def test_02_store_AD_credentials_in_a_file_for_mount_smbfs():
    global ad_dns
    cmd = f'ping -c 5 {AD_DOMAIN}'
    results = SSH_TEST(cmd, user, password, ip)
    ad_dns = results['result']


@skip_ad_test
def test_03_set_nameserver_for_ad():
    if ad_dns is True:
        pytest.skip('DNS is fine')
    global payload
    payload = {
        "nameserver1": ADNameServer,
        "nameserver2": nameserver1,
        "nameserver3": nameserver2
    }
    global results
    results = PUT("/network/configuration/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


@skip_ad_test
def test_04_get_activedirectory_data():
    global results
    results = GET('/activedirectory/')
    assert results.status_code == 200, results.text


@skip_ad_test
@pytest.mark.parametrize('data', list(ad_data_type.keys()))
def test_05_verify_activedirectory_data_type_of_the_object_value_of_(data):
    assert isinstance(results.json()[data], ad_data_type[data]), results.text


@skip_ad_test
def test_06_get_activedirectory_state():
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'DISABLED', results.text


@skip_ad_test
def test_07_get_activedirectory_started_before_starting_activedirectory():
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is False, results.text


@skip_ad_test
def test_08_creating_ad_dataset_for_smb():
    results = POST("/pool/dataset/", {"name": dataset})
    assert results.status_code == 200, results.text


@skip_ad_test
def test_09_Changing_permissions_on_dataset():
    global job_id
    results = POST(f'/pool/dataset/id/{dataset_url}/permission/', {
        'acl': [],
        'mode': '777',
        'user': 'root',
        'group': 'wheel'
    })
    assert results.status_code == 200, results.text
    job_id = results.json()


@skip_ad_test
def test_10_verify_the_job_id_is_successfull():
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


@skip_ad_test
def test_11_enabling_activedirectory():
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


@skip_ad_test
def test_12_verify_job_id_is_successfull():
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


@skip_ad_test
def test_13_get_activedirectory_state():
    global results
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'HEALTHY', results.text


@skip_ad_test
def test_14_get_activedirectory_started():
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


@skip_ad_test
def test_15_get_activedirectory_data():
    global results
    results = GET('/activedirectory/')
    assert results.status_code == 200, results.text


@skip_ad_test
@pytest.mark.parametrize('data', ad_object_list)
def test_16_verify_activedirectory_data_of_(data):
    if data == 'domainname':
        assert results.json()[data].lower() == payload[data], results.text
    else:
        assert results.json()[data] == payload[data], results.text


@skip_ad_test
def test_17_setting_up_smb():
    global payload, results
    payload = {
        "description": "Test FreeNAS Server",
        "guest": "nobody",
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


@skip_ad_test
@pytest.mark.parametrize('data', ["description", "guest"])
def test_18_verify_the_value_of_put_smb_object_value_of_(data):
    assert results.json()[data] == payload[data], results.text


@skip_ad_test
def test_19_get_smb_data():
    global results
    results = GET("/smb/")
    assert results.status_code == 200, results.text


@skip_ad_test
@pytest.mark.parametrize('data', ["description", "guest"])
def test_20_verify_the_value_of_get_smb_object_(data):
    assert results.json()[data] == payload[data], results.text


@skip_ad_test
def test_21_creating_a_smb_share_on_smb_path():
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


@skip_ad_test
@pytest.mark.parametrize('data', ["comment", "path", "name", "guestok", "streams"])
def test_22_verify_the_value_of_the_created_sharing_smb_object_(data):
    assert results.json()[data] == payload[data], results.text


@skip_ad_test
def test_23_get_sharing_smb_from_id():
    global results
    results = GET(f"/sharing/smb/id/{smb_id}/")
    assert results.status_code == 200, results.text


@skip_ad_test
@pytest.mark.parametrize('data', ["comment", "path", "name", "guestok", "streams"])
def test_24_verify_the_value_of_get_sharing_smb_object_(data):
    assert results.json()[data] == payload[data], results.text


@skip_ad_test
def test_25_enable_cifs_service():
    results = PUT("/service/id/cifs/", {"enable": True})
    assert results.status_code == 200, results.text


@skip_ad_test
def test_26_checking_to_see_if_clif_service_is_enabled():
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] is True, results.text


@skip_ad_test
def test_27_starting_cifs_service():
    payload = {"service": "cifs"}
    results = POST("/service/restart/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


@skip_ad_test
def test_28_checking_to_see_if_nfs_service_is_running():
    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "RUNNING", results.text


@bsd_host_cfg
@skip_ad_test
def test_29_creating_smb_mountpoint():
    results = SSH_TEST('mkdir -p "%s" && sync' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@skip_ad_test
def test_30_store_AD_credentials_in_a_file_for_mount_smbfs():
    cmd = 'echo "[TESTNAS:ADUSER]" > ~/.nsmbrc && '
    cmd += 'echo "password=12345678" >> ~/.nsmbrc'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@skip_ad_test
def test_31_mounting_SMB():
    cmd = 'mount_smbfs -N -I %s -W AD03 ' % ip
    cmd += '"//aduser@testnas/%s" "%s"' % (SMB_NAME, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@skip_ad_test
def test_32_creating_SMB_file():
    results = SSH_TEST('touch "%s/testfile"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@skip_ad_test
def test_33_moving_SMB_file():
    cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@skip_ad_test
def test_34_copying_SMB_file():
    cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@skip_ad_test
def test_35_deleting_SMB_file_1_2():
    results = SSH_TEST('rm "%s/testfile"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@skip_ad_test
def test_36_deleting_SMB_file_2_2():
    results = SSH_TEST('rm "%s/testfile2"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@skip_ad_test
def test_37_unmounting_SMB():
    results = SSH_TEST('umount "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


# Delete tests
@bsd_host_cfg
@skip_ad_test
def test_38_removing_SMB_mountpoint():
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@skip_ad_test
def test_39_leave_activedirectory():
    global payload, results
    payload = {
        "username": ADUSERNAME,
        "password": ADPASSWORD
    }
    results = POST("/activedirectory/leave/", payload)
    assert results.status_code == 200, results.text


@skip_ad_test
def test_40_get_activedirectory_state():
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'DISABLED', results.text


@skip_ad_test
def test_41_get_activedirectory_started_after_leaving_AD():
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is False, results.text


@skip_ad_test
def test_42_re_enable_activedirectory():
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


@skip_ad_test
def test_43_verify_job_id_is_successfull():
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


@skip_ad_test
def test_44_get_activedirectory_state():
    global results
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'HEALTHY', results.text


@skip_ad_test
def test_45_get_activedirectory_started():
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


@skip_ad_test
def test_46_get_activedirectory_data():
    global results
    results = GET('/activedirectory/')
    assert results.status_code == 200, results.text


@skip_ad_test
@pytest.mark.parametrize('data', ad_object_list)
def test_47_verify_activedirectory_data_of_(data):
    if data == 'domainname':
        assert results.json()[data].lower() == payload[data], results.text
    else:
        assert results.json()[data] == payload[data], results.text


# Testing OSX
# Mount share on OSX system and create a test file
@osx_host_cfg
@skip_ad_test
def test_48_Create_mount_point_for_SMB_on_OSX_system():
    results = SSH_TEST('mkdir -p "%s"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
@skip_ad_test
def test_49_Mount_SMB_share_on_OSX_system():
    cmd = 'mount -t smbfs "smb://%s:' % ADUSERNAME
    cmd += '%s@%s/%s" "%s"' % (ADPASSWORD, ip, SMB_NAME, MOUNTPOINT)
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
@skip_ad_test
def test_50_Create_file_on_SMB_share_via_OSX_to_test_permissions():
    results = SSH_TEST('touch "%s/testfile.txt"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Move test file to a new location on the SMB share
@osx_host_cfg
@skip_ad_test
def test_51_Moving_SMB_test_file_into_a_new_directory():
    cmd = 'mkdir -p "%s/tmp" && ' % MOUNTPOINT
    cmd += 'mv "%s/testfile.txt" ' % MOUNTPOINT
    cmd += '"%s/tmp/testfile.txt"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete test file and test directory from SMB share
@osx_host_cfg
@skip_ad_test
def test_52_Deleting_test_file_and_directory_from_SMB_share():
    cmd = 'rm -f "%s/tmp/testfile.txt" && ' % MOUNTPOINT
    cmd += 'rmdir "%s/tmp"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
@skip_ad_test
def test_53_Verifying_that_test_file_directory_successfully_removed():
    cmd = 'find -- "%s/" -prune -type d -empty | grep -q .' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Clean up mounted SMB share
@osx_host_cfg
@skip_ad_test
def test_54_Unmount_SMB_share():
    results = SSH_TEST('umount -f "%s"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete tests
@osx_host_cfg
@skip_ad_test
def test_55_Removing_SMB_mountpoint():
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# put all code to disable and delete under here
@skip_ad_test
def test_56_disable_activedirectory():
    global payload, results
    payload = {
        "enable": False
    }
    results = PUT("/activedirectory/", payload)
    assert results.status_code == 200, results.text


@skip_ad_test
def test_57_get_activedirectory_state():
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'DISABLED', results.text


@skip_ad_test
def test_58_get_activedirectory_started_after_disabling_AD():
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is False, results.text


@skip_ad_test
def test_59_re_enable_activedirectory():
    global payload, results, job_id
    payload = {
        "enable": True
    }
    results = PUT("/activedirectory/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()['job_id']


def test_60_verify_job_id_is_successfull():
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


@skip_ad_test
def test_61_get_activedirectory_state():
    global results
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'HEALTHY', results.text


@skip_ad_test
def test_62_get_activedirectory_started():
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


@skip_ad_test
def test_63_leave_activedirectory():
    global payload, results
    payload = {
        "username": ADUSERNAME,
        "password": ADPASSWORD
    }
    results = POST("/activedirectory/leave/", payload)
    assert results.status_code == 200, results.text


@skip_ad_test
def test_64_get_activedirectory_state():
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'DISABLED', results.text


@skip_ad_test
def test_65_get_activedirectory_started_after_living():
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is False, results.text


@skip_ad_test
def test_66_disable_cifs_service_at_boot():
    results = PUT("/service/id/cifs/", {"enable": False})
    assert results.status_code == 200, results.text


@skip_ad_test
def test_67_checking_to_see_if_clif_service_is_enabled_at_boot():
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] is False, results.text


@skip_ad_test
def test_68_stoping_clif_service():
    payload = {"service": "cifs"}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


@skip_ad_test
def test_69_checking_if_cifs_is_stop():
    results = GET("/service?service=cifs")
    assert results.json()[0]['state'] == "STOPPED", results.text


@skip_ad_test
def test_70_destroying_ad_dataset_for_smb():
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text


@skip_ad_test
def test_71_configure_setting_domain_hostname_and_dns():
    if ad_dns is True:
        pytest.skip('DSN is fine')
    global payload
    payload = {
        "nameserver1": nameserver1,
        "nameserver2": nameserver2,
        "nameserver3": ""
    }
    global results
    results = PUT("/network/configuration/", payload)
    assert results.status_code == 200, results.text
