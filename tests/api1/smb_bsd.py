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
    MOUNTPOINT = "/tmp/smb-bsd" + BRIDGEHOST
DATASET = "smb-bsd"
SMB_NAME = "TestShare"
SMB_PATH = "/mnt/tank/" + DATASET
VOL_GROUP = "wheel"
Reason = "BRIDGEHOST are missing in ixautomation.conf"
BSDReason = 'BSD host configuration is missing in ixautomation.conf'

mount_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                         "MOUNTPOINT" in locals()
                                         ]) is False, reason=Reason)

bsd_host_cfg = pytest.mark.skipif(all(["BSD_HOST" in locals(),
                                       "BSD_USERNAME" in locals(),
                                       "BSD_PASSWORD" in locals()
                                       ]) is False, reason=BSDReason)


# Create tests
def test_01_Setting_auxilary_parameters_for_mount_smbfs():
    toload = "lanman auth = yes\nntlm auth = yes \nraw NTLMv2 auth = yes"
    payload = {"cifs_srv_smb_options": toload}
    results = PUT("/services/cifs/", payload)
    assert results.status_code == 200, results.text


def test_02_Creating_SMB_dataset():
    results = POST("/storage/volume/tank/datasets/", {"name": DATASET})
    assert results.status_code == 201, results.text


def test_03_Starting_SMB_service():
    results = PUT("/services/services/cifs/", {"srv_enable": True})
    assert results.status_code == 200, results.text


def test_04_Checking_to_see_if_SMB_service_is_running():
    results = GET("/services/services/cifs/")
    assert results.json()["srv_state"] == "RUNNING", results.text


def test_05_Changing_permissions_on_SMB_PATH():
    payload = {"mp_path": SMB_PATH,
               "mp_acl": "unix",
               "mp_mode": "777",
               "mp_user": "root",
               "mp_group": "wheel"}
    results = PUT("/storage/permission/", payload)
    assert results.status_code == 201, results.text


def test_06_Creating_a_SMB_share_on_SMB_PATH():
    payload = {"cfs_comment": "My Test SMB Share",
               "cifs_path": SMB_PATH,
               "cifs_name": SMB_NAME,
               "cifs_guestok": True,
               "cifs_vfsobjects": "streams_xattr"}
    results = POST("/sharing/cifs/", payload)
    assert results.status_code == 201, results.text


# Now check if we can mount SMB / create / rename / copy / delete / umount
@mount_test_cfg
@bsd_host_cfg
def test_07_Creating_SMB_mountpoint():
    results = SSH_TEST('mkdir -p "%s" && sync' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_08_Mounting_SMB():
    cmd = 'mount_smbfs -N -I %s ' % ip
    cmd += '"//guest@testnas/%s" "%s"' % (SMB_NAME, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_09_Creating_SMB_file():
    results = SSH_TEST("touch %s/testfile" % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_10_Moving_SMB_file():
    cmd = 'mv %s/testfile %s/testfile2' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_11_Copying_SMB_file():
    cmd = 'cp %s/testfile2 %s/testfile' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_12_Deleting_SMB_file_1_2():
    results = SSH_TEST('rm "%s/testfile"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_13_Deleting_SMB_file_2_2():
    results = SSH_TEST('rm "%s/testfile2"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_14_Unmounting_SMB():
    results = SSH_TEST('umount -f %s' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


# Update tests
@mount_test_cfg
@bsd_host_cfg
def test_15_Mounting_SMB():
    cmd = 'mount_smbfs -N -I %s ' % ip
    cmd += '"//guest@testnas/%s" "%s"' % (SMB_NAME, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_16_Creating_SMB_file():
    results = SSH_TEST('touch %s/testfile' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_17_Moving_SMB_file():
    cmd = 'mv %s/testfile %s/testfile2' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_18_Copying_SMB_file():
    cmd = 'cp %s/testfile2 %s/testfile' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_19_Deleting_SMB_file_1_2():
    results = SSH_TEST('rm %s/testfile' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_20_Deleting_SMB_file_2_2():
    results = SSH_TEST('rm %s/testfile2' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_21_Unmounting_SMB():
    results = SSH_TEST('umount -f %s' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


# Delete tests
@mount_test_cfg
@bsd_host_cfg
def test_22_Removing_SMB_mountpoint():
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


def test_23_SMB_share_on_SMB_PATH():
    payload = {"cfs_comment": "My Test SMB Share",
               "cifs_path": SMB_PATH,
               "cifs_name": SMB_NAME,
               "cifs_guestok": True,
               "cifs_vfsobjects": "streams_xattr"}
    results = DELETE_ALL("/sharing/cifs/", payload)
    assert results.status_code == 204, results.text


# Now stop the service
def test_24_Stopping_SMB_service():
    results = PUT("/services/services/cifs/", {"srv_enable": False})
    assert results.status_code == 200, results.text


def test_25_Verify_SMB_service_is_disabled():
    results = GET("/services/services/cifs/")
    assert results.json()["srv_state"] == "STOPPED", results.text


# Check destroying a SMB dataset
def test_26_Destroying_SMB_dataset():
    results = DELETE("/storage/volume/1/datasets/%s/" % DATASET)
    assert results.status_code == 204, results.text
