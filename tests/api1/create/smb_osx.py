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
from auto_config import ip
from config import *

if "BRIDGEHOST" in locals():
    MOUNTPOINT = "/tmp/smb-osx" + BRIDGEHOST

DATASET = "smb-osx"
SMB_NAME = "TestShare"
SMB_PATH = "/mnt/tank/" + DATASET
VOL_GROUP = "wheel"

Reason = "BRIDGEHOST is missing in ixautomation.conf"
OSXReason = 'OSX host configuration is missing in ixautomation.conf'

mount_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                         "MOUNTPOINT" in locals()
                                         ]) is False, reason=Reason)

osx_host_cfg = pytest.mark.skipif(all(["OSX_HOST" in locals(),
                                       "OSX_USERNAME" in locals(),
                                       "OSX_PASSWORD" in locals()
                                       ]) is False, reason=OSXReason)


def test_01_Creating_SMB_dataset():
    assert POST("/storage/volume/tank/datasets/", {"name": DATASET}) == 201


def test_02_Starting_SMB_service():
    assert PUT("/services/services/cifs/", {"srv_enable": True}) == 200


def test_03_Changing_permissions_on_SMB_PATH():
    payload = {"mp_path": SMB_PATH,
               "mp_acl": "unix",
               "mp_mode": "777",
               "mp_user": "root",
               "mp_group": "wheel"}
    assert PUT("/storage/permission/", payload) == 201


def test_04_Creating_a_SMB_share_on_SMB_PATH():
    payload = {"cfs_comment": "My Test SMB Share",
               "cifs_path": SMB_PATH,
               "cifs_name": SMB_NAME,
               "cifs_guestok": True,
               "cifs_vfsobjects": "streams_xattr"}
    assert POST("/sharing/cifs/", payload) == 201


def test_05_Checking_to_see_if_SMB_service_is_running():
    assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "RUNNING"


# Mount share on OSX system and create a test file
@mount_test_cfg
@osx_host_cfg
def test_06_Create_mount_point_for_SMB_on_OSX_system():
    assert SSH_TEST('mkdir -p "%s"' % MOUNTPOINT,
                    OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


@mount_test_cfg
@osx_host_cfg
def test_07_Mount_SMB_share_on_OSX_system():
    cmd = 'mount -t smbfs "smb://guest'
    cmd += '@%s/%s" "%s"' % (ip, SMB_NAME, MOUNTPOINT)
    assert SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


# @mount_test_cfg
# @osx_host_cfg
# def test_08_Checking_permissions_on_MOUNTPOINT():
#     device_name = return_output('dirname "%s"' % MOUNTPOINT)
#     cmd = 'ls -la "%s" | ' % device_name
#     cmd += 'awk \'$4 == "%s" && $9 == "%s"\'' % (VOL_GROUP, DATASET)
#     assert SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


@mount_test_cfg
@osx_host_cfg
def test_09_Create_file_on_SMB_share_via_OSX_to_test_permissions():
    assert SSH_TEST('touch "%s/testfile.txt"' % MOUNTPOINT,
                    OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


# Move test file to a new location on the SMB share
@mount_test_cfg
@osx_host_cfg
def test_10_Moving_SMB_test_file_into_a_new_directory():
    cmd = 'mkdir -p "%s/tmp" ' % MOUNTPOINT
    cmd += '&& mv "%s/testfile.txt" ' % MOUNTPOINT
    cmd += '"%s/tmp/testfile.txt"' % MOUNTPOINT
    assert SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


# Delete test file and test directory from SMB share
@mount_test_cfg
@osx_host_cfg
def test_11_Deleting_test_file_and_directory_from_SMB_share():
    cmd = 'rm -f "%s/tmp/testfile.txt" ' % MOUNTPOINT
    cmd += '&& rmdir "%s/tmp"' % MOUNTPOINT
    assert SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


@mount_test_cfg
@osx_host_cfg
def test_12_Verifying_test_file_directory_were_successfully_removed():
    cmd = 'find -- "%s/" -prune -type d -empty | grep -q .' % MOUNTPOINT
    assert SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


# Clean up mounted SMB share
@mount_test_cfg
@osx_host_cfg
def test_13_Unmount_SMB_share():
    assert SSH_TEST('umount -f "%s"' % MOUNTPOINT,
                    OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


def test_14_Removing_SMB_share_on_SMB_PATH():
    payload = {"cfs_comment": "My Test SMB Share",
               "cifs_path": SMB_PATH,
               "cifs_name": SMB_NAME,
               "cifs_guestok": True,
               "cifs_vfsobjects": "streams_xattr"}
    assert DELETE_ALL("/sharing/cifs/", payload) == 204


# Now stop the service
def test_15_Stopping_SMB_service():
    assert PUT("/services/services/cifs/", {"srv_enable": False}) == 200


def test_16_Verify_SMB_service_is_disabled():
    assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "STOPPED"


# Check destroying a SMB dataset
def test_17_Destroying_SMB_dataset():
    assert DELETE("/storage/volume/1/datasets/%s/" % DATASET) == 204
