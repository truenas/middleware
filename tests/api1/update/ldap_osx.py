#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET_OUTPUT, DELETE, DELETE_ALL
from functions import SSH_TEST
from auto_config import ip
from config import *

if "BRIDGEHOST" in locals():
    MOUNTPOINT = "/tmp/ldap-osx" + BRIDGEHOST

DATASET = "ldap-osx"
SMB_NAME = "TestShare"
SMB_PATH = "/mnt/tank/%s" % DATASET
LDAP_USER = "ldapuser"
LDAP_PASS = "12345678"
VOL_GROUP = "wheel"
Reason = "BRIDGEHOST, LDAPBASEDN and LDAPHOSTNAME are not in ixautomation.conf"
OSXReason = 'OSX host configuration is missing in ixautomation.conf'

ldap_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                        "LDAPBASEDN" in locals(),
                                        "LDAPHOSTNAME" in locals(),
                                        "MOUNTPOINT" in locals()
                                        ]) is False, reason=Reason)

osx_host_cfg = pytest.mark.skipif(all(["OSX_HOST" in locals(),
                                       "OSX_USERNAME" in locals(),
                                       "OSX_PASSWORD" in locals()
                                       ]) is False, reason=OSXReason)


# Clean up any leftover items from previous failed AD LDAP or SMB runs
@osx_host_cfg
@ldap_test_cfg
def test_00_cleanup_tests():
    # Clean up any leftover items from previous failed AD LDAP or SMB runs
    payload2 = {"ldap_basedn": LDAPBASEDN,
                "ldap_anonbind": False,
                "ldap_netbiosname_a": BRIDGEHOST,
                "ldap_hostname": LDAPHOSTNAME,
                "ldap_has_samba_schema": True,
                "ldap_enable": False}
    PUT("/directoryservice/ldap/1/", payload2)
    PUT("/services/services/cifs/", {"srv_enable": False})
    payload3 = {"cfs_comment": "My Test SMB Share",
                "cifs_path": SMB_PATH,
                "cifs_name": SMB_NAME,
                "cifs_guestok": True,
                "cifs_vfsobjects": "streams_xattr"}
    DELETE_ALL("/sharing/cifs/", payload3)
    DELETE("/storage/volume/1/datasets/%s/" % DATASET)
    cmd = 'umount -f "%s"; rmdir "%s"; exit 0' % (MOUNTPOINT, MOUNTPOINT)
    SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)


# Set auxilary parameters to allow mount_smbfs to work with ldap
def test_01_Creating_SMB_dataset():
    assert POST("/storage/volume/tank/datasets/", {"name": DATASET}) == 201


# Enable LDAP
@ldap_test_cfg
def test_02_Enabling_LDAP():
    payload = {"ldap_basedn": LDAPBASEDN2,
               "ldap_binddn": LDAPBINDDN2,
               "ldap_bindpw": LDAPBINDPASSWORD2,
               "ldap_netbiosname_a": BRIDGEHOST,
               "ldap_hostname": LDAPHOSTNAME2,
               "ldap_has_samba_schema": True,
               "ldap_enable": True}
    assert PUT("/directoryservice/ldap/1/", payload) == 200


# Check LDAP
@ldap_test_cfg
def test_03_Checking_LDAP():
    assert GET_OUTPUT("/directoryservice/ldap/", "ldap_enable") is True


def test_04_Enabling_SMB_service():
    payload = {"cifs_srv_description": "Test FreeNAS Server",
               "cifs_srv_guest": "nobody",
               "cifs_hostname_lookup": False,
               "cifs_srv_aio_enable": False}
    assert PUT("/services/cifs/", payload) == 200


# Now start the service
def test_05_Starting_SMB_service():
    assert PUT("/services/services/cifs/", {"srv_enable": True}) == 200


@ldap_test_cfg
def test_06_Checking_to_see_if_SMB_service_is_enabled():
    assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "RUNNING"


def test_07_Changing_permissions_on_SMB_PATH():
    payload = {"mp_path": SMB_PATH,
               "mp_acl": "unix",
               "mp_mode": "777",
               "mp_user": "root",
               "mp_group": "wheel",
               "mp_recursive": True}
    assert PUT("/storage/permission/", payload) == 201


