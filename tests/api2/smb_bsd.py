#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE, SSH_TEST
from auto_config import ip
from config import *
if "BRIDGEHOST" in locals():
    MOUNTPOINT = "/tmp/smb-bsd" + BRIDGEHOST
DATASET = "tank/smb-bsd"
SMB_NAME = "TestSMB"
SMB_PATH = "/mnt/" + DATASET
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


# Create tests
def test_01_Setting_auxilary_parameters_for_mount_smbfs():
    toload = "lanman auth = yes\nntlm auth = yes \nraw NTLMv2 auth = yes"
    payload = {"smb_options": toload}
    results = PUT("/smb", payload)
    assert results.status_code == 200, results.text


def test_02_Creating_SMB_dataset():
    results = POST("/pool/dataset", {"name": DATASET})
    assert results.status_code == 200, results.text


def test_03_Changing_permissions_on_SMB_PATH():
    payload = {"mp_path": SMB_PATH,
               "mp_acl": "unix",
               "mp_mode": "777",
               "mp_user": "root",
               "mp_group": "wheel"}
    results = PUT("/storage/permission/", payload, api="1")
    assert results.status_code == 201, results.text


def test_03_starting_cifs_service_at_boot():
    results = PUT("/service/id/cifs", {"enable": True})
    assert results.status_code == 200, results.text


def test_06_checking_to_see_if_clif_service_is_enabled_at_boot():
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] == True, results.text


def test_07_starting_cifs_service():
    payload = {"service": "cifs", "service-control": {"onetime": True}}
    results = POST("/service/start", payload)
    assert results.status_code == 200, results.text


def test_08_checking_to_see_if_nfs_service_is_running():
    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "RUNNING", results.text


def test_06_Creating_a_cifs_share_on_SMB_PATH():
    payload = {"comment": "My Test SMB Share",
               "path": SMB_PATH,
               "name": SMB_NAME,
               "guestok": True,
               "vfsobjects": ["streams_xattr"]}
    results = POST("/sharing/cifs", payload)
    assert results.status_code == 201, results.text


# Now check if we can mount SMB / create / rename / copy / delete / umount
@mount_test_cfg
@bsd_host_cfg
def test_07_Creating_SMB_mountpoint():
    cmd = f'mkdir -p "{MOUNTPOINT}" && sync'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_08_Mounting_SMB():
    cmd = f'mount_smbfs -N -I {ip} ' \
          f'"//guest@testnas/{SMB_NAME}" "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_09_Creating_SMB_file():
    cmd = f"touch {MOUNTPOINT}/testfile"
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_10_Moving_SMB_file():
    cmd = f'mv {MOUNTPOINT}/testfile {MOUNTPOINT}/testfile2'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_11_Copying_SMB_file():
    cmd = f'cp {MOUNTPOINT}/testfile2 {MOUNTPOINT}/testfile'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_12_Deleting_SMB_file_1_2():
    cmd = f'rm "{MOUNTPOINT}/testfile"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_13_Deleting_SMB_file_2_2():
    cmd = f'rm "{MOUNTPOINT}/testfile2"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_14_Unmounting_SMB():
    cmd = f'umount -f {MOUNTPOINT}'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


# Update tests
@mount_test_cfg
@bsd_host_cfg
def test_15_Mounting_SMB():
    cmd = f'mount_smbfs -N -I {ip} ' \
          f'"//guest@testnas/{SMB_NAME}" "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_16_Creating_SMB_file():
    cmd = f'touch {MOUNTPOINT}/testfile'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_17_Moving_SMB_file():
    cmd = f'mv {MOUNTPOINT}/testfile {MOUNTPOINT}/testfile2'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_18_Copying_SMB_file():
    cmd = f'cp {MOUNTPOINT}/testfile2 {MOUNTPOINT}/testfile'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_19_Deleting_SMB_file_1_2():
    cmd = f'rm {MOUNTPOINT}/testfile'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_20_Deleting_SMB_file_2_2():
    cmd = f'rm {MOUNTPOINT}/testfile2'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_21_Unmounting_SMB():
    cmd = f'umount -f {MOUNTPOINT}'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


# Delete tests
@mount_test_cfg
@bsd_host_cfg
def test_22_Removing_SMB_mountpoint():
    cmd = f'test -d "{MOUNTPOINT}" && rmdir "{MOUNTPOINT}" || exit 0'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


def test_23_SMB_share_on_SMB_PATH():
    payload = {"comment": "My Test SMB Share",
               "path": SMB_PATH,
               "name": SMB_NAME,
               "guestok": True,
               "vfsobjects": "streams_xattr"}
    results = DELETE(f"/sharing/cifs/id/{SMB_NAME}", payload)
    assert results.status_code == 204, results.text


# Now stop the service
def test_24_Stopping_SMB_service():
    results = PUT("/service/id/cifs", {"enable": False})
    assert results.status_code == 200, results.text


def test_26_checking_to_see_if_clif_service_is_enabled_at_boot():
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] == False, results.text


def test_25_stoping_clif_service():
    payload = {"service": "clif", "service-control": {"onetime": True}}
    results = POST("/service/stop", payload)
    assert results.status_code == 200, results.text


# Check destroying a SMB dataset
def test_27_Destroying_SMB_dataset():
    results = DELETE(f"/pool/dataset/id/{DATASET}")
    assert results.status_code == 204, results.text
