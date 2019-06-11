#!/usr/bin/env python3.6

import os
import sys
import pytest
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import pool_name
from config import *
from functions import GET, POST, PUT, DELETE, SSH_TEST

ad_data_type = {
    'id': int,
    'domainname': str,
    'bindname': str,
    'bindpw': str,
    'ssl': str,
    'certificate': type(None),
    'verbose_logging': bool,
    'unix_extensions': bool,
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
    'idmap_backend': str,
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
        "idmap_backend",
        "enable"
]

if "BRIDGEHOST" in locals():
    MOUNTPOINT = f"/tmp/ad{BRIDGEHOST}"
dataset = f"{pool_name}/ad-bsd"
dataset_url = dataset.replace('/', '%2F')
SMB_NAME = "TestShare"
SMB_PATH = f"/mnt/{dataset}"
VOL_GROUP = "wheel"

Reason = "BRIDGEHOST, BRIDGEDOMAIN, ADPASSWORD, and ADUSERNAME are missing in "
Reason += "ixautomation.conf"
BSDReason = 'BSD host configuration is missing in ixautomation.conf'
OSXReason = 'OSX host configuration is missing in ixautomation.conf'

ad_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                      "BRIDGEDOMAIN" in locals(),
                                      "ADPASSWORD" in locals(),
                                      "ADUSERNAME" in locals(),
                                      "MOUNTPOINT" in locals()
                                      ]) is False, reason=Reason)


bsd_host_cfg = pytest.mark.skipif(all(["BSD_HOST" in locals(),
                                       "BSD_USERNAME" in locals(),
                                       "BSD_PASSWORD" in locals()
                                       ]) is False, reason=BSDReason)

osx_host_cfg = pytest.mark.skipif(all(["OSX_HOST" in locals(),
                                       "OSX_USERNAME" in locals(),
                                       "OSX_PASSWORD" in locals()
                                       ]) is False, reason=OSXReason)


def test_01_get_activedirectory_data():
    global results
    results = GET('/activedirectory/')
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', list(ad_data_type.keys()))
def test_02_verify_activedirectory_data_type_of_the_object_value_of_(data):
    assert isinstance(results.json()[data], ad_data_type[data]), results.text


def test_03_get_activedirectory_state():
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'DISABLED', results.text


def test_04_get_activedirectory_started_before_starting_activedirectory():
    results = GET('/activedirectory/started/')
    assert results.status_code == 400, results.text


def test_05_creating_ad_dataset_for_smb():
    results = POST("/pool/dataset/", {"name": dataset})
    assert results.status_code == 200, results.text


@ad_test_cfg
def test_06_enabling_activedirectory():
    global payload, results
    payload = {
        "bindpw": ADPASSWORD,
        "bindname": ADUSERNAME,
        "domainname": BRIDGEDOMAIN,
        "netbiosname": BRIDGEHOST,
        "idmap_backend": "RID",
        "enable": True
    }
    results = PUT("/activedirectory/", payload)
    assert results.status_code == 200, results.text


@ad_test_cfg
def test_07_get_activedirectory_state():
    global results
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'HEALTHY', results.text


@ad_test_cfg
def test_08_get_activedirectory_started():
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


@ad_test_cfg
def test_09_get_activedirectory_data():
    global results
    results = GET('/activedirectory/')
    assert results.status_code == 200, results.text


@ad_test_cfg
@pytest.mark.parametrize('data', ad_object_list)
def test_10_verify_activedirectory_data_of_(data):
    if data == 'domainname':
        assert results.json()[data].lower() == payload[data], results.text
    else:
        assert results.json()[data] == payload[data], results.text


def test_11_setting_up_smb():
    global payload, results
    payload = {
        "description": "Test FreeNAS Server",
        "guest": "nobody",
        "hostlookup": False,
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', ["description", "guest", "hostlookup"])
def test_12_verify_the_value_of_put_smb_object_value_of_(data):
    assert results.json()[data] == payload[data], results.text


def test_13_get_smb_data():
    global results
    results = GET("/smb/")
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', ["description", "guest", "hostlookup"])
def test_14_verify_the_value_of_get_smb_object_(data):
    assert results.json()[data] == payload[data], results.text


def test_15_creating_a_smb_share_on_smb_path():
    global payload, results, smb_id
    payload = {
        "comment": "My Test SMB Share",
        "path": SMB_PATH,
        "name": SMB_NAME,
        "guestok": True,
        "vfsobjects": ["streams_xattr"]
    }
    results = POST("/sharing/smb/", payload)
    assert results.status_code == 200, results.text
    smb_id = results.json()['id']


@pytest.mark.parametrize('data', ["comment", "path", "name", "guestok", "vfsobjects"])
def test_16_verify_the_value_of_the_created_sharing_smb_object_(data):
    assert results.json()[data] == payload[data], results.text


def test_17_get_sharing_smb_from_id():
    global results
    results = GET(f"/sharing/smb/id/{smb_id}/")
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', ["comment", "path", "name", "guestok", "vfsobjects"])
def test_18_verify_the_value_of_get_sharing_smb_object_(data):
    assert results.json()[data] == payload[data], results.text


def test_19_enable_cifs_service():
    results = PUT("/service/id/cifs/", {"enable": True})
    assert results.status_code == 200, results.text


def test_20_checking_to_see_if_clif_service_is_enabled():
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] is True, results.text


