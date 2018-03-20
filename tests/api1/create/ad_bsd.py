#!/usr/bin/env python3.6
# Author: Eric Turgeon.
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
    from config import BRIDGEHOST, BRIDGEDOMAIN, ADPASSWORD, ADUSERNAME
    from config import LDAPBASEDN, LDAPBINDDN, LDAPHOSTNAME, LDAPBINDPASSWORD
except ImportError:
    RunTest = False
else:
    MOUNTPOINT = "/tmp/ad-bsd" + BRIDGEHOST
    RunTest = True
TestName = "create ad bsd"

DATASET = "ad-bsd"
SMB_NAME = "TestShare"
SMB_PATH = "/mnt/tank/" + DATASET
VOL_GROUP = "wheel"
Reason = "BRIDGEHOST, BRIDGEDOMAIN, ADPASSWORD, ADUSERNAME, LDAPBASEDN, "
Reason += "LDAPBINDDN, LDAPHOSTNAME and  LDAPBINDPASSWORD are not in "
Reason += "ixautomation.conf"


@pytest.mark.skipif(RunTest is False, reason=Reason)
class create_ad_bsd_test(unittest.TestCase):

    # Clean up any leftover items from previous failed runs
    @classmethod
    def setUpClass(inst):
        payload1 = {"ad_bindpw": ADPASSWORD,
                    "ad_bindname": ADUSERNAME,
                    "ad_domainname": BRIDGEDOMAIN,
                    "ad_netbiosname_a": BRIDGEHOST,
                    "ad_idmap_backend": "rid",
                    "ad_enable": False}
        PUT("/directoryservice/activedirectory/1/", payload1) == 200
        payload2 = {"ldap_basedn": LDAPBASEDN,
                    "ldap_binddn": LDAPBINDDN,
                    "ldap_bindpw": LDAPBINDPASSWORD,
                    "ldap_netbiosname_a": BRIDGEHOST,
                    "ldap_hostname": LDAPHOSTNAME,
                    "ldap_has_samba_schema": "true",
                    "ldap_enable": "false"}
        PUT("/directoryservice/ldap/1/", payload2) == 200
        PUT("/services/services/cifs/", {"srv_enable": "false"}) == 200
        payload3 = {"cfs_comment": "My Test SMB Share",
                    "cifs_path": SMB_PATH,
                    "cifs_name": SMB_NAME,
                    "cifs_guestok": "true",
                    "cifs_vfsobjects": "streams_xattr"}
        DELETE_ALL("/sharing/cifs/", payload3) == 204
        DELETE("/storage/volume/1/datasets/%s/" % DATASET) == 204
        BSD_TEST("umount -f " + MOUNTPOINT)
        BSD_TEST("rmdir " + MOUNTPOINT)

    def test_01_creating_smb_dataset(self):
        assert POST("/storage/volume/tank/datasets/", {"name": DATASET}) == 201

    def test_02_enabling_active_directory(self):
        payload = {"ad_bindpw": ADPASSWORD,
                   "ad_bindname": ADUSERNAME,
                   "ad_domainname": BRIDGEDOMAIN,
                   "ad_netbiosname_a": BRIDGEHOST,
                   "ad_idmap_backend": "rid",
                   "ad_enable": True}
        assert PUT("/directoryservice/activedirectory/1/", payload) == 200

    def test_03_checking_active_directory(self):
        assert GET_OUTPUT("/directoryservice/activedirectory/",
                          "ad_enable") is True

    def test_04_checking_to_see_if_smb_service_is_enabled(self):
        assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "RUNNING"

    def test_05_enabling_smb_service(self):
        payload = {"cifs_srv_description": "Test FreeNAS Server",
                   "cifs_srv_guest": "nobody",
                   "cifs_hostname_lookup": False,
                   "cifs_srv_aio_enable": False}
        assert PUT("/services/cifs/", payload) == 200

    # Now start the service
    def test_06_Starting_SMB_service(self):
        assert PUT("/services/services/cifs/", {"srv_enable": "true"}) == 200

    def test_07_Changing_permissions_on_SMB_PATH(self):
        payload = {"mp_path": SMB_PATH,
                   "mp_acl": "unix",
                   "mp_mode": "777",
                   "mp_user": "root",
                   "mp_group": "wheel",
                   "mp_recursive": True}
        assert PUT("/storage/permission/", payload) == 201

    def test_08_Creating_a_SMB_share_on_SMB_PATH(self):
        payload = {"cfs_comment": "My Test SMB Share",
                   "cifs_path": SMB_PATH,
                   "cifs_name": SMB_NAME,
                   "cifs_guestok": "true",
                   "cifs_vfsobjects": "streams_xattr"}
        assert POST("/sharing/cifs/", payload) == 201

    def test_09_creating_smb_mountpoint(self):
        assert BSD_TEST('mkdir -p "%s" && sync' % MOUNTPOINT) is True

    # The ADUSER user must exist in AD with this password
    def test_10_Store_AD_credentials_in_a_file_for_mount_smbfs(self):
        cmd = 'echo "[TESTNAS:ADUSER]" > ~/.nsmbrc && '
        cmd += 'echo "password=12345678" >> ~/.nsmbrc'
        assert BSD_TEST(cmd) is True

    def test_11_Mounting_SMB(self):
        cmd = 'mount_smbfs -N -I %s -W AD01 ' % ip
        cmd += '"//aduser@testnas/%s" "%s"' % (SMB_NAME, MOUNTPOINT)
        assert BSD_TEST(cmd) is True

    def test_13_Creating_SMB_file(self):
        assert BSD_TEST('touch "%s/testfile"' % MOUNTPOINT) is True

    def test_14_Moving_SMB_file(self):
        cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
        assert BSD_TEST(cmd) is True

    def test_15_Copying_SMB_file(self):
        cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
        assert BSD_TEST(cmd) is True

    def test_16_Deleting_SMB_file_1_2(self):
        assert BSD_TEST('rm "%s/testfile"' % MOUNTPOINT) is True

    def test_17_Deleting_SMB_file_2_2(self):
        assert BSD_TEST('rm "%s/testfile2"' % MOUNTPOINT) is True

    def test_18_Unmounting_SMB(self):
        assert BSD_TEST('umount "%s"' % MOUNTPOINT) is True

    def test_19_Removing_SMB_mountpoint(self):
        cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
        assert BSD_TEST(cmd) is True

    # Disable Active Directory Directory
    def test_20_disabling_active_directory(self):
        payload = {"ad_bindpw": ADPASSWORD,
                   "ad_bindname": ADUSERNAME,
                   "ad_domainname": BRIDGEDOMAIN,
                   "ad_netbiosname_a": BRIDGEHOST,
                   "ad_idmap_backend": "rid",
                   "ad_enable": "false"}
        assert PUT("/directoryservice/activedirectory/1/", payload) == 200

    # Check Active Directory
    def test_21_Verify_Active_Directory_is_disabled(self):
        assert GET_OUTPUT("/directoryservice/activedirectory/",
                          "ad_enable") is False

    def test_22_Verify_SMB_service_is_disabled(self):
        assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "STOPPED"

    # Check destroying a SMB dataset
    def test_23_Destroying_SMB_dataset(self):
        assert DELETE("/storage/volume/1/datasets/%s/" % DATASET) == 204
