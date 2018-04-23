#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE, DELETE_ALL, SSH_TEST
from auto_config import ip
from config import *

if "BRIDGEHOST" in locals():
    MOUNTPOINT = "/tmp/ldap-osx" + BRIDGEHOST
DATASET = "ldap-osx"
SMB_NAME = "TestShare"
SMB_PATH = "/mnt/tank/" + DATASET
VOL_GROUP = "qa"
Reason = "BRIDGEHOST, LDAPBASEDN and LDAPHOSTNAME are not in ixautomation.conf"
OSXReason = 'OSX host configuration is missing in ixautomation.conf'

ldap_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                        "LDAPBASEDN" in locals(),
                                        "LDAPBINDDN" in locals(),
                                        "LDAPHOSTNAME" in locals(),
                                        "LDAPBINDPASSWORD" in locals(),
                                        "MOUNTPOINT" in locals()
                                        ]) is False, reason=Reason)

up_ldap_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                           "LDAPBASEDN2" in locals(),
                                           "LDAPBINDDN2" in locals(),
                                           "LDAPHOSTNAME2" in locals(),
                                           "LDAPBINDPASSWORD2" in locals(),
                                           "MOUNTPOINT" in locals()
                                           ]) is False, reason=Reason)

osx_host_cfg = pytest.mark.skipif(all(["OSX_HOST" in locals(),
                                       "OSX_USERNAME" in locals(),
                                       "OSX_PASSWORD" in locals()
                                       ]) is False, reason=OSXReason)


# Create tests
# Set auxilary parameters to allow mount_smbfs to work with ldap
def test_01_Creating_SMB_dataset():
    results = POST("/storage/volume/tank/datasets/", {"name": DATASET})
    assert results.status_code == 201, results.text


# Enable LDAP
@ldap_test_cfg
def test_02_Enabling_LDAPd():
    payload = {"ldap_basedn": LDAPBASEDN,
               "ldap_binddn": LDAPBINDDN,
               "ldap_bindpw": LDAPBINDPASSWORD,
               "ldap_netbiosname_a": BRIDGEHOST,
               "ldap_hostname": LDAPHOSTNAME,
               "ldap_has_samba_schema": True,
               "ldap_enable": True}
    results = PUT("/directoryservice/ldap/1/", payload)
    assert results.status_code == 200, results.text


# Check LDAP
@ldap_test_cfg
def test_03_Checking_LDAP():
    results = GET("/directoryservice/ldap/")
    assert results.json()["ldap_enable"] is True, results.text


def test_04_Enabling_SMB_service():
    payload = {"cifs_srv_description": "Test FreeNAS Server",
               "cifs_srv_guest": "nobody",
               "cifs_hostname_lookup": False,
               "cifs_srv_aio_enable": False}
    results = PUT("/services/cifs/", payload)
    assert results.status_code == 200, results.text


# Now start the service
def test_05_Starting_SMB_service():
    results = PUT("/services/services/cifs/", {"srv_enable": True})
    assert results.status_code == 200, results.text


@ldap_test_cfg
def test_06_Checking_to_see_if_SMB_service_is_enabled():
    results = GET("/services/services/cifs/")
    assert results.json()["srv_state"] == "RUNNING", results.text


def test_07_Changing_permissions_on_SMB_PATH():
    payload = {"mp_path": SMB_PATH,
               "mp_acl": "unix",
               "mp_mode": "777",
               "mp_user": "root",
               "mp_group": "wheel",
               "mp_recursive": True}
    results = PUT("/storage/permission/", payload)
    assert results.status_code == 201, results.text


def test_08_Creating_a_SMB_share_on_SMB_PATH():
    payload = {"cfs_comment": "My Test SMB Share",
               "cifs_path": SMB_PATH,
               "cifs_name": SMB_NAME,
               "cifs_guestok": True,
               "cifs_vfsobjects": "streams_xattr"}
    results = POST("/sharing/cifs/", payload)
    assert results.status_code == 201, results.text


