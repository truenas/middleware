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

if BRIDGEHOST in locals():
    MOUNTPOINT = "/tmp/afp-osx" + BRIDGEHOST
DATASET = "afp-osx"
AFP_NAME = "MyAFPShare"
AFP_PATH = "/mnt/tank/" + DATASET
VOL_GROUP = "qa"
Reason = "BRIDGEHOST is missing in ixautomation.conf"
OSXReason = 'OSX host configuration is mising in ixautomation.conf'

mount_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                         "MOUNTPOINT" in locals()
                                         ]) is False, reason=Reason)

osx_host_cfg = pytest.mark.skipif(all(["OSX_HOST" in locals(),
                                       "OSX_USERNAME" in locals(),
                                       "OSX_PASSWORD" in locals()
                                       ]) is False, reason=OSXReason)


# Clean up any leftover items from previous failed AD LDAP or SMB runs
def test_00_cleanup_tests():
    PUT("/services/afp/", {"afp_srv_guest": False})
    payload = {"afp_name": AFP_NAME, "afp_path": AFP_PATH}
    DELETE_ALL("/sharing/afp/", payload)
    DELETE("/storage/volume/1/datasets/%s/" % DATASET)
    # cmd = 'umount -f "%s"; rmdir "%s"; exit 0;' % (MOUNTPOINT, MOUNTPOINT)
    # SSH_TEST(cmd)


def test_01_Creating_AFP_dataset():
    assert POST("/storage/volume/tank/datasets/", {"name": DATASET}) == 201


def test_02_Updating_AFP_service():
    payload = {"afp_srv_connections_limit": "100"}
    assert PUT("/services/afp/", payload) == 200


def test_03_Enabling_AFP_service():
    payload = {"afp_srv_guest": True, "afp_srv_bindip": ip}
    assert PUT("/services/afp/", payload) == 200


# Now start the service
def test_04_Starting_AFP_service():
    assert PUT("/services/services/afp/", {"srv_enable": True}) == 200


def test_05_Checking_to_see_if_AFP_service_is_enabled():
    assert GET_OUTPUT("/services/services/afp/", "srv_state") == "RUNNING"


def test_06_Changing_permissions_on_AFP_PATH():
    payload = {"mp_path": AFP_PATH,
               "mp_acl": "unix",
               "mp_mode": "777",
               "mp_user": "root",
               "mp_group": "wheel"}
    assert PUT("/storage/permission/", payload) == 201


def test_07_Creating_a_AFP_share_on_AFP_PATH():
    payload = {"afp_name": AFP_NAME, "afp_path": AFP_PATH}
    assert POST("/sharing/afp/", payload) == 201


# Mount share on OSX system and create a test file
@mount_test_cfg
@osx_host_cfg
def test_08_Create_mount_point_for_AFP_on_OSX_system():
    assert SSH_TEST('mkdir -p "%s"' % MOUNTPOINT,
                    OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


@mount_test_cfg
@osx_host_cfg
def test_09_Mount_AFP_share_on_OSX_system():
    cmd = 'mount -t afp "afp://%s/%s" "%s"' % (ip, AFP_NAME, MOUNTPOINT)
    assert SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


@mount_test_cfg
@osx_host_cfg
def test_11_Create_file_on_AFP_share_via_OSX_to_test_permissions():
    assert SSH_TEST('touch "%s/testfile.txt"' % MOUNTPOINT,
                    OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


# Move test file to a new location on the AFP share
@mount_test_cfg
@osx_host_cfg
def test_12_Moving_AFP_test_file_into_a_new_directory():
    cmd = 'mkdir -p "%s/tmp" && ' % MOUNTPOINT
    cmd += 'mv "%s/testfile.txt" ' % MOUNTPOINT
    cmd += '"%s/tmp/testfile.txt"' % MOUNTPOINT
    assert SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


# Delete test file and test directory from AFP share
@mount_test_cfg
@osx_host_cfg
def test_13_Deleting_test_file_and_directory_from_AFP_share():
    cmd = 'rm -f "%s/tmp/testfile.txt" && ' % MOUNTPOINT
    cmd += 'rmdir "%s/tmp"' % MOUNTPOINT
    assert SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


@mount_test_cfg
@osx_host_cfg
def test_14_Verifying_test_file_directory_were_successfully_removed():
    cmd = 'find -- "%s/" -prune -type d -empty | grep -q .' % MOUNTPOINT
    assert SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


# Clean up mounted AFP share
@mount_test_cfg
@osx_host_cfg
def test_15_Unmount_AFP_share():
    assert SSH_TEST('umount -f "%s"' % MOUNTPOINT,
                    OSX_USERNAME, OSX_PASSWORD, OSX_HOST) is True


# Test disable AFP
def test_16_Verify_AFP_service_can_be_disabled():
    assert PUT("/services/afp/", {"afp_srv_guest": False}) == 200


# Test delete AFP dataset
def test_17_Verify_AFP_dataset_can_be_destroyed():
    assert DELETE("/storage/volume/1/datasets/%s/" % DATASET) == 204
