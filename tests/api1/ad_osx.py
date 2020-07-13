#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET, PUT, SSH_TEST, DELETE
from auto_config import ip, pool_name, hostname

try:
    from config import AD_DOMAIN, ADPASSWORD, ADUSERNAME, ADNameServer
except ImportError:
    Reason = 'ADNameServer AD_DOMAIN, ADPASSWORD, or/and ADUSERNAME are missing in config.py"'
    pytestmark = pytest.mark.skip(reason=Reason)

OSXReason = 'OSX host configuration is missing in ixautomation.conf'
try:
    from config import OSX_HOST, OSX_USERNAME, OSX_PASSWORD
    osx_host_cfg = pytest.mark.skipif(False, reason=OSXReason)
except ImportError:
    osx_host_cfg = pytest.mark.skipif(True, reason=OSXReason)

MOUNTPOINT = "/tmp/ad-osx"
DATASET = "ad-osx"
SMB_NAME = "TestShare"
SMB_PATH = f"/mnt/{pool_name}/{DATASET}"
VOL_GROUP = "wheel"


def test_01_get_default_nameserver():
    global nameserver
    results = GET("/network/globalconfiguration/")
    assert results.status_code == 200, results.text
    nameserver = results.json()["gc_nameserver1"]


def test_02_setting_ad_dns():
    payload = {
        "gc_nameserver1": ADNameServer
    }
    results = PUT("/network/globalconfiguration/", payload)
    assert results.status_code == 200, results.text


def test_03_creating_smb_dataset():
    results = POST(f"/storage/volume/{pool_name}/datasets/", {"name": DATASET})
    assert results.status_code == 201, results.text


def test_04_Enabling_Active_Directory():
    payload = {
        "ad_bindpw": ADPASSWORD,
        "ad_bindname": ADUSERNAME,
        "ad_domainname": AD_DOMAIN,
        "ad_netbiosname": hostname,
        "ad_idmap_backend": "rid",
        "ad_enable": True
    }
    results = PUT("/directoryservice/activedirectory/1/", payload)
    assert results.status_code == 200, results.text
    sleep(10)


def test_05_Checking_Active_Directory():
    results = GET("/directoryservice/activedirectory/")
    assert results.json()["ad_enable"] is True, results.text
    sleep(2)


def test_06_Enabling_SMB_service():
    payload = {"cifs_srv_description": "Test FreeNAS Server",
               "cifs_srv_guest": "nobody",
               "cifs_hostname_lookup": False,
               "cifs_srv_aio_enable": False}
    results = PUT("/services/cifs/", payload)
    assert results.status_code == 200, results.text


# Now start the service
def test_07_Starting_SMB_service():
    results = PUT("/services/services/cifs/", {"srv_enable": "true"})
    assert results.status_code == 200, results.text
    sleep(2)


def test_08_Checking_to_see_if_SMB_service_is_enabled():
    results = GET("/services/services/cifs/")
    assert results.json()["srv_state"] == "RUNNING", results.text


def test_09_Changing_permissions_on_SMB_PATH():
    payload = {"mp_path": SMB_PATH,
               "mp_acl": "unix",
               "mp_mode": "777",
               "mp_user": "root",
               "mp_group": "wheel",
               "mp_recursive": True}
    results = PUT("/storage/permission/", payload)
    assert results.status_code == 201, results.text


def test_10_Creating_a_SMB_share_on_SMB_PATH():
    payload = {"cifs_comment": "My Test SMB Share",
               "cifs_path": SMB_PATH,
               "cifs_name": SMB_NAME,
               "cifs_guestok": True,
               "cifs_vfsobjects": "streams_xattr"}
    results = POST("/sharing/cifs/", payload)
    assert results.status_code == 201, results.text