# Mount share on OSX system and create a test file
@osx_host_cfg
@ldap_test_cfg
def test_09_Create_mount_point_for_SMB_on_OSX_system():
    results = SSH_TEST('mkdir -p "%s"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
@ldap_test_cfg
def test_10_Mount_SMB_share_on_OSX_system():
    cmd = 'mount -t smbfs "smb://ldapuser:12345678'
    cmd += '@%s/%s" %s' % (ip, SMB_NAME, MOUNTPOINT)
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
@ldap_test_cfg
def test_11_Create_file_on_SMB_share_via_OSX_to_test_permissions():
    results = SSH_TEST('touch "%s/testfile.txt"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Move test file to a new location on the SMB share
@osx_host_cfg
@ldap_test_cfg
def test_12_Moving_SMB_test_file_into_a_new_directory():
    cmd = 'mkdir -p "%s/tmp" && ' % MOUNTPOINT
    cmd += 'mv "%s/testfile.txt" ' % MOUNTPOINT
    cmd += '"%s/tmp/testfile.txt"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete test file and test directory from SMB share
@osx_host_cfg
@ldap_test_cfg
def test_13_Deleting_test_file_and_directory_from_SMB_share():
    cmd = 'rm -f "%s/tmp/testfile.txt" && ' % MOUNTPOINT
    cmd += 'rmdir "%s/tmp"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
@ldap_test_cfg
def test_14_Verifying_test_file_directory_were_successfully_removed():
    cmd = 'find -- "%s/" -prune -type d -empty | grep -q .' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Clean up mounted SMB share
@osx_host_cfg
@ldap_test_cfg
def test_15_Unmount_SMB_share():
    results = SSH_TEST('umount -f "%s"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Update tests
# Enable LDAP
@up_ldap_test_cfg
def test_16_Enabling_LDAP():
    payload = {"ldap_basedn": LDAPBASEDN2,
               "ldap_binddn": LDAPBINDDN2,
               "ldap_bindpw": LDAPBINDPASSWORD2,
               "ldap_netbiosname_a": BRIDGEHOST,
               "ldap_hostname": LDAPHOSTNAME2,
               "ldap_has_samba_schema": True,
               "ldap_enable": True}
    results = PUT("/directoryservice/ldap/1/", payload)
    assert results.status_code == 200, results.text


# Check LDAP
@up_ldap_test_cfg
def test_17_Checking_LDAP():
    results = GET("/directoryservice/ldap/")
    assert results.json()["ldap_enable"] is True, results.text


@osx_host_cfg
@up_ldap_test_cfg
def test_18_Mount_SMB_share_on_OSX_system():
    cmd = 'mount -t smbfs "smb://ldapuser:12345678'
    cmd += '@%s/%s" "%s"' % (ip, SMB_NAME, MOUNTPOINT)
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
@up_ldap_test_cfg
def test_20_Create_file_on_SMB_share_via_OSX_to_test_permissions():
    results = SSH_TEST('touch "%s/testfile.txt"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Move test file to a new location on the SMB share
@osx_host_cfg
@up_ldap_test_cfg
def test_21_Moving_SMB_test_file_into_a_new_directory():
    cmd = 'mkdir -p "%s/tmp" && ' % MOUNTPOINT
    cmd += 'mv "%s/testfile.txt" ' % MOUNTPOINT
    cmd += '"%s/tmp/testfile.txt"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete test file and test directory from SMB share
@osx_host_cfg
@up_ldap_test_cfg
def test_22_Deleting_test_file_and_directory_from_SMB_share():
    cmd = 'rm -f "%s/tmp/testfile.txt" && ' % MOUNTPOINT
    cmd += 'rmdir "%s/tmp"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
@up_ldap_test_cfg
def test_23_Verifying_test_file_directory_were_successfully_removed():
    cmd = 'find -- "%s/" -prune -type d -empty | grep -q .' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Clean up mounted SMB share
@osx_host_cfg
@up_ldap_test_cfg
def test_24_Unmount_SMB_share():
    results = SSH_TEST('umount -f "%s"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete tests
@osx_host_cfg
@ldap_test_cfg
def test_25_Removing_SMB_mountpoint():
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


def test_26_Removing_SMB_share_on_SMB_PATH():
    payload = {"cfs_comment": "My Test SMB Share",
               "cifs_path": SMB_PATH,
               "cifs_name": SMB_NAME,
               "cifs_guestok": True,
               "cifs_vfsobjects": "streams_xattr"}
    results = DELETE_ALL("/sharing/cifs/", payload)
    assert results.status_code == 204, results.text


# Disable LDAP
@up_ldap_test_cfg
def test_27_Disabling_LDAP():
    payload = {"ldap_basedn": LDAPBASEDN2,
               "ldap_binddn": LDAPBINDDN2,
               "ldap_bindpw": LDAPBINDPASSWORD2,
               "ldap_netbiosname_a": BRIDGEHOST,
               "ldap_hostname": LDAPHOSTNAME2,
               "ldap_has_samba_schema": True,
               "ldap_enable": False}
    results = PUT("/directoryservice/ldap/1/", payload)
    assert results.status_code == 200, results.text


# Now stop the SMB service
def test_28_Stopping_SMB_service():
    results = PUT("/services/services/cifs/", {"srv_enable": False})
    assert results.status_code == 200, results.text


# Check LDAP
@ldap_test_cfg
def test_29_Verify_LDAP_is_disabledd():
    results = GET("/directoryservice/ldap/")
    assert results.json()["ldap_enable"] is False, results.text


@ldap_test_cfg
def test_30_Verify_SMB_service_has_shut_down():
    results = GET("/services/services/cifs/")
    assert results.json()["srv_state"] == "STOPPED", results.text


# Check destroying a SMB dataset
def test_31_Destroying_SMB_dataset():
    results = DELETE("/storage/volume/1/datasets/%s/" % DATASET)
    assert results.status_code == 204, results.text
