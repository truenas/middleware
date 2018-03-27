#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET_OUTPUT, DELETE, DELETE_ALL, SSH_TEST
from config import *

if BRIDGEHOST in locals():
    MOUNTPOINT = "/tmp/ad-osx" + BRIDGEHOST
DATASET = "ad-osx"
SMB_NAME = "TestShare"
SMB_PATH = "/mnt/tank/" + DATASET
VOL_GROUP = "qa"
Reason = "BRIDGEHOST, BRIDGEDOMAIN, ADPASSWORD, and ADUSERNAME are missing in "
Reason += "ixautomation.conf"
OSXReason = 'OSX host configuration is mising in ixautomation.conf'

ad_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                      "BRIDGEDOMAIN" in locals(),
                                      "ADPASSWORD" in locals(),
                                      "ADUSERNAME" in locals(),
                                      "MOUNTPOINT" in locals()
                                      ]) is False, reason=Reason)

osx_host_cfg = pytest.mark.skipif(all(["OSX_HOST" in locals(),
                                       "OSX_USERNAME" in locals(),
                                       "OSX_PASSWORD" in locals()
                                       ]) is False, reason=OSXReason)


# Clean up any leftover items from previous failed AD LDAP or SMB runs
@ad_test_cfg
def test_00_cleanup_tests():
    payload = {"ad_bindpw": ADPASSWORD,
               "ad_bindname": ADUSERNAME,
               "ad_domainname": BRIDGEDOMAIN,
               "ad_netbiosname_a": BRIDGEHOST,
               "ad_idmap_backend": "rid",
               "ad_enable": False}
    PUT("/directoryservice/activedirectory/1/", payload)
    PUT("/services/services/cifs/", {"srv_enable": False})
    payload = {"cfs_comment": "My Test SMB Share",
               "cifs_path": SMB_PATH,
               "cifs_name": SMB_NAME,
               "cifs_guestok": True,
               "cifs_vfsobjects": "streams_xattr"}
    DELETE_ALL("/sharing/cifs/", payload)
    DELETE("/storage/volume/1/datasets/%s/" % DATASET)


# Set auxilary parameters allow mount_smbfs to work with Active Directory
def test_01_Creating_SMB_dataset():
    assert POST("/storage/volume/tank/datasets/", {"name": DATASET}) == 201


# Enable Active Directory Directory
@ad_test_cfg
def test_02_Enabling_Active_Directory():
    payload = {"ad_bindpw": ADPASSWORD,
               "ad_bindname": ADUSERNAME,
               "ad_domainname": BRIDGEDOMAIN,
               "ad_netbiosname_a": BRIDGEHOST,
               "ad_idmap_backend": "ad",
               "ad_enable": True}
    assert PUT("/directoryservice/activedirectory/1/", payload)


# Check Active Directory
@ad_test_cfg
def test_03_Checking_Active_Directory():
    assert GET_OUTPUT("/directoryservice/activedirectory/",
                      "ad_enable") is True


@ad_test_cfg
def test_04_Checking_to_see_if_SMB_service_is_enabled(seff):
    assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "RUNNING"


def test_05_Enabling_SMB_service():
    payload = {"cifs_srv_description": "Test FreeNAS Server",
               "cifs_srv_guest": "nobody",
               "cifs_hostname_lookup": False,
               "cifs_srv_aio_enable": False}
    assert PUT("/services/cifs/", payload) == 200


# Now start the service
def test_06_Starting_SMB_service():
    assert PUT("/services/services/cifs/", {"srv_enable": True}) == 200


# Mount share on OSX system and create a test file
@osx_host_cfg
@ad_test_cfg
def test_07_Create_mount_point_for_SMB_on_OSX_system():
    assert SSH_TEST('mkdir -p "%s"' % MOUNTPOINT,
                    OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


# @osx_host_cfg
# @ad_test_cfg
# def test_08_Mount_SMB_share_on_OSX_system():
#     cmd = 'mount -t smbfs "smb://%s:' % ADUSERNAME
#     cmd += '%s@%s/%s" "%s"' % (ADPASSWORD, ip, SMB_NAME, MOUNTPOINT)
#     assert SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


@osx_host_cfg
@ad_test_cfg
def test_10_Create_file_on_SMB_share_via_OSX_to_test_permissions():
    assert SSH_TEST('touch "%s/testfile.txt"' % MOUNTPOINT,
                    OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


# Move test file to a new location on the SMB share
@osx_host_cfg
@ad_test_cfg
def test_11_Moving_SMB_test_file_into_a_new_directory():
    cmd = 'mkdir -p "%s/tmp" && ' % MOUNTPOINT
    cmd += 'mv "%s/testfile.txt" ' % MOUNTPOINT
    cmd += '"%s/tmp/testfile.txt"' % MOUNTPOINT
    assert SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


# Delete test file and test directory from SMB share
@osx_host_cfg
@ad_test_cfg
def test_12_Deleting_test_file_and_directory_from_SMB_share():
    cmd = 'rm -f "%s/tmp/testfile.txt" && ' % MOUNTPOINT
    cmd += 'rmdir "%s/tmp"' % MOUNTPOINT
    assert SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


@osx_host_cfg
@ad_test_cfg
def test_13_Verifying_test_file_directory_were_successfully_removed():
    cmd = 'find -- "%s/" -prune -type d -empty | grep -q .' % MOUNTPOINT
    assert SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True

# Clean up mounted SMB share
# @osx_host_cfg
# @ad_test_cfg
# def test_14_Unmount_SMB_share():
#     assert SSH_TEST('umount -f "%s"' % MOUNTPOINT,
#                     OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


# Disable Active Directory Directory
@ad_test_cfg
def test_15_Disabling_Active_Directory():
    payload = {"ad_bindpw": ADPASSWORD,
               "ad_bindname": ADUSERNAME,
               "ad_domainname": BRIDGEDOMAIN,
               "ad_netbiosname_a": BRIDGEHOST,
               "ad_idmap_backend": "ad",
               "ad_enable": False}
    assert PUT("/directoryservice/activedirectory/1/", payload) == 200


# Check Active Directory
@ad_test_cfg
def test_16_Verify_Active_Directory_is_disabled():
    assert GET_OUTPUT("/directoryservice/activedirectory/",
                      "ad_enable") is False


@ad_test_cfg
def test_17_Verify_SMB_service_is_disabled():
    assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "STOPPED"


# Check destroying a SMB dataset
def test_18_Destroying_SMB_dataset():
    assert DELETE("/storage/volume/1/datasets/%s/" % DATASET) == 204