# Mount share on OSX system and create a test file
@osx_host_cfg
def test_11_Create_mount_point_for_SMB_on_OSX_system():
    results = SSH_TEST('mkdir -p "%s"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_12_Mount_SMB_share_on_OSX_system():
    cmd = 'mount -t smbfs "smb://%s:' % ADUSERNAME
    cmd += '%s@%s/%s" "%s"' % (ADPASSWORD, ip, SMB_NAME, MOUNTPOINT)
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_13_Create_file_on_SMB_share_via_OSX_to_test_permissions():
    results = SSH_TEST('touch "%s/testfile.txt"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Move test file to a new location on the SMB share
@osx_host_cfg
def test_14_Moving_SMB_test_file_into_a_new_directory():
    cmd = 'mkdir -p "%s/tmp" && ' % MOUNTPOINT
    cmd += 'mv "%s/testfile.txt" ' % MOUNTPOINT
    cmd += '"%s/tmp/testfile.txt"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete test file and test directory from SMB share
@osx_host_cfg
def test_15_Deleting_test_file_and_directory_from_SMB_share():
    cmd = 'rm -f "%s/tmp/testfile.txt" && ' % MOUNTPOINT
    cmd += 'rmdir "%s/tmp"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_16_Verifying_that_test_file_directory_successfully_removed():
    cmd = 'find -- "%s/" -prune -type d -empty | grep -q .' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Clean up mounted SMB share
@osx_host_cfg
def test_17_Unmount_SMB_share():
    results = SSH_TEST('umount -f "%s"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Update tests
@osx_host_cfg
def test_18_Mount_SMB_share_on_OSX_system():
    cmd = 'mount -t smbfs "smb://%s:' % ADUSERNAME
    cmd += '%s@%s/%s" "%s"' % (ADPASSWORD, ip, SMB_NAME, MOUNTPOINT)
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_19_Create_file_on_SMB_share_via_OSX_to_test_permissions():
    results = SSH_TEST('touch "%s/testfile.txt"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Move test file to a new location on the SMB share
@osx_host_cfg
def test_20_Moving_SMB_test_file_into_a_new_directory():
    cmd = 'mkdir -p "%s/tmp" && ' % MOUNTPOINT
    cmd += 'mv "%s/testfile.txt" ' % MOUNTPOINT
    cmd += '"%s/tmp/testfile.txt"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete test file and test directory from SMB share
@osx_host_cfg
def test_21_Deleting_test_file_and_directory_from_SMB_share():
    cmd = 'rm -f "%s/tmp/testfile.txt" && ' % MOUNTPOINT
    cmd += 'rmdir "%s/tmp"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_22_Verifying_test_file_directory_were_successfully_removed():
    cmd = 'find -- "%s/" -prune -type d -empty | grep -q .' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Clean up mounted SMB share
@osx_host_cfg
def test_23_Unmount_SMB_share():
    results = SSH_TEST('umount -f "%s"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete tests
@osx_host_cfg
def test_24_Removing_SMB_mountpoint():
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Disable Active Directory Directory
def test_25_Disabling_Active_Directory_and_clear_kerberos_principal():
    payload = {
        "ad_netbiosname": hostname,
        "ad_idmap_backend": "ad",
        "ad_kerberos_principal": "",
        "ad_enable": False
    }
    results = PUT("/directoryservice/activedirectory/1/", payload)
    assert results.status_code == 200, results.text


# Check Active Directory
def test_26_Verify_Active_Directory_is_disabled():
    results = GET("/directoryservice/activedirectory/")
    assert results.json()["ad_enable"] is False, results.text
    sleep(1)


def test_27_Stop_SMB_service():
    results = PUT("/services/services/cifs/", {"srv_enable": False})
    assert results.status_code == 200, results.text
    sleep(1)


def test_28_Verify_SMB_service_is_disabled():
    results = GET("/services/services/cifs/")
    assert results.json()["srv_state"] == "STOPPED", results.text


def test_29_Delete_cifs_share_on_SMB_PATH():
    payload = {"cifs_comment": "My Test SMB Share",
               "cifs_path": SMB_PATH,
               "cifs_name": SMB_NAME,
               "cifs_guestok": True,
               "cifs_vfsobjects": "streams_xattr"}
    results = DELETE("/sharing/cifs/", payload)
    assert results.status_code == 204, results.text


# Check destroying a SMB dataset
def test_30_Destroying_SMB_dataset():
    results = DELETE(f"/storage/volume/{pool_name}/datasets/{DATASET}/")
    assert results.status_code == 204, results.text


def test_31_setting_back_the_old_nameserver():
    payload = {
        "gc_nameserver1": nameserver
    }
    results = PUT("/network/globalconfiguration/", payload)
    assert results.status_code == 200, results.text
