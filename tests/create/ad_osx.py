#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import unittest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET_OUTPUT, PUT, DELETE, DELETE_ALL, OSX_TEST
from functions import SSH_TEST, return_output
from auto_config import ip

try:
    from config import BRIDGEHOST, BRIDGEDOMAIN, ADPASSWORD, ADUSERNAME
    from config import LDAPBASEDN, LDAPBINDDN, LDAPBINDPASSWORD, LDAPHOSTNAME
except ImportError:
    exit()

DATASET = "ad-osx"
SMB_NAME = "TestShare"
SMB_PATH = "/mnt/tank/" + DATASET
MOUNTPOINT = "/tmp/ad-osx" + BRIDGEHOST
VOL_GROUP = "wheel"


class ad_osx_test(unittest.TestCase):

    # Clean up any leftover items from previous failed AD LDAP or SMB runs
    @classmethod
    def setUpClass(inst):
        payload1 = {"ad_bindpw": ADPASSWORD,
                    "ad_bindname": ADUSERNAME,
                    "ad_domainname": BRIDGEDOMAIN,
                    "ad_netbiosname_a": BRIDGEHOST,
                    "ad_idmap_backend": "rid",
                    "ad_enable": "false"}
        PUT("/directoryservice/activedirectory/1/", payload1)
        payload2 = {"ldap_basedn": LDAPBASEDN,
                    "ldap_binddn": LDAPBINDDN,
                    "ldap_bindpw": LDAPBINDPASSWORD,
                    "ldap_netbiosname_a": BRIDGEHOST,
                    "ldap_hostname": LDAPHOSTNAME,
                    "ldap_has_samba_schema": "true",
                    "ldap_enable": "false"}
        PUT("/directoryservice/ldap/1/", payload2)
        PUT("/services/services/cifs/", {"srv_enable": "false"})
        payload3 = {"cfs_comment": "My Test SMB Share",
                    "cifs_path": SMB_PATH,
                    "cifs_name": SMB_NAME,
                    "cifs_guestok": "true",
                    "cifs_vfsobjects": "streams_xattr"}
        DELETE_ALL("/sharing/cifs/", payload3)
        DELETE("/storage/volume/1/datasets/%s/" % DATASET)

    # Set auxilary parameters allow mount_smbfs to work with Active Directory
    def test_01_Creating_SMB_dataset(self):
        assert POST("/storage/volume/tank/datasets/", {"name": DATASET}) == 201

    def test_02_Enabling_Active_Directory(self):
        payload = {"ad_bindpw": ADPASSWORD,
                   "ad_bindname": ADUSERNAME,
                   "ad_domainname": BRIDGEDOMAIN,
                   "ad_netbiosname_a": BRIDGEHOST,
                   "ad_idmap_backend": "rid",
                   "ad_enable": "true"}
        assert PUT("/directoryservice/activedirectory/1/", payload) == 200

    def test_03_Checking_Active_Directory(self):
        assert GET_OUTPUT("/directoryservice/activedirectory/",
                          "ad_enable") is True

    def test_04_Checking_to_see_if_SMB_service_is_enabled(self):
        assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "RUNNING"

    def test_05_Enabling_SMB_service(self):
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
                   "cifs_guestok": True,
                   "cifs_vfsobjects": "streams_xattr"}
        assert POST("/sharing/cifs/", payload) == 201

    # def test_09_Checking_permissions_on_SMB_NAME(self):
        # vol_name = return_output('dirname "%s"' % SMB_PATH)
        # cmd = 'ls -la "%s" | ' % vol_name
        # cmd += 'awk \'$4 == "%s" && $9 == "%s"\'' % (VOL_GROUP, DATASET)
        # assert SSH_TEST(cmd) is True

    # Mount share on OSX system and create a test file
    def test_10_Create_mount_point_for_SMB_on_OSX_system(self):
        assert OSX_TEST('mkdir -p "%s"' % MOUNTPOINT) is True

    def test_11_Mount_SMB_share_on_OSX_system(self):
        cmd = 'mount -t smbfs "smb://%s:' % ADUSERNAME
        cmd += '%s@%s/%s" "%s"' % (ADPASSWORD, ip, SMB_NAME, MOUNTPOINT)
        assert OSX_TEST(cmd) is True

    # def test_12_Checking_permissions_on_MOUNTPOINT_(self):
    #     device_name = return_output('dirname "%s"' % MOUNTPOINT)
    #     cmd = 'ls -la "%s" | ' % device_name
    #     cmd += 'awk \'$4 == "%s" && $9 == "%s"\'' % (VOL_GROUP, DATASET)
    #     assert OSX_TEST(cmd) is True

    def test_13_Create_file_on_SMB_share_via_OSX_to_test_permissions(self):
        assert OSX_TEST('touch "%s/testfile.txt"' % MOUNTPOINT) is True

    # Move test file to a new location on the SMB share
    def test_14_Moving_SMB_test_file_into_a_new_directory(self):
        cmd = 'mkdir -p "%s/tmp" && ' % MOUNTPOINT
        cmd += 'mv "%s/testfile.txt" ' % MOUNTPOINT
        cmd += '"%s/tmp/testfile.txt"' % MOUNTPOINT
        assert OSX_TEST(cmd) is True

    # Delete test file and test directory from SMB share
    def test_15_Deleting_test_file_and_directory_from_SMB_share(self):
        cmd = 'rm -f "%s/tmp/testfile.txt" && ' % MOUNTPOINT
        cmd += 'rmdir "%s/tmp"' % MOUNTPOINT
        assert OSX_TEST(cmd) is True

    def test_16_Verifying_that_test_file_directory_successfully_removed(self):
        cmd = 'find -- "%s/" -prune -type d -empty | grep -q .' % MOUNTPOINT
        assert OSX_TEST(cmd) is True

    # Clean up mounted SMB share
    def test_17_Unmount_SMB_share(self):
        assert OSX_TEST('umount -f "%s"' % MOUNTPOINT) is True

    # Disable Active Directory Directory
    def test_18_Disabling_Active_Directory(self):
        payload = {"ad_bindpw": ADPASSWORD,
                   "ad_bindname": ADUSERNAME,
                   "ad_domainname": BRIDGEDOMAIN,
                   "ad_netbiosname_a": BRIDGEHOST,
                   "ad_idmap_backend": "rid",
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

if __name__ == "__main__":
    unittest.main(verbosity=2)
