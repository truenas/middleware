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
from auto_config import pool_name, ha, hostname
from auto_config import dev_test, password, user
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

if ha and "virtual_ip" in os.environ:
    ip = os.environ["virtual_ip"]
else:
    from auto_config import ip
MOUNTPOINT = f"/tmp/nfs-{hostname}"
dataset = f"{pool_name}/nfs"
dataset_url = dataset.replace('/', '%2F')
NFS_PATH = "/mnt/" + dataset

Reason = 'BSD host configuration is missing in ixautomation.conf'
try:
    from config import BSD_HOST, BSD_USERNAME, BSD_PASSWORD
    bsd_host_cfg = pytest.mark.skipif(False, reason=Reason)
except ImportError:
    bsd_host_cfg = pytest.mark.skipif(True, reason=Reason)


def parse_exports():
    results = SSH_TEST("cat /etc/exports", user, password, ip)
    assert results['result'] is True, results['error']
    exp = results['output'].splitlines()
    rv = []
    for idx, line in enumerate(exp):
        if not line or line.startswith('\t'):
            continue

        entry = {"path": line.strip()[1:-2], "opts": []}

        i = idx + 1
        while i < len(exp):
            if not exp[i].startswith('\t'):
                break

            e = exp[i].strip()
            host, params = e.split('(', 1)
            entry['opts'].append({
                "host": host,
                "parameters": params[:-1].split(",")
            })
            i += 1

        rv.append(entry)

    return rv

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
        "group": 'root'
    }
    results = POST(f"/pool/dataset/id/{dataset_url}/permission/", payload)
    assert results.status_code == 200, results.text
    global job_id
    job_id = results.json()


def test_04_verify_the_job_id_is_successfull(request):
    depends(request, ["pool_04"], scope="session")
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_05_creating_a_nfs_share_on_nfs_PATH(request):
    depends(request, ["pool_04"], scope="session")
    global nfsid
    paylaod = {"comment": "My Test Share",
               "paths": [NFS_PATH],
               "security": ["SYS"]}
    results = POST("/sharing/nfs/", paylaod)
    assert results.status_code == 200, results.text
    nfsid = results.json()['id']


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


