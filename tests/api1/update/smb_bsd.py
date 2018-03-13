#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import unittest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET_OUTPUT, DELETE, DELETE_ALL
from functions import BSD_TEST

try:
    from config import BRIDGEHOST
except ImportError:
    RunTest = False
else:
    MOUNTPOINT = "/tmp/smb-bsd" + BRIDGEHOST
    RunTest = True

TestName = "update smb bsd"

DATASET = "smb-bsd2"
SMB_NAME = "TestShare"
SMB_PATH = "/mnt/thank/" + DATASET
VOL_GROUP = "wheel"
Reason = "BRIDGEHOST ixautomation.conf"


class update_smb_bsd_test(unittest.TestCase):

    # Clean up any leftover items from previous failed AD LDAP or SMB runs
    @pytest.mark.skipif(RunTest is False, reason=Reason)
    @classmethod
    def setUpClass(inst):
        PUT("/services/services/cifs/", {"srv_enable": False})
        payload3 = {"cfs_comment": "My Test SMB Share",
                    "cifs_path": SMB_PATH,
                    "cifs_name": SMB_NAME,
                    "cifs_guestok": True,
                    "cifs_vfsobjects": "streams_xattr"}
        DELETE_ALL("/sharing/cifs/", payload3)
        DELETE("/storage/volume/1/datasets/%s/" % DATASET)
        cmd = 'umount -f "%s" &>/dev/null; ' % MOUNTPOINT
        cmd += 'rmdir "%s" &>/dev/null' % MOUNTPOINT
        BSD_TEST(cmd)

    # Set auxilary parameters to allow mount_smbfs to work
    def test_01_Setting_auxilary_parameters_for_mount_smbfs(self):
        option = "lanman auth = yes\nntlm auth = yes \nraw NTLMv2 auth = yes"
        payload = {"cifs_srv_smb_options": option}
        assert PUT("/services/cifs/", payload) == 200

    def test_02_Creating_SMB_dataset(self):
        assert POST("/storage/volume/tank/datasets/", {"name": DATASET}) == 201

    def test_03_Updating_SMB_service(self):
        assert PUT("/services/cifs/", {"cifs_srv_hostlookup": False}) == 200

    # Now start the service
    def test_04_Starting_SMB_service(self):
        assert PUT("/services/services/cifs/", {"srv_enable": True}) == 200

    def test_05_Checking_to_see_if_SMB_service_is_enabled(self):
        assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "RUNNING"

    def test_06_Changing_permissions_on_SMB_PATH(self):
        payload = {"mp_path": SMB_PATH,
                   "mp_acl": "unix",
                   "mp_mode": "777",
                   "mp_user": "root",
                   "mp_group": "wheel"}
        assert PUT("/storage/permission/", payload) == 201

    # def test_07_Creating_a_SMB_share_on_SMB_PATH(self):
    #     payload = {"cfs_comment": "My Test SMB Share",
    #                "cifs_path": SMB_PATH,
    #                "cifs_name": SMB_NAME,
    #                "cifs_guestok": True,
    #                "cifs_vfsobjects": "streams_xattr"}
    #     assert POST("/sharing/cifs/", payload) == 201

    # Now check if we can mount SMB / create / rename / copy / delete / umount
    @pytest.mark.skipif(RunTest is False, reason=Reason)
    def test_08_Creating_SMB_mountpoint(self):
        assert BSD_TEST('mkdir "%s" && sync' % MOUNTPOINT) is True

    # def test_09_Mounting_SMB(self):
    #     cmd = 'mount_smbfs -N -I %s ' % ip
    #     cmd += '"//guest@testnas/%s" "%s"' % (SMB_NAME, MOUNTPOINT)
    #     assert BSD_TEST(cmd) is True

    @pytest.mark.skipif(RunTest is False, reason=Reason)
    def test_11_Creating_SMB_file(self):
        assert BSD_TEST('touch %s/testfile' % MOUNTPOINT) is True

    @pytest.mark.skipif(RunTest is False, reason=Reason)
    def test_12_Moving_SMB_file(self):
        cmd = 'mv %s/testfile %s/testfile2' % (MOUNTPOINT, MOUNTPOINT)
        assert BSD_TEST(cmd) is True

    @pytest.mark.skipif(RunTest is False, reason=Reason)
    def test_13_Copying_SMB_file(self):
        cmd = 'cp %s/testfile2 %s/testfile' % (MOUNTPOINT, MOUNTPOINT)
        assert BSD_TEST(cmd) is True

    @pytest.mark.skipif(RunTest is False, reason=Reason)
    def test_14_Deleting_SMB_file_1_2(self):
        assert BSD_TEST('rm %s/testfile' % MOUNTPOINT) is True

    @pytest.mark.skipif(RunTest is False, reason=Reason)
    def test_15_Deleting_SMB_file_2_2(self):
        assert BSD_TEST('rm %s/testfile2' % MOUNTPOINT) is True

    # def test_16_Unmounting_SMB(self):
    #     assert BSD_TEST('umount -f %s' % MOUNTPOINT) is True

    @pytest.mark.skipif(RunTest is False, reason=Reason)
    def test_17_Removing_SMB_mountpoint(self):
        cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
        assert BSD_TEST(cmd) is True

    def test_18_Removing_SMB_share_on_SMB_PATH(self):
        payload = {"cfs_comment": "My Test SMB Share",
                   "cifs_path": SMB_PATH,
                   "cifs_name": SMB_NAME,
                   "cifs_guestok": True,
                   "cifs_vfsobjects": "streams_xattr"}
        assert DELETE_ALL("/sharing/cifs/", payload) == 204

    # Now stop the service
    def test_19_Stopping_SMB_service(self):
        assert PUT("/services/services/cifs/", {"srv_enable": False}) == 200

    def test_20_Verify_SMB_service_is_disabled(self):
        assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "STOPPED"

    # Check destroying a SMB dataset
    def test_21_Destroying_SMB_dataset(self):
        assert DELETE("/storage/volume/1/datasets/%s/" % DATASET) == 204
