#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os
import xmlrunner
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET_OUTPUT, DELETE_ALL, DELETE, BSD_TEST
from functions import return_output
from auto_config import ip, results_xml

try:
    from config import BRIDGEHOST, BRIDGEDOMAIN, ADPASSWORD, ADUSERNAME
    from config import LDAPBASEDN, LDAPHOSTNAME
except ImportError:
    RunTest = False
else:
    MOUNTPOINT = "/tmp/ldap-bsd" + BRIDGEHOST
    RunTest = True
TestName = "create ldap bsd"

DATASET = "ldap-bsd"
SMB_NAME = "TestShare"
SMB_PATH = "/mnt/tank/" + DATASET
VOL_GROUP = "qa"


class create_ldap_bsd_test(unittest.TestCase):

    # Clean up any leftover items from previous failed AD LDAP or SMB runs
    @classmethod
    def setUpClass(inst):
        payload = {"ad_bindpw": ADPASSWORD,
                   "ad_bjindname": ADUSERNAME,
                   "ad_domainname": BRIDGEDOMAIN,
                   "ad_netbiosname_a": BRIDGEHOST,
                   "ad_idmap_backend": "rid",
                   "ad_enable": "false"}
        PUT("/directoryservice/activedirectory/1/", payload)
        payload1 = {"ldap_basedn": LDAPBASEDN,
                    "ldap_anonbind": "true",
                    "ldap_netbiosname_a": BRIDGEHOST,
                    "ldap_hostname": LDAPHOSTNAME,
                    "ldap_has_samba_schema": "true",
                    "ldap_enable": "false"}
        PUT("/directoryservice/ldap/1/", payload1)
        payload2 = {"cfs_comment": "My Test SMB Share",
                    "cifs_path": SMB_PATH,
                    "cifs_name": SMB_NAME,
                    "cifs_guestok": "true",
                    "cifs_vfsobjects": "streams_xattr"}
        DELETE_ALL("/sharing/cifs/", payload2)
        DELETE("/storage/volume/1/datasets/%s/" % DATASET)
        cmd = 'umount -f "%s" &>/dev/null; ' % MOUNTPOINT
        cmd += 'rmdir "%s" &>/dev/null' % MOUNTPOINT
        BSD_TEST(cmd)

    # Set auxilary parameters to allow mount_smbfs to work with ldap
    def test_01_Setting_auxilary_parameters_for_mount_smbfs(self):
        options = "lanman auth = yes\nntlm auth = yes \nraw NTLMv2 auth = yes"
        payload = {"cifs_srv_smb_options": options}
        assert PUT("/services/cifs/", payload) == 200

    def test_02_Creating_SMB_dataset(self):
        assert POST("/storage/volume/tank/datasets/", {"name": DATASET}) == 201

    # Enable LDAP
    def test_03_Enabling_LDAP_with_anonymous_bind(self):
        payload = {"ldap_basedn": LDAPBASEDN,
                   "ldap_anonbind": "true",
                   "ldap_netbiosname_a": BRIDGEHOST,
                   "ldap_hostname": LDAPHOSTNAME,
                   "ldap_has_samba_schema": "true",
                   "ldap_enable": "true"}
        assert PUT("/directoryservice/ldap/1/", payload) == 200

    # Check LDAP
    def test_04_Checking_LDAP(self):
        assert GET_OUTPUT("/directoryservice/ldap/", "ldap_enable") is True

    def test_05_Enabling_SMB_service(self):
        payload = {"cifs_srv_description": "Test FreeNAS Server",
                   "cifs_srv_guest": "nobody",
                   "cifs_hostname_lookup": False,
                   "cifs_srv_aio_enable": False}
        assert PUT("/services/cifs/", payload) == 200

    # Now start the service
    def test_06_Starting_SMB_service(self):
        assert PUT("/services/services/cifs/", {"srv_enable": True}) == 200

    def test_07_Checking_to_see_if_SMB_service_is_enabled(self):
        GET_OUTPUT("/services/services/cifs/", "srv_state")

    def test_08_Changing_permissions_on_SMB_PATH(self):
        payload = {"mp_path": SMB_PATH,
                   "mp_acl": "unix",
                   "mp_mode": "777",
                   "mp_user": "root",
                   "mp_group": "wheel",
                   "mp_recursive": True}
        assert PUT("/storage/permission/", payload) == 201

    def test_09_Creating_a_SMB_share_on_SMB_PATH(self):
        payload = {"cfs_comment": "My Test SMB Share",
                   "cifs_path": SMB_PATH,
                   "cifs_name": SMB_NAME,
                   "cifs_guestok": True,
                   "cifs_vfsobjects": "streams_xattr"}
        assert POST("/sharing/cifs/", payload) == 201

    def test_10_Checking_to_see_if_SMB_service_is_enabled(self):
        assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "RUNNING"

    # BSD test to be done when when BSD_TEST is functional
    def test_11_Creating_SMB_mountpoint(self):
        assert BSD_TEST('mkdir -p "%s" && sync' % MOUNTPOINT) is True

    # The LDAPUSER user must exist in LDAP with this password
    def test_12_Store_LDAP_credentials_for_mount_smbfs(self):
        cmd = 'echo "[TESTNAS:LDAPUSER]" > ~/.nsmbrc && '
        cmd += 'echo "password=12345678" >> ~/.nsmbrc'
        assert BSD_TEST(cmd) is True

    def test_13_Mounting_SMB(self):
        cmd = 'mount_smbfs -N -I %s -W LDAP01 ' % ip
        cmd += '//ldapuser@testnas/%s "%s"' % (SMB_NAME, MOUNTPOINT)
        assert BSD_TEST(cmd) is True

    # def test_14_Checking_permissions_on_MOUNTPOINT(self):
    #    device_name = return_output('dirname "%s"' % MOUNTPOINT)
    #    cmd = 'ls -la "%s" | ' % device_name
    #    cmd += 'awk \'$4 == "%s" && $9 == "%s"\'' % (VOL_GROUP, DATASET)
    #    assert BSD_TEST(cmd) is True

    def test_15_Creating_SMB_file(self):
        assert BSD_TEST('touch "%s/testfile"' % MOUNTPOINT) is True

    def test_16_Moving_SMB_file(self):
        cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
        assert BSD_TEST(cmd) is True

    def test_17_Copying_SMB_file(self):
        cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
        assert BSD_TEST(cmd) is True

    def test_18_Deleting_SMB_file_1_2(self):
        assert BSD_TEST('rm "%s/testfile"' % MOUNTPOINT) is True

    def test_19_Deleting_SMB_file_2_2(self):
        assert BSD_TEST('rm "%s/testfile2"' % MOUNTPOINT) is True

    def test_20_Unmounting_SMB(self):
        assert BSD_TEST('umount -f "%s"' % MOUNTPOINT) is True

    def test_21_Verifying_SMB_share_was_unmounted(self):
        assert BSD_TEST('mount | grep -qv "%s"' % MOUNTPOINT) is True

    def test_22_Removing_SMB_mountpoint(self):
        cmd = 'test -d "%s" && ' % MOUNTPOINT
        cmd += 'rmdir "%s" || exit 0' % MOUNTPOINT
        assert BSD_TEST(cmd) is True

    def test_23_Removing_SMB_share_on_SMB_PATH(self):
        payload = {"cfs_comment": "My Test SMB Share",
                   "cifs_path": SMB_PATH,
                   "cifs_name": SMB_NAME,
                   "cifs_guestok": "true",
                   "cifs_vfsobjects": "streams_xattr"}
        DELETE_ALL("/sharing/cifs/", payload) == 204

    # Disable LDAP
    def test_24_Disabling_LDAP_with_anonymous_bind(self):
        payload = {"ldap_basedn": LDAPBASEDN,
                   "ldap_anonbind": True,
                   "ldap_netbiosname_a": "'${BRIDGEHOST}'",
                   "ldap_hostname": "'${LDAPHOSTNAME}'",
                   "ldap_has_samba_schema": True,
                   "ldap_enable": False}
        assert PUT("/directoryservice/ldap/1/", payload) == 200

    # Now stop the SMB service
    def test_25_Stopping_SMB_service(self):
        PUT("/services/services/cifs/", {"srv_enable": False}) == 200

    # Check LDAP
    def test_26_Verify_LDAP_is_disabled(self):
        GET_OUTPUT("/directoryservice/ldap/", "ldap_enable") is False

    def test_27_Verify_SMB_service_is_disabled(self):
        GET_OUTPUT("/services/services/cifs/", "srv_state") == "STOPPED"

    # Check destroying a SMB dataset
    def test_28_Destroying_SMB_dataset(self):
        DELETE("/storage/volume/1/datasets/%s/" % DATASET) == 204


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(create_ldap_bsd_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
