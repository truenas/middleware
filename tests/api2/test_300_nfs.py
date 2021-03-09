#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
from pytest_dependency import depends
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, SSH_TEST, DELETE, wait_on_job
from auto_config import pool_name, user, password, scale, ha, hostname
from config import *
from auto_config import dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

if ha and "virtual_ip" in os.environ:
    ip = os.environ["virtual_ip"]
else:
    from auto_config import ip


group = 'root' if scale else 'wheel'
MOUNTPOINT = f"/tmp/nfs-{hostname}"
dataset = f"{pool_name}/nfs"
dataset_url = dataset.replace('/', '%2F')
NFS_PATH = "/mnt/" + dataset
Reason = "BRIDGEHOST is missing in ixautomation.conf"
BSDReason = 'BSD host configuration is missing in ixautomation.conf'

bsd_host_cfg = pytest.mark.skipif(all(["BSD_HOST" in locals(),
                                       "BSD_USERNAME" in locals(),
                                       "BSD_PASSWORD" in locals()
                                       ]) is False, reason=BSDReason)


# Enable NFS server
def test_01_creating_the_nfs_server():
    print(ip)
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


def test_02_creating_dataset_nfs(request):
    depends(request, ["pool_04"], scope="session")
    payload = {"name": dataset}
    results = POST("/pool/dataset/", payload)
    assert results.status_code == 200, results.text


def test_03_changing_dataset_permissions_of_nfs_dataset(request):
    depends(request, ["pool_04"], scope="session")
    payload = {
        "acl": [],
        "mode": "777",
        "user": "root",
        "group": group
    }
    results = POST(f"/pool/dataset/id/{dataset_url}/permission/", payload)
    assert results.status_code == 200, results.text
    global job_id
    job_id = results.json()


def test_04_verify_the_job_id_is_successfull(request):
    depends(request, ["pool_04"], scope="session")
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


# creating a NFS share
def test_05_creating_a_nfs_share_on_nfs_PATH(request):
    depends(request, ["pool_04"], scope="session")
    paylaod = {"comment": "My Test Share",
               "paths": [NFS_PATH],
               "security": ["SYS"]}
    results = POST("/sharing/nfs/", paylaod)
    assert results.status_code == 200, results.text


# Now start the service
def test_06_starting_nfs_service_at_boot(request):
    depends(request, ["pool_04"], scope="session")
    results = PUT("/service/id/nfs/", {"enable": True})
    assert results.status_code == 200, results.text


