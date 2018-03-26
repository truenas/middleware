#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET_OUTPUT, DELETE, DELETE_ALL, BSD_TEST
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


# Clean up any leftover items from previous failed AD LDAP or SMB runs
@mount_test_cfg
@bsd_host_cfg
def test_00_cleanup_tests():
    PUT("/services/services/cifs/", {"srv_enable": False})
    payload3 = {"cfs_comment": "My Test SMB Share",
                "cifs_path": SMB_PATH,
                "cifs_name": SMB_NAME,
                "cifs_guestok": True,
                "cifs_vfsobjects": "streams_xattr"}
    DELETE_ALL("/sharing/cifs/", payload3)
    DELETE("/storage/volume/1/datasets/%s/" % DATASET)
    # BSD_TEST to add when functional
    cmd = 'umount -f "%s" &>/dev/null; ' % MOUNTPOINT
    cmd += 'rmdir "%s" &>/dev/null' % MOUNTPOINT
    BSD_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)


def test_01_Setting_auxilary_parameters_for_mount_smbfs():
    toload = "lanman auth = yes\nntlm auth = yes \nraw NTLMv2 auth = yes"
    payload = {"cifs_srv_smb_options": toload}
    assert PUT("/services/cifs/", payload) == 200


def test_02_Creating_SMB_dataset():
    assert POST("/storage/volume/tank/datasets/", {"name": DATASET}) == 201


def test_03_Starting_SMB_service():
    assert PUT("/services/services/cifs/", {"srv_enable": True}) == 200


def test_04_Checking_to_see_if_SMB_service_is_running():
    assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "RUNNING"


def test_05_Changing_permissions_on_SMB_PATH():
    payload = {"mp_path": SMB_PATH,
               "mp_acl": "unix",
               "mp_mode": "777",
               "mp_user": "root",
               "mp_group": "wheel"}
    assert PUT("/storage/permission/", payload) == 201


def test_06_Creating_a_SMB_share_on_SMB_PATH():
    payload = {"cfs_comment": "My Test SMB Share",
               "cifs_path": SMB_PATH,
               "cifs_name": SMB_NAME,
               "cifs_guestok": True,
               "cifs_vfsobjects": "streams_xattr"}
    assert POST("/sharing/cifs/", payload) == 201


# Now check if we can mount SMB / create / rename / copy / delete / umount
@mount_test_cfg
@bsd_host_cfg
def test_07_Creating_SMB_mountpoint():
    assert BSD_TEST('mkdir -p "%s" && sync' % MOUNTPOINT,
                    BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@mount_test_cfg
@bsd_host_cfg
def test_08_Mounting_SMB():
    cmd = 'mount_smbfs -N -I %s ' % ip
    cmd += '"//guest@testnas/%s" "%s"' % (SMB_NAME, MOUNTPOINT)
    assert BSD_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@mount_test_cfg
@bsd_host_cfg
def test_10_Creating_SMB_file():
    assert BSD_TEST("touch %s/testfile" % MOUNTPOINT,
                    BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@mount_test_cfg
@bsd_host_cfg
def test_11_Moving_SMB_file():
    cmd = 'mv %s/testfile %s/testfile2' % (MOUNTPOINT, MOUNTPOINT)
    assert BSD_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@mount_test_cfg
@bsd_host_cfg
def test_12_Copying_SMB_file():
    cmd = 'cp %s/testfile2 %s/testfile' % (MOUNTPOINT, MOUNTPOINT)
    assert BSD_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@mount_test_cfg
@bsd_host_cfg
def test_13_Deleting_SMB_file_1_2():
    assert BSD_TEST('rm "%s/testfile"' % MOUNTPOINT,
                    BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@mount_test_cfg
@bsd_host_cfg
def test_14_Deleting_SMB_file_2_2():
    assert BSD_TEST('rm "%s/testfile2"' % MOUNTPOINT,
                    BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@mount_test_cfg
@bsd_host_cfg
def test_15_Unmounting_SMB():
    assert BSD_TEST('umount -f %s' % MOUNTPOINT,
                    BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@mount_test_cfg
@bsd_host_cfg
def test_16_Removing_SMB_mountpoint():
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    assert BSD_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


def test_17_SMB_share_on_SMB_PATH():
    payload = {"cfs_comment": "My Test SMB Share",
               "cifs_path": SMB_PATH,
               "cifs_name": SMB_NAME,
               "cifs_guestok": True,
               "cifs_vfsobjects": "streams_xattr"}
    assert DELETE_ALL("/sharing/cifs/", payload) == 204


# Now stop the service
def test_18_Stopping_SMB_service():
    assert PUT("/services/services/cifs/", {"srv_enable": False}) == 200


def test_19_Verify_SMB_service_is_disabled():
    assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "STOPPED"


# Check destroying a SMB dataset
def test_20_Destroying_SMB_dataset():
    assert DELETE("/storage/volume/1/datasets/%s/" % DATASET) == 204
