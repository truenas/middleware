#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, SSH_TEST, DELETE_ALL, DELETE
from auto_config import ip
from config import *

if "BRIDGEHOST" in locals():
    MOUNTPOINT = "/tmp/ldap-bsd" + BRIDGEHOST

DATASET = "ldap-bsd"
SMB_NAME = "TestShare"
SMB_PATH = "/mnt/tank/" + DATASET
VOL_GROUP = "qa"
Reason = "BRIDGEHOST, LDAPBASEDN and LDAPHOSTNAME are missing "
Reason += "in ixautomation.conf"
BSDReason = 'BSD host configuration is missing in ixautomation.conf'

ldap_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                        "LDAPBASEDN" in locals(),
                                        "LDAPBINDDN" in locals(),
                                        "LDAPHOSTNAME" in locals(),
                                        "LDAPBINDPASSWORD" in locals(),
                                        "MOUNTPOINT" in locals()
                                        ]) is False, reason=Reason)

up_ldap_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                           "LDAPBASEDN2" in locals(),
                                           "LDAPBINDDN2" in locals(),
                                           "LDAPHOSTNAME2" in locals(),
                                           "LDAPBINDPASSWORD2" in locals(),
                                           "MOUNTPOINT" in locals()
                                           ]) is False, reason=Reason)

bsd_host_cfg = pytest.mark.skipif(all(["BSD_HOST" in locals(),
                                       "BSD_USERNAME" in locals(),
                                       "BSD_PASSWORD" in locals()
                                       ]) is False, reason=BSDReason)


# Create tests
# Set auxilary parameters to allow mount_smbfs to work with ldap
def test_01_Setting_auxilary_parameters_for_mount_smbfs():
    options = "lanman auth = yes\nntlm auth = yes \nraw NTLMv2 auth = yes"
    payload = {"cifs_srv_smb_options": options}
    results = PUT("/services/cifs/", payload)
    assert results.status_code == 200, results.text


def test_02_Creating_SMB_dataset():
    results = POST("/storage/volume/tank/datasets/", {"name": DATASET})
    assert results.status_code == 201, results.text


@ldap_test_cfg
def test_03_Enabling_LDAPd():
    payload = {"ldap_basedn": LDAPBASEDN,
               "ldap_binddn": LDAPBINDDN,
               "ldap_bindpw": LDAPBINDPASSWORD,
               "ldap_netbiosname_a": BRIDGEHOST,
               "ldap_hostname": LDAPHOSTNAME,
               "ldap_has_samba_schema": True,
               "ldap_enable": True}
    results = PUT("/directoryservice/ldap/1/", payload)
    assert results.status_code == 200, results.text


# Check LDAP
@ldap_test_cfg
def test_04_Checking_LDAP():
    results = GET("/directoryservice/ldap/")
    assert results.json()["ldap_enable"] is True, results.text


@ldap_test_cfg
def test_05_Enabling_SMB_service():
    payload = {"cifs_srv_description": "Test FreeNAS Server",
               "cifs_srv_guest": "nobody",
               "cifs_hostname_lookup": False,
               "cifs_srv_aio_enable": False}
    results = PUT("/services/cifs/", payload)
    assert results.status_code == 200, results.text


# Now start the service
def test_06_Starting_SMB_service():
    results = PUT("/services/services/cifs/", {"srv_enable": True})
    assert results.status_code == 200, results.text


@ldap_test_cfg
def test_07_Checking_to_see_if_SMB_service_is_enabled():
    results = GET("/services/services/cifs/")
    assert results.json()["srv_state"] == "RUNNING", results.text


def test_08_Changing_permissions_on_SMB_PATH():
    payload = {"mp_path": SMB_PATH,
               "mp_acl": "unix",
               "mp_mode": "777",
               "mp_user": "root",
               "mp_group": "wheel",
               "mp_recursive": True}
    results = PUT("/storage/permission/", payload)
    assert results.status_code == 201, results.text


def test_09_Creating_a_SMB_share_on_SMB_PATH():
    payload = {"cfs_comment": "My Test SMB Share",
               "cifs_path": SMB_PATH,
               "cifs_name": SMB_NAME,
               "cifs_guestok": True,
               "cifs_vfsobjects": "streams_xattr"}
    results = POST("/sharing/cifs/", payload)
    assert results.status_code == 201, results.text


