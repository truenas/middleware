#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, SSH_TEST
from auto_config import ip
from config import *

if "BRIDGEHOST" in locals():
    MOUNTPOINT = "/tmp/nfs" + BRIDGEHOST

NFS_PATH = "/mnt/tank/share"
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
def test_01_Creating_the_NFS_server():
    paylaod = {"nfs_srv_bindip": ip,
               "nfs_srv_mountd_port": 618,
               "nfs_srv_allow_nonroot": False,
               "nfs_srv_servers": 10,
               "nfs_srv_udp": False,
               "nfs_srv_rpcstatd_port": 871,
               "nfs_srv_rpclockd_port": 32803,
               "nfs_srv_v4": False,
               "nfs_srv_v4_krb": False,
               "id": 1}
    results = PUT("/services/nfs/", paylaod)
    assert results.status_code == 200, results.text


# Check creating a NFS share
def test_02_Creating_a_NFS_share_on_NFS_PATH():
    paylaod = {"nfs_comment": "My Test Share",
               "nfs_paths": [NFS_PATH],
               "nfs_security": "sys"}
    results = POST("/sharing/nfs/", paylaod)
    assert results.status_code == 201, results.text


# Now start the service
def test_03_Starting_NFS_service():
    results = PUT("/services/services/nfs/", {"srv_enable": True})
    assert results.status_code == 200, results.text


def test_04_Checking_to_see_if_NFS_service_is_enabled():
    results = GET("/services/services/nfs/")
    assert results.json()["srv_state"] == "RUNNING", results.text


@mount_test_cfg
@bsd_host_cfg
# Now check if we can mount NFS / create / rename / copy / delete / umount
def test_05_Creating_NFS_mountpoint():
    results = SSH_TEST('mkdir -p "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_06_Mounting_NFS():
    cmd = 'mount_nfs %s:%s %s' % (ip, NFS_PATH, MOUNTPOINT)
    # command below does not make sence
    # "umount '${MOUNTPOINT}' ; rmdir '${MOUNTPOINT}'" "60"
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_07_Creating_NFS_file():
    cmd = 'touch "%s/testfile"' % MOUNTPOINT
    # 'umount "${MOUNTPOINT}"; rmdir "${MOUNTPOINT}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_08_Moving_NFS_file():
    cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_09_Copying_NFS_file():
    cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_10_Deleting_NFS_file():
    results = SSH_TEST('rm "%s/testfile2"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_11_Unmounting_NFS():
    results = SSH_TEST('umount "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_12_Removing_NFS_mountpoint():
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


# Update test
def test_13_Updating_the_NFS_service():
    results = PUT("/services/nfs/", {"nfs_srv_servers": "50"})
    assert results.status_code == 200, results.text


def test_14_Checking_to_see_if_NFS_service_is_enabled():
    results = GET("/services/services/nfs/")
    assert results.json()["srv_state"] == "RUNNING", results.text
