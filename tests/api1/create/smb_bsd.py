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
from functions import PUT, POST, GET_OUTPUT, DELETE, DELETE_ALL, BSD_TEST
from auto_config import ip
try:
    from config import BRIDGEHOST
except ImportError:
    RunTest = False
else:
    MOUNTPOINT = "/tmp/smb-bsd" + BRIDGEHOST
    RunTest = True

TestName = "create smb bsd"
DATASET = "smb-bsd"
SMB_NAME = "TestShare"
SMB_PATH = "/mnt/tank/" + DATASET
VOL_GROUP = "wheel"

Reason = "BRIDGEHOST are not in ixautomation.conf"


class create_smb_bsd_test(unittest.TestCase):

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
        # BSD_TEST to add when functional
        cmd = 'umount -f "%s" &>/dev/null; ' % MOUNTPOINT
        cmd += 'rmdir "%s" &>/dev/null' % MOUNTPOINT
        BSD_TEST(cmd)

    def test_01_Setting_auxilary_parameters_for_mount_smbfs(self):
        toload = "lanman auth = yes\nntlm auth = yes \nraw NTLMv2 auth = yes"
        payload = {"cifs_srv_smb_options": toload}
        assert PUT("/services/cifs/", payload) == 200

    def test_02_Creating_SMB_dataset(self):
        assert POST("/storage/volume/tank/datasets/", {"name": DATASET}) == 201

    def test_03_Starting_SMB_service(self):
        assert PUT("/services/services/cifs/", {"srv_enable": True}) == 200

    def test_04_Checking_to_see_if_SMB_service_is_running(self):
        assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "RUNNING"

    def test_05_Changing_permissions_on_SMB_PATH(self):
        payload = {"mp_path": SMB_PATH,
                   "mp_acl": "unix",
                   "mp_mode": "777",
                   "mp_user": "root",
                   "mp_group": "wheel"}
        assert PUT("/storage/permission/", payload) == 201

    def test_06_Creating_a_SMB_share_on_SMB_PATH(self):
        payload = {"cfs_comment": "My Test SMB Share",
                   "cifs_path": SMB_PATH,
                   "cifs_name": SMB_NAME,
                   "cifs_guestok": True,
                   "cifs_vfsobjects": "streams_xattr"}
        assert POST("/sharing/cifs/", payload) == 201

    # Now check if we can mount SMB / create / rename / copy / delete / umount
    @pytest.mark.skipif(RunTest is False, reason=Reason)
    def test_07_Creating_SMB_mountpoint(self):
        assert BSD_TEST('mkdir -p "%s" && sync' % MOUNTPOINT) is True

    @pytest.mark.skipif(RunTest is False, reason=Reason)
    def test_08_Mounting_SMB(self):
        cmd = 'mount_smbfs -N -I %s ' % ip
        cmd += '"//guest@testnas/%s" "%s"' % (SMB_NAME, MOUNTPOINT)
        assert BSD_TEST(cmd) is True

    @pytest.mark.skipif(RunTest is False, reason=Reason)
    def test_10_Creating_SMB_file(self):
        assert BSD_TEST("touch %s/testfile" % MOUNTPOINT) is True

    @pytest.mark.skipif(RunTest is False, reason=Reason)
    def test_11_Moving_SMB_file(self):
        cmd = 'mv %s/testfile %s/testfile2' % (MOUNTPOINT, MOUNTPOINT)
        assert BSD_TEST(cmd) is True

    @pytest.mark.skipif(RunTest is False, reason=Reason)
    def test_12_Copying_SMB_file(self):
        cmd = 'cp %s/testfile2 %s/testfile' % (MOUNTPOINT, MOUNTPOINT)
        assert BSD_TEST(cmd) is True

    @pytest.mark.skipif(RunTest is False, reason=Reason)
    def test_13_Deleting_SMB_file_1_2(self):
        assert BSD_TEST('rm "%s/testfile"' % MOUNTPOINT) is True

    @pytest.mark.skipif(RunTest is False, reason=Reason)
    def test_14_Deleting_SMB_file_2_2(self):
        assert BSD_TEST('rm "%s/testfile2"' % MOUNTPOINT) is True

    @pytest.mark.skipif(RunTest is False, reason=Reason)
    def test_15_Unmounting_SMB(self):
        assert BSD_TEST('umount -f %s' % MOUNTPOINT) is True

    @pytest.mark.skipif(RunTest is False, reason=Reason)
    def test_16_Removing_SMB_mountpoint(self):
        cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
        assert BSD_TEST(cmd) is True

    def test_17_SMB_share_on_SMB_PATH(self):
        payload = {"cfs_comment": "My Test SMB Share",
                   "cifs_path": SMB_PATH,
                   "cifs_name": SMB_NAME,
                   "cifs_guestok": True,
                   "cifs_vfsobjects": "streams_xattr"}
        assert DELETE_ALL("/sharing/cifs/", payload) == 204

    # Now stop the service
    def test_18_Stopping_SMB_service(self):
        assert PUT("/services/services/cifs/", {"srv_enable": False}) == 200

    def test_19_Verify_SMB_service_is_disabled(self):
        assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "STOPPED"

    # Check destroying a SMB dataset
    def test_20_Destroying_SMB_dataset(self):
        assert DELETE("/storage/volume/1/datasets/%s/" % DATASET) == 204
