#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, SSH_TEST, DELETE
from auto_config import ip
from config import *

if "BRIDGEHOST" in locals():
    MOUNTPOINT = "/tmp/nfs" + BRIDGEHOST

DATASET = "tank/nfs"
urlDataset = "tank%2Fnfs"
NFS_PATH = "/mnt/" + DATASET
Reason = "BRIDGEHOST is missing in ixautomation.conf"
BSDReason = 'BSD host configuration is missing in ixautomation.conf'

mount_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                         "MOUNTPOINT" in locals()
                                         ]) is False, reason=Reason)

bsd_host_cfg = pytest.mark.skipif(all(["BSD_HOST" in locals(),
                                       "BSD_USERNAME" in locals(),
                                       "BSD_PASSWORD" in locals()
                                       ]) is False, reason=BSDReason)


# Enable NFS server
def test_01_creating_the_nfs_server():
    paylaod = {"servers": 10,
               "bindip": [ip],
               "mountd_port": 618,
               "allow_nonroot": False,
               "udp": False,
               "rpcstatd_port": 871,
               "rpclockd_port": 32803,
               "v4": True}
    results = PUT("/nfs/", paylaod)
    assert results.status_code == 200, results.text


def test_02_creating_dataset_nfs():
    payload = {"name": DATASET}
    results = POST("/pool/dataset/", payload)
    assert results.status_code == 200, results.text


def test_03_changing_permissions_on_nfs():
    payload = {"mp_path": NFS_PATH,
               "mp_acl": "unix",
               "mp_mode": "777",
               "mp_user": "root",
               "mp_group": "wheel"}
    results = PUT("/storage/permission/", payload, api="1")
    assert results.status_code == 201, results.text


# creating a NFS share
def test_04_creating_a_nfs_share_on_nfs_PATH():
    paylaod = {"comment": "My Test Share",
               "paths": [NFS_PATH],
               "security": ["SYS"]}
    results = POST("/sharing/nfs/", paylaod)
    assert results.status_code == 200, results.text


# Now start the service
def test_05_starting_nfs_service_at_boot():
    results = PUT("/service/id/nfs/", {"enable": True})
    assert results.status_code == 200, results.text


def test_06_checking_to_see_if_nfs_service_is_enabled_at_boot():
    results = GET("/service?service=nfs")
    assert results.json()[0]["enable"] is True, results.text


def test_07_starting_nfs_service():
    payload = {"service": "nfs", "service-control": {"onetime": True}}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text


def test_08_checking_to_see_if_nfs_service_is_running():
    results = GET("/service?service=nfs")
    assert results.json()[0]["state"] == "RUNNING", results.text


@mount_test_cfg
@bsd_host_cfg
# Now check if we can mount NFS / create / rename / copy / delete / umount
def test_09_creating_nfs_mountpoint():
    results = SSH_TEST(f'mkdir -p "{MOUNTPOINT}"',
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_10_mounting_nfs():
    cmd = f'mount_nfs {ip}:{NFS_PATH} {MOUNTPOINT}'
    # command below does not make sence
    # "umount '${MOUNTPOINT}' ; rmdir '${MOUNTPOINT}'" "60"
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_11_creating_nfs_file():
    cmd = 'touch "%s/testfile"' % MOUNTPOINT
    # 'umount "${MOUNTPOINT}"; rmdir "${MOUNTPOINT}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_12_moving_nfs_file():
    cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_13_copying_nfs_file():
    cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_14_deleting_nfs_file():
    results = SSH_TEST('rm "%s/testfile2"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_15_unmounting_nfs():
    results = SSH_TEST('umount "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_16_removing_nfs_mountpoint():
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


# Update test
def test_17_updating_the_nfs_service():
    results = PUT("/nfs/", {"servers": "50"})
    assert results.status_code == 200, results.text


def test_18_update_nfs_share():
    nfsid = GET('/sharing/nfs?comment=My Test Share').json()[0]['id']
    payload = {"security": []}
    results = PUT(f"/sharing/nfs/id/{nfsid}/", payload)
    assert results.status_code == 200, results.text


def test_19_checking_to_see_if_nfs_service_is_enabled():
    results = GET("/service?service=nfs")
    assert results.json()[0]["state"] == "RUNNING", results.text


@mount_test_cfg
@bsd_host_cfg
# Now check if we can mount NFS / create / rename / copy / delete / umount
def test_20_creating_nfs_mountpoint():
    results = SSH_TEST('mkdir -p "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_21_mounting_nfs():
    cmd = 'mount_nfs %s:%s %s' % (ip, NFS_PATH, MOUNTPOINT)
    # command below does not make sence
    # "umount '${MOUNTPOINT}' ; rmdir '${MOUNTPOINT}'" "60"
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_22_creating_nfs_file():
    cmd = 'touch "%s/testfile"' % MOUNTPOINT
    # 'umount "${MOUNTPOINT}"; rmdir "${MOUNTPOINT}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_23_moving_nfs_file():
    cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_24_copying_nfs_file():
    cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_25_deleting_nfs_file():
    results = SSH_TEST('rm "%s/testfile2"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_26_unmounting_nfs():
    results = SSH_TEST('umount "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_27_removing_nfs_mountpoint():
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


def test_28_delete_nfs_share():
    nfsid = GET('/sharing/nfs?comment=My Test Share').json()[0]['id']
    results = DELETE(f"/sharing/nfs/id/{nfsid}")
    assert results.status_code == 200, results.text


def test_29_stoping_nfs_service():
    payload = {"service": "nfs", "service-control": {"onetime": True}}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text


def test_30_checking_to_see_if_nfs_service_is_stop():
    results = GET("/service?service=nfs")
    assert results.json()[0]["state"] == "STOPPED", results.text


# Test disable AFP
def test_31_disable_nfs_service_at_boot():
    results = PUT("/service/id/nfs/", {"enable": False})
    assert results.status_code == 200, results.text


def test_32_checking_nfs_disable_at_boot():
    results = GET("/service?service=nfs")
    assert results.json()[0]['enable'] is False, results.text


# Check destroying a SMB dataset
def test_33_destroying_smb_dataset():
    results = DELETE(f"/pool/dataset/id/{urlDataset}/")
    assert results.status_code == 200, results.text