# BSD test to be done when when SSH_TEST is functional
@bsd_host_cfg
@ldap_test_cfg
def test_10_Creating_SMB_mountpoint():
    results = SSH_TEST('mkdir -p "%s" && sync' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


# The LDAPUSER user must exist in LDAP with this password
@bsd_host_cfg
@ldap_test_cfg
def test_11_Store_LDAP_credentials_for_mount_smbfs():
    cmd = 'echo "[TESTNAS:LDAPUSER]" > ~/.nsmbrc && '
    cmd += 'echo "password=12345678" >> ~/.nsmbrc'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@ldap_test_cfg
def test_12_Mounting_SMB():
    cmd = 'mount_smbfs -N -I %s -W LDAP01 ' % ip
    cmd += '//ldapuser@testnas/%s "%s"' % (SMB_NAME, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@ldap_test_cfg
def test_14_Creating_SMB_file():
    results = SSH_TEST('touch "%s/testfile"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@ldap_test_cfg
def test_15_Moving_SMB_file():
    cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@ldap_test_cfg
def test_16_Copying_SMB_file():
    cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@ldap_test_cfg
def test_17_Deleting_SMB_file_1_2():
    results = SSH_TEST('rm "%s/testfile"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@ldap_test_cfg
def test_18_Deleting_SMB_file_2_2():
    results = SSH_TEST('rm "%s/testfile2"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@ldap_test_cfg
def test_19_Unmounting_SMB():
    results = SSH_TEST('umount -f "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@ldap_test_cfg
def test_20_Verifying_SMB_share_was_unmounted():
    results = SSH_TEST('mount | grep -qv "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


# Update tests
# Enable LDAP
@up_ldap_test_cfg
def test_21_Enabling_LDAPd():
    payload = {"ldap_basedn": LDAPBASEDN2,
               "ldap_binddn": LDAPBINDDN2,
               "ldap_bindpw": LDAPBINDPASSWORD2,
               "ldap_netbiosname_a": BRIDGEHOST,
               "ldap_hostname": LDAPHOSTNAME2,
               "ldap_has_samba_schema": True,
               "ldap_enable": True}
    results = PUT("/directoryservice/ldap/1/", payload)
    assert results.status_code == 200, results.text


# Check LDAP
@up_ldap_test_cfg
def test_22_Checking_LDAPd():
    results = GET("/directoryservice/ldap/")
    assert results.json()["ldap_enable"] is True, results.text


@bsd_host_cfg
@up_ldap_test_cfg
def test_23_Mounting_SMB():
    cmd = 'mount_smbfs -N -I %s -W LDAP02 ' % ip
    cmd += '"//ldapuser@testnas/%s" "%s"' % (SMB_NAME, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@up_ldap_test_cfg
def test_24_Creating_SMB_file():
    results = SSH_TEST('touch "%s/testfile"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@up_ldap_test_cfg
def test_25_Moving_SMB_file():
    cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@up_ldap_test_cfg
def test_26_Copying_SMB_file():
    cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@up_ldap_test_cfg
def test_27_Deleting_SMB_file_1_2():
    results = SSH_TEST('rm "%s/testfile"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@up_ldap_test_cfg
def test_28_Deleting_SMB_file_2_2():
    results = SSH_TEST('rm "%s/testfile2"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@up_ldap_test_cfg
def test_29_Unmounting_SMB():
    results = SSH_TEST('umount -f "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@up_ldap_test_cfg
def test_30_Verifying_SMB_share_was_unmounted():
    results = SSH_TEST('mount | grep -qv "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@up_ldap_test_cfg
def test_31_Removing_SMB_mountpoint():
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


# Delete tests
@bsd_host_cfg
@up_ldap_test_cfg
def test_32_Removing_SMB_mountpoint():
    cmd = 'test -d "%s" && ' % MOUNTPOINT
    cmd += 'rmdir "%s" || exit 0' % MOUNTPOINT
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@up_ldap_test_cfg
def test_33_Removing_SMB_share_on_SMB_PATH():
    payload = {"cfs_comment": "My Test SMB Share",
               "cifs_path": SMB_PATH,
               "cifs_name": SMB_NAME,
               "cifs_guestok": "true",
               "cifs_vfsobjects": "streams_xattr"}
    results = DELETE_ALL("/sharing/cifs/", payload)
    assert results.status_code == 204, results.stat


# Disable LDAP
@up_ldap_test_cfg
def test_34_Disabling_LDAPd():
    payload = {"ldap_basedn": LDAPBASEDN2,
               "ldap_binddn": LDAPBINDDN2,
               "ldap_bindpw": LDAPBINDPASSWORD2,
               "ldap_netbiosname_a": BRIDGEHOST,
               "ldap_hostname": LDAPHOSTNAME2,
               "ldap_has_samba_schema": True,
               "ldap_enable": False}
    results = PUT("/directoryservice/ldap/1/", payload)
    assert results.status_code == 200, results.text


# Now stop the SMB service
def test_35_Stopping_SMB_service():
    results = PUT("/services/services/cifs/", {"srv_enable": False})
    assert results.status_code == 200, results.text


# Check LDAP
@ldap_test_cfg
def test_36_Verify_LDAP_is_disabled():
    results = GET("/directoryservice/ldap/")
    assert results.json()["ldap_enable"] is False, results.text


@ldap_test_cfg
def test_37_Verify_SMB_service_is_disabled():
    results = GET("/services/services/cifs/")
    assert results.json()["srv_state"] == "STOPPED", results.text


# Check destroying a SMB dataset
def test_38_Destroying_SMB_dataset():
    results = DELETE("/storage/volume/1/datasets/%s/" % DATASET)
    assert results.status_code == 204, results.text
