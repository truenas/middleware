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
from config import *

if "BRIDGEHOST" in locals():
    MOUNTPOINT = "/tmp/ad-bsd" + BRIDGEHOST
DATASET = "ad-bsd"
SMB_NAME = "TestShare"
SMB_PATH = "/mnt/tank/" + DATASET
VOL_GROUP = "wheel"

Reason = "BRIDGEHOST, BRIDGEDOMAIN, ADPASSWORD, and ADUSERNAME are missing in "
Reason += "ixautomation.conf"
BSDReason = 'BSD host configuration is missing in ixautomation.conf'

ad_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                      "BRIDGEDOMAIN" in locals(),
                                      "ADPASSWORD" in locals(),
                                      "ADUSERNAME" in locals(),
                                      "MOUNTPOINT" in locals()
                                      ]) is False, reason=Reason)

bsd_host_cfg = pytest.mark.skipif(all(["BSD_HOST" in locals(),
                                       "BSD_USERNAME" in locals(),
                                       "BSD_PASSWORD" in locals()
                                       ]) is False, reason=BSDReason)


@ad_test_cfg
class update_ad_bsd_test(unittest.TestCase):

    # Clean up any leftover items from previous failed AD LDAP or SMB runs
    @bsd_host_cfg
    @classmethod
    @bsd_host_cfg
    def setUpClass(inst):
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
        cmd = 'umount -f "%s" &>/dev/null; '
        cmd += 'rmdir "%s" &>/dev/null'
        BSD_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)

    # Set auxilary parameters allow mount_smbfs to work with Active Directory
    def test_01_Creating_SMB_dataset(self):
        assert POST("/storage/volume/tank/datasets/", {"name": DATASET}) == 201

    # Enable Active Directory Directory
    def test_02_Enabling_Active_Directory(self):
        payload = {"ad_bindpw": ADPASSWORD,
                   "ad_bindname": ADUSERNAME,
                   "ad_domainname": BRIDGEDOMAIN,
                   "ad_netbiosname_a": BRIDGEHOST,
                   "ad_idmap_backend": "ad",
                   "ad_enable": True}
        assert PUT("/directoryservice/activedirectory/1/", payload)

    # Check Active Directory
    def test_03_Checking_Active_Directory(self):
        assert GET_OUTPUT("/directoryservice/activedirectory/",
                          "ad_enable") is True

    def test_04_Checking_to_see_if_SMB_service_is_enabled(seff):
        assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "RUNNING"

    def test_05_Enabling_SMB_service(self):
        payload = {"cifs_srv_description": "Test FreeNAS Server",
                   "cifs_srv_guest": "nobody",
                   "cifs_hostname_lookup": False,
                   "cifs_srv_aio_enable": False}
        assert PUT("/services/cifs/", payload) == 200

    # Now start the service
    def test_06_Starting_SMB_service(self):
        assert PUT("/services/services/cifs/", {"srv_enable": True}) == 200

    @bsd_host_cfg
    def test_07_creating_smb_mountpoint(self):
        assert BSD_TEST('mkdir -p "%s" && sync' % MOUNTPOINT,
                        BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True

    # The ADUSER user must exist in AD with this password
    @bsd_host_cfg
    def test_08_Store_AD_credentials_in_a_file_for_mount_smbfs(self):
        cmd = 'echo "[TESTNAS:ADUSER]" > ~/.nsmbrc && '
        cmd += 'echo "password=12345678" >> ~/.nsmbrc'
        assert BSD_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True

    # def test_09_Mounting_SMB(self):
    #     cmd = 'mount_smbfs -N -I %s -W AD01 ' % ip
    #     cmd += '"//aduser@testnas/%s" "%s"' % (SMB_NAME, MOUNTPOINT)
    #     assert BSD_TEST(cmd) is True

    @bsd_host_cfg
    def test_11_Creating_SMB_file(self):
        assert BSD_TEST('touch "%s/testfile"' % MOUNTPOINT,
                        BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True

    @bsd_host_cfg
    def test_12_Moving_SMB_file(self):
        cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
        assert BSD_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True

    @bsd_host_cfg
    def test_13_Copying_SMB_file(self):
        cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
        assert BSD_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True

    @bsd_host_cfg
    def test_14_Deleting_SMB_file_1_2(self):
        assert BSD_TEST('rm "%s/testfile"' % MOUNTPOINT,
                        BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True

    @bsd_host_cfg
    def test_15_Deleting_SMB_file_2_2(self):
        assert BSD_TEST('rm "%s/testfile2"' % MOUNTPOINT,
                        BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True

    # def test_16_Unmounting_SMB(self):
    #     assert BSD_TEST('umount "%s"' % MOUNTPOINT) is True

    @bsd_host_cfg
    def test_17_Removing_SMB_mountpoint(self):
        cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
        assert BSD_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True

    # Disable Active Directory Directory
    def test_18_Disabling_Active_Directory(self):
        payload = {"ad_bindpw": ADPASSWORD,
                   "ad_bindname": ADUSERNAME,
                   "ad_domainname": BRIDGEDOMAIN,
                   "ad_netbiosname_a": BRIDGEHOST,
                   "ad_idmap_backend": "ad",
                   "ad_enable": False}
        assert PUT("/directoryservice/activedirectory/1/", payload) == 200

    # Check Active Directory
    def test_19_Verify_Active_Directory_is_disabled(self):
        assert GET_OUTPUT("/directoryservice/activedirectory/",
                          "ad_enable") is False

    def test_20_Verify_SMB_service_is_disabled(self):
        assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "STOPPED"

    # Check destroying a SMB dataset
    def test_21_Destroying_SMB_dataset(self):
        assert DELETE("/storage/volume/1/datasets/%s/" % DATASET) == 204
