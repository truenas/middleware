#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, SSH_TEST, DELETE_ALL, DELETE
from auto_config import ip
from config import *

if "BRIDGEHOST" in locals():
    MOUNTPOINT = "/tmp/afp-osx" + BRIDGEHOST
DATASET = "afp-osx"
AFP_NAME = "MyAFPShare"
AFP_PATH = "/mnt/tank/" + DATASET
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


# Create tests
def test_01_Creating_AFP_dataset():
    results = POST("/storage/volume/tank/datasets/", {"name": DATASET})
    assert results.status_code == 201, results.text


def test_02_Enabling_AFP_service():
    payload = {"afp_srv_guest": "true",
               "afp_srv_bindip": ip}
    results = PUT("/services/afp/", payload)
    assert results.status_code == 200, results.text


def test_03_Starting_AFP_service():
    results = PUT("/services/services/afp/", {"srv_enable": "true"})
    assert results.status_code == 200, results.text


def test_04_Checking_to_see_if_AFP_service_is_enabled():
    results = GET("/services/services/afp/")
    assert results.json()["srv_state"] == "RUNNING", results.text


def test_05_Changing_permissions_on_AFP_PATH():
    payload = {"mp_path": AFP_PATH,
               "mp_acl": "unix",
               "mp_mode": "777",
               "mp_user": "root",
               "mp_group": "wheel"}
    results = PUT("/storage/permission/", payload)
    assert results.status_code == 201, results.text


def test_06_Creating_a_AFP_share_on_AFP_PATH():
    payload = {"afp_name": AFP_NAME, "afp_path": AFP_PATH}
    results = POST("/sharing/afp/", payload)
    assert results.status_code == 201, results.text


# Mount share on OSX system and create a test file
@mount_test_cfg
@osx_host_cfg
def test_07_Create_mount_point_for_AFP_on_OSX_system():
    results = SSH_TEST('mkdir -p "%s"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@osx_host_cfg
def test_08_Mount_AFP_share_on_OSX_system():
    cmd = 'mount -t afp "afp://%s/%s" "%s"' % (ip, AFP_NAME, MOUNTPOINT)
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@osx_host_cfg
def test_10_Create_file_on_AFP_share_via_OSX_to_test_permissions():
    results = SSH_TEST('touch "%s/testfile.txt"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Move test file to a new location on the AFP share
@mount_test_cfg
@osx_host_cfg
def test_11_Moving_AFP_test_file_into_a_new_directory():
    cmd = 'mkdir -p "%s/tmp" && ' % MOUNTPOINT
    cmd += 'mv "%s/testfile.txt" ' % MOUNTPOINT
    cmd += '"%s/tmp/testfile.txt"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete test file and test directory from AFP share
@mount_test_cfg
@osx_host_cfg
def test_12_Deleting_test_file_and_directory_from_AFP_share():
    cmd = 'rm -f "%s/tmp/testfile.txt" && ' % MOUNTPOINT
    cmd += 'rmdir "%s/tmp"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@osx_host_cfg
def test_13_Verifying_test_file_directory_were_successfully_removed():
    cmd = 'find -- "%s/" -prune -type d -empty | grep -q .' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Clean up mounted AFP share
@mount_test_cfg
@osx_host_cfg
def test_14_Unmount_AFP_share():
    results = SSH_TEST("umount -f '%s'" % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Update tests
@mount_test_cfg
@osx_host_cfg
def test_16_Mount_AFP_share_on_OSX_system():
    cmd = 'mount -t afp "afp://%s/%s" "%s"' % (ip, AFP_NAME, MOUNTPOINT)
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@osx_host_cfg
def test_17_Create_file_on_AFP_share_via_OSX_to_test_permissions():
    results = SSH_TEST('touch "%s/testfile.txt"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Move test file to a new location on the AFP share
@mount_test_cfg
@osx_host_cfg
def test_18_Moving_AFP_test_file_into_a_new_directory():
    cmd = 'mkdir -p "%s/tmp" && ' % MOUNTPOINT
    cmd += 'mv "%s/testfile.txt" ' % MOUNTPOINT
    cmd += '"%s/tmp/testfile.txt"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete test file and test directory from AFP share
@mount_test_cfg
@osx_host_cfg
def test_19_Deleting_test_file_and_directory_from_AFP_share():
    cmd = 'rm -f "%s/tmp/testfile.txt" && ' % MOUNTPOINT
    cmd += 'rmdir "%s/tmp"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@osx_host_cfg
def test_20_Verifying_test_file_directory_were_successfully_removed():
    cmd = 'find -- "%s/" -prune -type d -empty | grep -q .' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Clean up mounted AFP share
@mount_test_cfg
@osx_host_cfg
def test_21_Unmount_AFP_share():
    results = SSH_TEST('umount -f "%s"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete tests
@mount_test_cfg
@osx_host_cfg
def test_22_Removing_SMB_mountpoint():
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Test disable AFP
def test_23_Verify_AFP_service_can_be_disabled():
    results = PUT("/services/afp/", {"afp_srv_guest": "false"})
    assert results.status_code == 200, results.text


def test_24_Verify_delete_afp_name_and_afp_path():
    payload = {"afp_name": AFP_NAME, "afp_path": AFP_PATH}
    results = DELETE_ALL("/sharing/afp/", payload)
    assert results.status_code == 204, results.text


# Test delete AFP dataset
def test_25_Verify_AFP_dataset_can_be_destroyed():
    results = DELETE("/storage/volume/1/datasets/%s/" % DATASET)
    assert results.status_code == 204, results.text
