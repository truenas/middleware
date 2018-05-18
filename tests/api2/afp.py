#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, SSH_TEST
from auto_config import ip
from config import *

if "BRIDGEHOST" in locals():
    MOUNTPOINT = "/tmp/afp" + BRIDGEHOST
DATASET = "afp"
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


# have to wait for the volume api
# def test_01_Creating_afp_dataset():
#     results = POST("/storage/volume/tank/datasets/", {"name": DATASET})
#     assert results.status_code == 201, results.text


def test_02_setting_afp():
    payload = {"guest": True,
               "bindip": [ip]}
    results = PUT("/afp", payload)
    assert results.status_code == 200, results.text


def test_03_enable_afp_service_at_boot():
    results = PUT("/service/id/afp", {"enable": True})
    assert results.status_code == 200, results.text


def test_04_checking_afp_enable_at_boot():
    results = GET("/service?service=afp")
    assert results.json()[0]['enable'] == True, results.text


def test_05_Start_afp_service():
    payload = {"service": "afp", "service-control": {"onetime": True}}
    results = POST("/service/start", payload)
    assert results.status_code == 200, results.text


def test_06_checking_if_afp_is_running():
    results = GET("/service?service=afp")
    assert results.json()[0]['state'] == "RUNNING", results.text

# have to wait for the volume api
# def test_07_Changing_permissions_on_afp_path():
#     payload = {"mp_path": AFP_PATH,
#                "mp_acl": "unix",
#                "mp_mode": "777",
#                "mp_user": "root",
#                "mp_group": "wheel"}
#     results = PUT("/storage/permission/", payload)
#     assert results.status_code == 201, results.text


# def test_08_Creating_a_afp_share_on_afp_path():
#     payload = {"name": AFP_NAME, "path": AFP_PATH}
#     results = POST("/sharing/afp", payload)
#     assert results.status_code == 201, results.text

# have to wait for the volume api
# Mount share on OSX system and create a test file
@mount_test_cfg
@osx_host_cfg
def test_09_create_mount_point_for_afp_on_osx_system():
    results = SSH_TEST('mkdir -p "%s"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@osx_host_cfg
def test_10_mount_afp_share_on_osx_system():
    cmd = 'mount -t afp "afp://%s/%s" "%s"' % (ip, AFP_NAME, MOUNTPOINT)
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@osx_host_cfg
def test_11_create_file_on_afp_share_via_osx_to_test_permissions():
    results = SSH_TEST('touch "%s/testfile.txt"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Move test file to a new location on the AFP share
@mount_test_cfg
@osx_host_cfg
def test_12_moving_afp_test_file_into_a_new_directory():
    cmd = 'mkdir -p "%s/tmp" && ' % MOUNTPOINT
    cmd += 'mv "%s/testfile.txt" ' % MOUNTPOINT
    cmd += '"%s/tmp/testfile.txt"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete test file and test directory from AFP share
@mount_test_cfg
@osx_host_cfg
def test_13_deleting_test_file_and_directory_from_afp_share():
    cmd = 'rm -f "%s/tmp/testfile.txt" && ' % MOUNTPOINT
    cmd += 'rmdir "%s/tmp"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@osx_host_cfg
def test_14_verifying_test_file_directory_were_successfully_removed():
    cmd = 'find -- "%s/" -prune -type d -empty | grep -q .' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Clean up mounted AFP share
@mount_test_cfg
@osx_host_cfg
def test_15_unmount_afp_share():
    results = SSH_TEST("umount -f '%s'" % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Update tests
@mount_test_cfg
@osx_host_cfg
def test_16_mount_afp_share_on_osx_system():
    cmd = 'mount -t afp "afp://%s/%s" "%s"' % (ip, AFP_NAME, MOUNTPOINT)
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@osx_host_cfg
def test_17_create_file_on_afp_share_via_osx_to_test_permissions():
    results = SSH_TEST('touch "%s/testfile.txt"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Move test file to a new location on the AFP share
@mount_test_cfg
@osx_host_cfg
def test_18_moving_afp_test_file_into_a_new_directory():
    cmd = 'mkdir -p "%s/tmp" && ' % MOUNTPOINT
    cmd += 'mv "%s/testfile.txt" ' % MOUNTPOINT
    cmd += '"%s/tmp/testfile.txt"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete test file and test directory from AFP share
@mount_test_cfg
@osx_host_cfg
def test_19_deleting_test_file_and_directory_from_afp_share():
    cmd = 'rm -f "%s/tmp/testfile.txt" && ' % MOUNTPOINT
    cmd += 'rmdir "%s/tmp"' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@osx_host_cfg
def test_20_verifying_test_file_directory_were_successfully_removed():
    cmd = 'find -- "%s/" -prune -type d -empty | grep -q .' % MOUNTPOINT
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Clean up mounted AFP share
@mount_test_cfg
@osx_host_cfg
def test_21_unmount_afp_share():
    results = SSH_TEST('umount -f "%s"' % MOUNTPOINT,
                       OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete tests
@mount_test_cfg
@osx_host_cfg
def test_22_removing_SMB_mountpoint():
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


def test_25_stopping_afp_service():
    payload = {"service": "afp", "service-control": {"onetime": True}}
    results = POST("/service/stop", payload)
    assert results.status_code == 200, results.text


def test_26_checking_if_afp_is_stop():
    results = GET("/service?service=afp")
    assert results.json()[0]['state'] == "STOPPED", results.text


# Test disable AFP
def test_23_disable_afp_service_at_boot():
    results = PUT("/service/id/afp", {"enable": False})
    assert results.status_code == 200, results.text


def test_24_checking_afp_disable_at_boot():
    results = GET("/service?service=afp")
    assert results.json()[0]['enable'] == False, results.text