@bsd_host_cfg
def test_11_creating_nfs_mountpoint(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    results = SSH_TEST(f'mkdir -p "{MOUNTPOINT}"',
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@pytest.mark.timeout(10)
def test_12_mounting_nfs(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = f'mount_nfs {ip}:{NFS_PATH} {MOUNTPOINT}'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_13_creating_nfs_file(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = 'touch "%s/testfile"' % MOUNTPOINT
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_14_moving_nfs_file(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_15_copying_nfs_file(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_16_deleting_nfs_file(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    results = SSH_TEST('rm "%s/testfile2"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_17_unmounting_nfs(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    results = SSH_TEST('umount "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_18_removing_nfs_mountpoint(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


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
    depends(request, ["pool_04", "ssh_password"], scope="session")
    results = SSH_TEST('mkdir -p "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@pytest.mark.timeout(10)
def test_23_mounting_nfs(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = 'mount_nfs %s:%s %s' % (ip, NFS_PATH, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_24_creating_nfs_file(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = 'touch "%s/testfile"' % MOUNTPOINT
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_25_moving_nfs_file(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_26_copying_nfs_file(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_27_deleting_nfs_file(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    results = SSH_TEST('rm "%s/testfile2"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_28_unmounting_nfs(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    results = SSH_TEST('umount "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_29_removing_nfs_mountpoint(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


def test_30_add_second_nfs_path(request):
    """
    Verify that adding a second path generates second exports entry
    Sample:

    "/mnt/dozer/NFSV4/foo"\
    	*(sec=sys,rw,subtree_check)
    "/mnt/dozer/NFSV4/foobar"\
    	*(sec=sys,rw,subtree_check)
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")

    paths = [f'{NFS_PATH}/sub1', f'{NFS_PATH}/sub2']
    results = SSH_TEST(f"mkdir {' '.join(paths)}", user, password, ip)
    assert results['result'] is True, results['error']

    results = PUT(f"/sharing/nfs/id/{nfsid}/", {'paths': paths})
    assert results.status_code == 200, results.text

    exports_paths = [x['path'] for x in parse_exports()]
    diff = set(exports_paths) ^ set(paths)
    assert len(diff) == 0, str(diff)

    # Restore to single entry
    results = PUT(f"/sharing/nfs/id/{nfsid}/", {'paths': [NFS_PATH]})
    assert results.status_code == 200, results.text

    exports_paths = [x['path'] for x in parse_exports()]
    assert len(exports_paths) == 1, exports_paths


def test_31_check_nfs_share_network(request):
    """
    Verify that adding a network generates an appropriate line in exports
    file for same path. Sample:

    "/mnt/dozer/nfs"\
    	192.168.0.0/24(sec=sys,rw,subtree_check)\
    	192.168.1.0/24(sec=sys,rw,subtree_check)
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")
    networks_to_test = ["192.168.0.0/24", "192.168.1.0/24"]

    results = PUT(f"/sharing/nfs/id/{nfsid}/", {'networks': networks_to_test})
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)

    exports_networks = [x['host'] for x in parsed[0]['opts']]
    diff = set(networks_to_test) ^ set(exports_networks)
    assert len(diff) == 0, f'diff: {diff}, exports: {parsed}'

    # Reset to default
    results = PUT(f"/sharing/nfs/id/{nfsid}/", {'networks': []})
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    exports_networks = [x['host'] for x in parsed[0]['opts']]
    assert len(exports_networks) == 1, str(parsed)
    assert exports_networks[0] == '*', str(parsed)


def test_32_check_nfs_share_hosts(request):
    """
    Verify that adding a network generates an appropriate line in exports
    file for same path. Sample:

    "/mnt/dozer/nfs"\
    	192.168.0.69(sec=sys,rw,subtree_check)\
    	192.168.0.70(sec=sys,rw,subtree_check)
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")
    hosts_to_test = ["192.168.0.69", "192.168.0.70"]

    results = PUT(f"/sharing/nfs/id/{nfsid}/", {'hosts': hosts_to_test})
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)

    exports_hosts = [x['host'] for x in parsed[0]['opts']]
    diff = set(hosts_to_test) ^ set(exports_hosts)
    assert len(diff) == 0, f'diff: {diff}, exports: {parsed}'

    # Reset to default
    results = PUT(f"/sharing/nfs/id/{nfsid}/", {'hosts': []})
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    exports_hosts= [x['host'] for x in parsed[0]['opts']]
    assert len(exports_hosts) == 1, str(parsed)


def test_33_check_nfs_share_ro(request):
    """
    Verify that toggling `ro` will cause appropriate change in
    exports file.
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    assert "rw" in parsed[0]['opts'][0]['parameters'], str(parsed)

    results = PUT(f"/sharing/nfs/id/{nfsid}/", {'ro': True})
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    assert "rw" not in parsed[0]['opts'][0]['parameters'], str(parsed)

    results = PUT(f"/sharing/nfs/id/{nfsid}/", {'ro': False})
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    assert "rw" in parsed[0]['opts'][0]['parameters'], str(parsed)


def test_34_check_nfs_share_maproot(request):
    """
    root squash is always enabled, and so maproot accomplished through
    anonuid and anongid

    Sample:
    "/mnt/dozer/NFSV4"\
    	*(sec=sys,rw,anonuid=65534,anongid=65534,subtree_check)
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")
    payload = {
        'maproot_user': 'nobody',
        'maproot_group': 'nogroup'
    }
    results = PUT(f"/sharing/nfs/id/{nfsid}/", payload)
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)

    params = parsed[0]['opts'][0]['parameters']
    assert 'anonuid=65534' in params, str(parsed)
    assert 'anongid=65534' in params, str(parsed)

    payload = {
        'maproot_user': '',
        'maproot_group': ''
    }
    results = PUT(f"/sharing/nfs/id/{nfsid}/", payload)
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    params = parsed[0]['opts'][0]['parameters']

    assert not any(filter(lambda x: x.startswith('anon'), params)), str(parsed)


def test_35_check_nfs_share_mapall(request):
    """
    mapall is accomplished through anonuid and anongid and
    setting 'all_squash'.

    Sample:
    "/mnt/dozer/NFSV4"\
    	*(sec=sys,rw,all_squash,anonuid=65534,anongid=65534,subtree_check)
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")
    payload = {
        'mapall_user': 'nobody',
        'mapall_group': 'nogroup'
    }
    results = PUT(f"/sharing/nfs/id/{nfsid}/", payload)
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)

    params = parsed[0]['opts'][0]['parameters']
    assert 'anonuid=65534' in params, str(parsed)
    assert 'anongid=65534' in params, str(parsed)
    assert 'all_squash' in params, str(parsed)

    payload = {
        'mapall_user': '',
        'mapall_group': ''
    }
    results = PUT(f"/sharing/nfs/id/{nfsid}/", payload)
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    params = parsed[0]['opts'][0]['parameters']

    assert not any(filter(lambda x: x.startswith('anon'), params)), str(parsed)
    assert 'all_squash' not in params, str(parsed)


def test_36_check_nfsdir_subtree_behavior(request):
    """
    If dataset mountpoint is exported rather than simple dir,
    we disable subtree checking as an optimization. This check
    makes sure we're doing this as expected:

    Sample:
    "/mnt/dozer/NFSV4"\
    	*(sec=sys,rw,no_subtree_check)
    "/mnt/dozer/NFSV4/foobar"\
    	*(sec=sys,rw,subtree_check)
    """
    paths = [NFS_PATH, f'{NFS_PATH}/sub1']

    results = PUT(f"/sharing/nfs/id/{nfsid}/", {'paths': paths})
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 2, str(parsed)

    assert parsed[0]['path'] == paths[0], str(parsed)
    assert 'no_subtree_check' in parsed[0]['opts'][0]['parameters'], str(parsed)

    assert parsed[1]['path'] == paths[1], str(parsed)
    assert 'subtree_check' in parsed[1]['opts'][0]['parameters'], str(parsed)

    # Restore to single entry
    results = PUT(f"/sharing/nfs/id/{nfsid}/", {'paths': [NFS_PATH]})
    assert results.status_code == 200, results.text

    exports_paths = [x['path'] for x in parse_exports()]
    assert len(exports_paths) == 1, exports_paths


 test_37_check_nfs_allow_nonroot_behavior(request):
    """
    If global configuration option "allow_nonroot" is set, then
    we append "insecure" to each exports line.
    Since this is a global option, it triggers an nfsd restart
    even though it's not technically required.

    Sample:
    "/mnt/dozer/NFSV4"\
        *(sec=sys,rw,insecure,no_subtree_check)
    """

    # Verify that NFS server configuration is as expected
    results = GET("/nfs")
    assert results.status_code == 200, results.text
    assert results.json()['allow_nonroot'] == False, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    assert 'insecure' not in parsed[0]['opts'][0]['parameters'], str(parsed)

    results = PUT("/nfs/", {"allow_nonroot": True})
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    assert 'insecure' in parsed[0]['opts'][0]['parameters'], str(parsed)

    results = PUT("/nfs/", {"allow_nonroot": False})
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    assert 'insecure' not in parsed[0]['opts'][0]['parameters'], str(parsed)


def test_51_stoping_nfs_service(request):
    depends(request, ["pool_04"], scope="session")
    payload = {"service": "nfs"}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_52_checking_to_see_if_nfs_service_is_stop(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/service?service=nfs")
    assert results.json()[0]["state"] == "STOPPED", results.text


def test_53_disable_nfs_service_at_boot(request):
    depends(request, ["pool_04"], scope="session")
    results = PUT("/service/id/nfs/", {"enable": False})
    assert results.status_code == 200, results.text


def test_54_checking_nfs_disable_at_boot(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/service?service=nfs")
    assert results.json()[0]['enable'] is False, results.text


def test_55_destroying_smb_dataset(request):
    depends(request, ["pool_04"], scope="session")
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
