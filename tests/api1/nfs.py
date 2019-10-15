#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE, SSH_TEST
from auto_config import ip, pool_name, user, password
from config import *

if "BRIDGEHOST" in locals():
    MOUNTPOINT = "/tmp/nfs" + BRIDGEHOST

NFS_PATH = f"/mnt/{pool_name}/share"
Reason = "BRIDGEHOST is missing in ixautomation.conf"
BSDReason = 'BSD host configuration is missing in ixautomation.conf'

mount_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                         "MOUNTPOINT" in locals()
                                         ]) is False, reason=Reason)

bsd_host_cfg = pytest.mark.skipif(all(["BSD_HOST" in locals(),
                                       "BSD_USERNAME" in locals(),
                                       "BSD_PASSWORD" in locals()
                                       ]) is False, reason=BSDReason)

nfs_key_list = [
    "nfs_srv_bindip",
    "nfs_srv_mountd_port",
    "nfs_srv_allow_nonroot",
    "nfs_srv_servers",
    "nfs_srv_udp",
    "nfs_srv_rpcstatd_port",
    "nfs_srv_rpclockd_port",
    "nfs_srv_v4",
    "nfs_srv_v4_krb",
    "id"
]


# Enable NFS server
def test_01_Creating_the_NFS_server():
    global results, payload
    payload = {
        "nfs_srv_bindip": [ip],
        "nfs_srv_mountd_port": 618,
        "nfs_srv_allow_nonroot": False,
        "nfs_srv_servers": 10,
        "nfs_srv_udp": False,
        "nfs_srv_rpcstatd_port": 871,
        "nfs_srv_rpclockd_port": 32803,
        "nfs_srv_v4": True,
        "nfs_srv_v4_krb": False,
        "id": 1
    }
    results = PUT("/services/nfs/", payload)
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('key', nfs_key_list)
def test_02_verify_put_services_nfs_result_for(key):
    assert results.json()[key] == payload[key], results.text


def test_03_get_services_nfs():
    global results
    results = GET("/services/nfs/")
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('key', nfs_key_list)
def test_04_verify_get_services_nfs_result_for(key):
    assert results.json()[key] == payload[key], results.text


# Check creating a NFS share
def test_05_Creating_a_NFS_share_on_NFS_PATH():
    global nfs_share_id, payload, results
    payload = {
        "nfs_comment": "My Test Share",
        "nfs_paths": [NFS_PATH],
        "nfs_security": ["sys"]
    }
    results = POST("/sharing/nfs/", payload)
    assert results.status_code == 201, results.text
    nfs_share_id = results.json()['id']


@pytest.mark.parametrize('key', ['nfs_comment', 'nfs_paths', 'nfs_security'])
def test_06_verify_post_sharing_nfs_result_for(key):
    assert results.json()[key] == payload[key], results.text


def test_07_get_sharing_nfs_by_id():
    results = GET(f"/sharing/nfs/{nfs_share_id}")
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('key', ['nfs_comment', 'nfs_paths', 'nfs_security'])
def test_08_verify_get_sharing_nfs_result_for(key):
    assert results.json()[key] == payload[key], results.text


# Now start the service
def test_09_Starting_NFS_service():
    results = PUT("/services/services/nfs/", {"srv_enable": True})
    assert results.status_code == 200, results.text
    sleep(1)


def test_10_Checking_to_see_if_NFS_service_is_enabled():
    results = GET("/services/services/nfs/")
    assert results.json()["srv_state"] == "RUNNING", results.text


def test_11_checking_if_sysctl_vfs_nfsd_server_max_nfsvers_is_4():
    cmd = 'sysctl -n vfs.nfsd.server_max_nfsvers'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == '4', results['output']


@mount_test_cfg
@bsd_host_cfg
# Now check if we can mount NFS / create / rename / copy / delete / umount
def test_12_Creating_NFS_mountpoint():
    results = SSH_TEST('mkdir -p "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_13_Mounting_NFS():
    cmd = 'mount_nfs %s:%s %s' % (ip, NFS_PATH, MOUNTPOINT)
    # command below does not make sence
    # "umount '${MOUNTPOINT}' ; rmdir '${MOUNTPOINT}'" "60"
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_14_Creating_NFS_file():
    cmd = 'touch "%s/testfile"' % MOUNTPOINT
    # 'umount "${MOUNTPOINT}"; rmdir "${MOUNTPOINT}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_15_Moving_NFS_file():
    cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_16_Copying_NFS_file():
    cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_17_Deleting_NFS_file():
    results = SSH_TEST('rm "%s/testfile2"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_18_Unmounting_NFS():
    results = SSH_TEST('umount "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_19_Removing_NFS_mountpoint():
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


# Update test
def test_20_Updating_the_NFS_service():
    results = PUT("/services/nfs/", {"nfs_srv_servers": "50"})
    assert results.status_code == 200, results.text


def test_21_Checking_to_see_if_NFS_service_is_enabled():
    results = GET("/services/services/nfs/")
    assert results.json()["srv_state"] == "RUNNING", results.text


# Now stop the service
def test_22_Stop_NFS_service():
    results = PUT("/services/services/nfs/", {"srv_enable": False})
    assert results.status_code == 200, results.text
    sleep(1)


def test_23_Checking_to_see_if_NFS_service_is_stopped():
    results = GET("/services/services/nfs/")
    assert results.status_code == 200, results.text
    assert results.json()["srv_state"] == "STOPPED", results.text


def test_24_delete_sharing_nfs():
    results = DELETE(f"/sharing/nfs/{nfs_share_id}")
    assert results.status_code == 204, results.text
