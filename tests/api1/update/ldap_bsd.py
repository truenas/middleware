#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET_OUTPUT, SSH_TEST
from auto_config import ip
from config import *

if "BRIDGEHOST" in locals():
    MOUNTPOINT = "/tmp/ldap-bsd" + BRIDGEHOST

DATASET = "ldap-bsd"
SMB_NAME = "TestShare"
SMB_PATH = "/mnt/tank/" + DATASET
LDAP_USER = 'ldapuser'
VOL_GROUP = "qa"
Reason = "BRIDGEHOST, LDAPBASEDN and LDAPHOSTNAME are missing "
Reason += "in ixautomation.conf"
BSDReason = 'BSD host configuration is missing in ixautomation.conf'

ldap_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                        "LDAPBASEDN" in locals(),
                                        "LDAPHOSTNAME" in locals(),
                                        "MOUNTPOINT" in locals()
                                        ]) is False, reason=Reason)

bsd_host_cfg = pytest.mark.skipif(all(["BSD_HOST" in locals(),
                                       "BSD_USERNAME" in locals(),
                                       "BSD_PASSWORD" in locals()
                                       ]) is False, reason=BSDReason)


# Enable LDAP
@ldap_test_cfg
def test_01_Enabling_LDAPd():
    payload = {"ldap_basedn": LDAPBASEDN2,
               "ldap_binddn": LDAPBINDDN2,
               "ldap_bindpw": LDAPBINDPASSWORD2,
               "ldap_netbiosname_a": BRIDGEHOST,
               "ldap_hostname": LDAPHOSTNAME2,
               "ldap_has_samba_schema": True,
               "ldap_enable": True}
    assert PUT("/directoryservice/ldap/1/", payload) == 200


# Check LDAP
@ldap_test_cfg
def test_03_Checking_LDAPd():
    assert GET_OUTPUT("/directoryservice/ldap/", "ldap_enable") is True


def test_03_Enabling_SMB_service():
    payload = {"cifs_srv_description": "Test FreeNAS Server",
               "cifs_srv_guest": "nobody",
               "cifs_hostname_lookup": False,
               "cifs_srv_aio_enable": False}
    assert PUT("/services/cifs/", payload) == 200


# Now start the service
def test_04_Starting_SMB_service():
    assert PUT("/services/services/cifs/", {"srv_enable": True}) == 200


@ldap_test_cfg
def test_05_Checking_to_see_if_SMB_service_is_enabled():
    assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "RUNNING"


def test_06_Changing_permissions_on_SMB_PATH():
    payload = {"mp_path": SMB_PATH,
               "mp_acl": "unix",
               "mp_mode": "777",
               "mp_user": "root",
               "mp_group": "wheel",
               "mp_recursive": True}
    assert PUT("/storage/permission/", payload) == 201


def test_07_Creating_a_SMB_share_on_SMB_PATH():
    payload = {"cfs_comment": "My Test SMB Share",
               "cifs_path": SMB_PATH,
               "cifs_name": SMB_NAME,
               "cifs_guestok": True,
               "cifs_vfsobjects": "streams_xattr"}
    assert POST("/sharing/cifs/", payload) == 201


# Now check if we can mount SMB / create / rename / copy / delete / umount
@bsd_host_cfg
@ldap_test_cfg
def test_08_Creating_SMB_mountpoint():
    assert SSH_TEST('mkdir -p "%s" && sync' % MOUNTPOINT,
                    BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


# The LDAPUSER user must exist in LDAP with this password
@bsd_host_cfg
@ldap_test_cfg
def test_09_Store_LDAP_credentials_in_file_for_mount_smbfs():
    cmd = 'echo "[TESTNAS:LDAPUSER]" > ~/.nsmbrc && '
    cmd += 'echo "password=12345678" >> ~/.nsmbrc'
    assert SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ldap_test_cfg
def test_10_Mounting_SMB():
    cmd = 'mount_smbfs -N -I %s -W LDAP02 ' % ip
    cmd += '"//%s@testnas/%s" "%s"' % (LDAP_USER, SMB_NAME, MOUNTPOINT)
    assert SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ldap_test_cfg
def test_11_Creating_SMB_file():
    assert SSH_TEST('touch "%s/testfile"' % MOUNTPOINT,
                    BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ldap_test_cfg
def test_12_Moving_SMB_file():
    cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
    assert SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ldap_test_cfg
def test_13_Copying_SMB_file():
    cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
    assert SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ldap_test_cfg
def test_14_Deleting_SMB_file_1_2():
    assert SSH_TEST('rm "%s/testfile"' % MOUNTPOINT,
                    BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ldap_test_cfg
def test_15_Deleting_SMB_file_2_2():
    assert SSH_TEST('rm "%s/testfile2"' % MOUNTPOINT,
                    BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ldap_test_cfg
def test_16_Unmounting_SMB():
    assert SSH_TEST('umount -f "%s"' % MOUNTPOINT,
                    BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ldap_test_cfg
def test_17_Verifying_SMB_share_was_unmounted():
    assert SSH_TEST('mount | grep -qv "%s"' % MOUNTPOINT,
                    BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ldap_test_cfg
def test_18_Removing_SMB_mountpoint():
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    assert SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True