def test_21_starting_cifs_service():
    payload = {"service": "cifs", "service-control": {"onetime": True}}
    results = POST("/service/restart/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_22_checking_to_see_if_nfs_service_is_running():
    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "RUNNING", results.text


@bsd_host_cfg
@ad_test_cfg
def test_23_creating_smb_mountpoint():
    results = SSH_TEST('mkdir -p "%s" && sync' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@ad_test_cfg
def test_24_store_AD_credentials_in_a_file_for_mount_smbfs():
    cmd = 'echo "[TESTNAS:ADUSER]" > ~/.nsmbrc && '
    cmd += 'echo "password=12345678" >> ~/.nsmbrc'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@ad_test_cfg
def test_25_mounting_SMB():
    cmd = 'mount_smbfs -N -I %s -W AD03 ' % ip
    cmd += '"//aduser@testnas/%s" "%s"' % (SMB_NAME, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@ad_test_cfg
def test_26_creating_SMB_file():
    results = SSH_TEST('touch "%s/testfile"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@ad_test_cfg
def test_27_moving_SMB_file():
    cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@ad_test_cfg
def test_28_copying_SMB_file():
    cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@ad_test_cfg
def test_29_deleting_SMB_file_1_2():
    results = SSH_TEST('rm "%s/testfile"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@ad_test_cfg
def test_30_deleting_SMB_file_2_2():
    results = SSH_TEST('rm "%s/testfile2"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@ad_test_cfg
def test_31_unmounting_SMB():
    results = SSH_TEST('umount "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


# Delete tests
@bsd_host_cfg
@ad_test_cfg
def test_32_removing_SMB_mountpoint():
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@ad_test_cfg
def test_33_leave_activedirectory():
    global payload, results
    payload = {
        "username": ADUSERNAME,
        "password": ADPASSWORD
    }
    results = POST("/activedirectory/leave/", payload)
    assert results.status_code == 200, results.text


@ad_test_cfg
def test_34_get_activedirectory_state():
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'DISABLED', results.text


@ad_test_cfg
def test_35_get_activedirectory_started_before_starting_activedirectory():
    results = GET('/activedirectory/started/')
    assert results.status_code == 400, results.text


@ad_test_cfg
def test_36_re_enable_activedirectory():
    global payload, results
    payload = {
        "bindpw": ADPASSWORD,
        "bindname": ADUSERNAME,
        "domainname": BRIDGEDOMAIN,
        "netbiosname": BRIDGEHOST,
        "idmap_backend": "RID",
        "enable": True
    }
    results = PUT("/activedirectory/", payload)
    assert results.status_code == 200, results.text


@ad_test_cfg
def test_37_get_activedirectory_state():
    global results
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'HEALTHY', results.text


@ad_test_cfg
def test_38_get_activedirectory_started():
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


@ad_test_cfg
def test_39_get_activedirectory_data():
    global results
    results = GET('/activedirectory/')
    assert results.status_code == 200, results.text


@ad_test_cfg
@pytest.mark.parametrize('data', ad_object_list)
def test_40_verify_activedirectory_data_of_(data):
    if data == 'domainname':
        assert results.json()[data].lower() == payload[data], results.text
    else:
        assert results.json()[data] == payload[data], results.text


# Testing OSX
# Mount share on OSX system and create a test file
@osx_host_cfg
@ad_test_cfg
def test_41_Create_mount_point_for_SMB_on_OSX_system():
    results = SSH_TEST('mkdir -p "%s"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
@ad_test_cfg
def test_42_Mount_SMB_share_on_OSX_system():
    cmd = 'mount -t smbfs "smb://%s:' % ADUSERNAME
    cmd += '%s@%s/%s" "%s"' % (ADPASSWORD, ip, SMB_NAME, MOUNTPOINT)
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
@ad_test_cfg
def test_43_Create_file_on_SMB_share_via_OSX_to_test_permissions():
    results = SSH_TEST('touch "%s/testfile.txt"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Move test file to a new location on the SMB share
@osx_host_cfg
@ad_test_cfg
def test_44_Moving_SMB_test_file_into_a_new_directory():
    cmd = 'mkdir -p "%s/tmp" && ' % MOUNTPOINT
    cmd += 'mv "%s/testfile.txt" ' % MOUNTPOINT
    cmd += '"%s/tmp/testfile.txt"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete test file and test directory from SMB share
@osx_host_cfg
@ad_test_cfg
def test_45_Deleting_test_file_and_directory_from_SMB_share():
    cmd = 'rm -f "%s/tmp/testfile.txt" && ' % MOUNTPOINT
    cmd += 'rmdir "%s/tmp"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
@ad_test_cfg
def test_46_Verifying_that_test_file_directory_successfully_removed():
    cmd = 'find -- "%s/" -prune -type d -empty | grep -q .' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Clean up mounted SMB share
@osx_host_cfg
@ad_test_cfg
def test_47_Unmount_SMB_share():
    results = SSH_TEST('umount -f "%s"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete tests
@osx_host_cfg
@ad_test_cfg
def test_48_Removing_SMB_mountpoint():
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# put all code to disable and delete under here
@ad_test_cfg
def test_49_disable_activedirectory():
    global payload, results
    payload = {
        "enable": False
    }
    results = PUT("/activedirectory/", payload)
    assert results.status_code == 200, results.text


def test_50_get_activedirectory_state():
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'DISABLED', results.text


def test_51_get_activedirectory_started_before_starting_activedirectory():
    results = GET('/activedirectory/started/')
    assert results.status_code == 400, results.text


def test_52_disable_cifs_service_at_boot():
    results = PUT("/service/id/cifs/", {"enable": False})
    assert results.status_code == 200, results.text


def test_53_checking_to_see_if_clif_service_is_enabled_at_boot():
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] is False, results.text


def test_54_stoping_clif_service():
    payload = {"service": "cifs", "service-control": {"onetime": True}}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_55_checking_if_cifs_is_stop():
    results = GET("/service?service=cifs")
    assert results.json()[0]['state'] == "STOPPED", results.text


def test_56_destroying_ad_dataset_for_smb():
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