def test_08_Creating_a_SMB_share_on_SMB_PATH():
    payload = {"cfs_comment": "My Test SMB Share",
               "cifs_path": SMB_PATH,
               "cifs_name": SMB_NAME,
               "cifs_guestok": True,
               "cifs_vfsobjects": "streams_xattr"}
    assert POST("/sharing/cifs/", payload) == 201


# Mount share on OSX system and create a test file
@osx_host_cfg
@ldap_test_cfg
def test_09_Create_mount_point_for_SMB_on_OSX_system():
    assert SSH_TEST('mkdir -p "%s"' % MOUNTPOINT,
                    OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


@osx_host_cfg
@ldap_test_cfg
def test_10_Mount_SMB_share_on_OSX_system():
    cmd = 'mount -t smbfs "smb://%s:%s' % (LDAP_USER, LDAP_PASS)
    cmd += '@%s/%s" "%s"' % (ip, SMB_NAME, MOUNTPOINT)
    assert SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


@osx_host_cfg
@ldap_test_cfg
def test_12_Create_file_on_SMB_share_via_OSX_to_test_permissions():
    assert SSH_TEST('touch "%s/testfile.txt"' % MOUNTPOINT,
                    OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


# Move test file to a new location on the SMB share
@osx_host_cfg
@ldap_test_cfg
def test_13_Moving_SMB_test_file_into_a_new_directory():
    cmd = 'mkdir -p "%s/tmp" && ' % MOUNTPOINT
    cmd += 'mv "%s/testfile.txt" ' % MOUNTPOINT
    cmd += '"%s/tmp/testfile.txt"' % MOUNTPOINT
    assert SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


# Delete test file and test directory from SMB share
@osx_host_cfg
@ldap_test_cfg
def test_14_Deleting_test_file_and_directory_from_SMB_share():
    cmd = 'rm -f "%s/tmp/testfile.txt" && ' % MOUNTPOINT
    cmd += 'rmdir "%s/tmp"' % MOUNTPOINT
    assert SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


@osx_host_cfg
@ldap_test_cfg
def test_15_Verifying_test_file_directory_were_successfully_removed():
    cmd = 'find -- "%s/" -prune -type d -empty | grep -q .' % MOUNTPOINT
    assert SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


# Clean up mounted SMB share
@osx_host_cfg
@ldap_test_cfg
def test_16_Unmount_SMB_share():
    assert SSH_TEST('umount -f "%s"' % MOUNTPOINT,
                    OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


def test_17_Removing_SMB_share_on_SMB_PATH():
    payload = {"cfs_comment": "My Test SMB Share",
               "cifs_path": SMB_PATH,
               "cifs_name": SMB_NAME,
               "cifs_guestok": True,
               "cifs_vfsobjects": "streams_xattr"}
    assert DELETE_ALL("/sharing/cifs/", payload) == 204


# Disable LDAP
@ldap_test_cfg
def test_18_Disabling_LDAP():
    payload = {"ldap_basedn": LDAPBASEDN2,
               "ldap_binddn": LDAPBINDDN2,
               "ldap_bindpw": LDAPBINDPASSWORD2,
               "ldap_netbiosname_a": BRIDGEHOST,
               "ldap_hostname": LDAPHOSTNAME2,
               "ldap_has_samba_schema": True,
               "ldap_enable": False}
    assert PUT("/directoryservice/ldap/1/", payload) == 200


# Now stop the SMB service
def test_19_Stopping_SMB_service():
    assert PUT("/services/services/cifs/", {"srv_enable": False}) == 200


# Check LDAP
@ldap_test_cfg
def test_20_Verify_LDAP_is_disabledd():
    assert GET_OUTPUT("/directoryservice/ldap/", "ldap_enable") is False


@ldap_test_cfg
def test_21_Verify_SMB_service_has_shut_down():
    assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "STOPPED"


# Check destroying a SMB dataset
def test_22_Destroying_SMB_dataset():
    assert DELETE("/storage/volume/1/datasets/%s/" % DATASET) == 204