def test_07_checking_to_see_if_nfs_service_is_enabled_at_boot(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/service?service=nfs")
    assert results.json()[0]["enable"] is True, results.text


def test_08_starting_nfs_service(request):
    depends(request, ["pool_04"], scope="session")
    payload = {"service": "nfs"}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_09_checking_to_see_if_nfs_service_is_running(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/service?service=nfs")
    assert results.json()[0]["state"] == "RUNNING", results.text


@pytest.mark.skipif(scale, reason='Skipping for Scale')
def test_10_checking_if_sysctl_vfs_nfsd_server_max_nfsvers_is_4(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = 'sysctl -n vfs.nfsd.server_max_nfsvers'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == '4', results['output']


@bsd_host_cfg
# Now check if we can mount NFS / create / rename / copy / delete / umount
def test_11_creating_nfs_mountpoint(request):
    depends(request, ["pool_04"], scope="session")
    results = SSH_TEST(f'mkdir -p "{MOUNTPOINT}"',
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@pytest.mark.timeout(10)
def test_12_mounting_nfs(request):
    depends(request, ["pool_04"], scope="session")
    cmd = f'mount_nfs {ip}:{NFS_PATH} {MOUNTPOINT}'
    # command below does not make sence
    # "umount '${MOUNTPOINT}' ; rmdir '${MOUNTPOINT}'" "60"
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_13_creating_nfs_file(request):
    depends(request, ["pool_04"], scope="session")
    cmd = 'touch "%s/testfile"' % MOUNTPOINT
    # 'umount "${MOUNTPOINT}"; rmdir "${MOUNTPOINT}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_14_moving_nfs_file(request):
    depends(request, ["pool_04"], scope="session")
    cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_15_copying_nfs_file(request):
    depends(request, ["pool_04"], scope="session")
    cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_16_deleting_nfs_file(request):
    depends(request, ["pool_04"], scope="session")
    results = SSH_TEST('rm "%s/testfile2"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_17_unmounting_nfs(request):
    depends(request, ["pool_04"], scope="session")
    results = SSH_TEST('umount "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_18_removing_nfs_mountpoint(request):
    depends(request, ["pool_04"], scope="session")
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


# Update test
def test_19_updating_the_nfs_service(request):
    depends(request, ["pool_04"], scope="session")
    results = PUT("/nfs/", {"servers": "50"})
    assert results.status_code == 200, results.text


def test_20_update_nfs_share(request):
    depends(request, ["pool_04"], scope="session")
    nfsid = GET('/sharing/nfs?comment=My Test Share').json()[0]['id']
    payload = {"security": []}
    results = PUT(f"/sharing/nfs/id/{nfsid}/", payload)
    assert results.status_code == 200, results.text


def test_21_checking_to_see_if_nfs_service_is_enabled(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/service?service=nfs")
    assert results.json()[0]["state"] == "RUNNING", results.text


@bsd_host_cfg
# Now check if we can mount NFS / create / rename / copy / delete / umount
def test_22_creating_nfs_mountpoint(request):
    depends(request, ["pool_04"], scope="session")
    results = SSH_TEST('mkdir -p "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@pytest.mark.timeout(10)
def test_23_mounting_nfs(request):
    depends(request, ["pool_04"], scope="session")
    cmd = 'mount_nfs %s:%s %s' % (ip, NFS_PATH, MOUNTPOINT)
    # command below does not make sence
    # "umount '${MOUNTPOINT}' ; rmdir '${MOUNTPOINT}'" "60"
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_24_creating_nfs_file(request):
    depends(request, ["pool_04"], scope="session")
    cmd = 'touch "%s/testfile"' % MOUNTPOINT
    # 'umount "${MOUNTPOINT}"; rmdir "${MOUNTPOINT}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_25_moving_nfs_file(request):
    depends(request, ["pool_04"], scope="session")
    cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_26_copying_nfs_file(request):
    depends(request, ["pool_04"], scope="session")
    cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_27_deleting_nfs_file(request):
    depends(request, ["pool_04"], scope="session")
    results = SSH_TEST('rm "%s/testfile2"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_28_unmounting_nfs(request):
    depends(request, ["pool_04"], scope="session")
    results = SSH_TEST('umount "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_29_removing_nfs_mountpoint(request):
    depends(request, ["pool_04"], scope="session")
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


def test_30_delete_nfs_share(request):
    depends(request, ["pool_04"], scope="session")
    nfsid = GET('/sharing/nfs?comment=My Test Share').json()[0]['id']
    results = DELETE(f"/sharing/nfs/id/{nfsid}")
    assert results.status_code == 200, results.text


def test_31_stoping_nfs_service(request):
    depends(request, ["pool_04"], scope="session")
    payload = {"service": "nfs"}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_32_checking_to_see_if_nfs_service_is_stop(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/service?service=nfs")
    assert results.json()[0]["state"] == "STOPPED", results.text


# Test disable AFP
def test_33_disable_nfs_service_at_boot(request):
    depends(request, ["pool_04"], scope="session")
    results = PUT("/service/id/nfs/", {"enable": False})
    assert results.status_code == 200, results.text


def test_34_checking_nfs_disable_at_boot(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/service?service=nfs")
    assert results.json()[0]['enable'] is False, results.text


# Check destroying a SMB dataset
def test_35_destroying_smb_dataset(request):
    depends(request, ["pool_04"], scope="session")
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
