#!/usr/bin/env python3.6
# Author: Eric Turgeon.
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


def test_01_creating_smb_dataset():
    assert POST("/storage/volume/tank/datasets/", {"name": DATASET}) == 201


@ad_test_cfg
def test_02_enabling_active_directory():
    payload = {"ad_bindpw": ADPASSWORD,
               "ad_bindname": ADUSERNAME,
               "ad_domainname": BRIDGEDOMAIN,
               "ad_netbiosname_a": BRIDGEHOST,
               "ad_idmap_backend": "rid",
               "ad_enable": True}
    assert PUT("/directoryservice/activedirectory/1/", payload) == 200


@ad_test_cfg
def test_03_checking_active_directory():
    assert GET_OUTPUT("/directoryservice/activedirectory/",
                      "ad_enable") is True


# @ad_test_cfg
# def test_04_checking_to_see_if_smb_service_is_enabled():
#     assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "RUNNING"


def test_04_enabling_smb_service():
    payload = {"cifs_srv_description": "Test FreeNAS Server",
               "cifs_srv_guest": "nobody",
               "cifs_hostname_lookup": False,
               "cifs_srv_aio_enable": False}
    assert PUT("/services/cifs/", payload) == 200


# Now start the service
def test_05_Starting_SMB_service():
    assert PUT("/services/services/cifs/", {"srv_enable": True}) == 200


@ad_test_cfg
def test_06_checking_to_see_if_smb_service_is_enabled():
    assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "RUNNING"


def test_07_Changing_permissions_on_SMB_PATH():
    payload = {"mp_path": SMB_PATH,
               "mp_acl": "unix",
               "mp_mode": "777",
               "mp_user": "root",
               "mp_group": "wheel",
               "mp_recursive": True}
    assert PUT("/storage/permission/", payload) == 201


def test_08_Creating_a_SMB_share_on_SMB_PATH():
    payload = {"cfs_comment": "My Test SMB Share",
               "cifs_path": SMB_PATH,
               "cifs_name": SMB_NAME,
               "cifs_guestok": "true",
               "cifs_vfsobjects": "streams_xattr"}
    assert POST("/sharing/cifs/", payload) == 201


@bsd_host_cfg
@ad_test_cfg
def test_09_creating_smb_mountpoint():
    assert SSH_TEST('mkdir -p "%s" && sync' % MOUNTPOINT,
                    BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


# The ADUSER user must exist in AD with this password
@bsd_host_cfg
@ad_test_cfg
def test_10_Store_AD_credentials_in_a_file_for_mount_smbfs():
    cmd = 'echo "[TESTNAS:ADUSER]" > ~/.nsmbrc && '
    cmd += 'echo "password=12345678" >> ~/.nsmbrc'
    assert SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ad_test_cfg
def test_11_Mounting_SMB():
    cmd = 'mount_smbfs -N -I %s -W AD01 ' % ip
    cmd += '"//aduser@testnas/%s" "%s"' % (SMB_NAME, MOUNTPOINT)
    assert SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ad_test_cfg
def test_13_Creating_SMB_file():
    assert SSH_TEST('touch "%s/testfile"' % MOUNTPOINT,
                    BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ad_test_cfg
def test_14_Moving_SMB_file():
    cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
    assert SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ad_test_cfg
def test_15_Copying_SMB_file():
    cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
    assert SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ad_test_cfg
def test_16_Deleting_SMB_file_1_2():
    assert SSH_TEST('rm "%s/testfile"' % MOUNTPOINT,
                    BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ad_test_cfg
def test_17_Deleting_SMB_file_2_2():
    assert SSH_TEST('rm "%s/testfile2"' % MOUNTPOINT,
                    BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ad_test_cfg
def test_18_Unmounting_SMB():
    assert SSH_TEST('umount "%s"' % MOUNTPOINT,
                    BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True
