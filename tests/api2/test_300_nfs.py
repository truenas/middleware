#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
import contextlib
import urllib.parse
from pytest_dependency import depends
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, SSH_TEST, DELETE, wait_on_job
from functions import make_ws_request
from auto_config import pool_name, ha, hostname
from auto_config import dev_test, password, user
from protocols import SSH_NFS
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')

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


def parse_server_config(fname="nfs-kernel-server"):
    results = SSH_TEST(f"cat /etc/default/{fname}", user, password, ip)
    assert results['result'] is True, results['error']
    conf = results['output'].splitlines()
    rv = {}

    for line in conf:
        if not line or line.startswith("#"):
            continue

        k, v = line.split("=", 1)
        rv.update({k: v})

    return rv


@contextlib.contextmanager
def nfs_dataset(name, options=None, acl=None, mode=None):
    assert "/" not in name

    dataset = f"{pool_name}/{name}"

    result = POST("/pool/dataset/", {"name": dataset, **(options or {})})
    assert result.status_code == 200, result.text

    if acl is None:
        result = POST("/filesystem/setperm/", {'path': f"/mnt/{dataset}", "mode": mode or "777"})
    else:
        result = POST("/filesystem/setacl/", {'path': f"/mnt/{dataset}", "dacl": acl})

    assert result.status_code == 200, result.text
    job_status = wait_on_job(result.json(), 180)
    assert job_status["state"] == "SUCCESS", str(job_status["results"])

    try:
        yield dataset
    finally:
        # dataset may be busy
        sleep(10)
        result = DELETE(f"/pool/dataset/id/{urllib.parse.quote(dataset, '')}/")
        assert result.status_code == 200, result.text


@contextlib.contextmanager
def nfs_share(path, options=None):
    results = POST("/sharing/nfs/", {
        "path": path,
        **(options or {}),
    })
    assert results.status_code == 200, results.text
    id = results.json()["id"]

    try:
        yield id
    finally:
        result = DELETE(f"/sharing/nfs/id/{id}/")
        assert result.status_code == 200, result.text


# Enable NFS server
def test_01_creating_the_nfs_server():
    paylaod = {"servers": 10,
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
               "path": NFS_PATH,
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
    """
    This test verifies that service can be updated in general,
    and also that the 'servers' key can be altered.
    Latter goal is achieved by reading the nfs config file
    and verifying that the value here was set correctly.
    """
    depends(request, ["pool_04"], scope="session")
    results = PUT("/nfs/", {"servers": "50"})
    assert results.status_code == 200, results.text

    s = parse_server_config()
    assert int(s["RPCNFSDCOUNT"][1:-1]) == 50, str(s)
    assert "--num-threads 50" in s["RPCMOUNTDOPTS"], str(s)


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
        192.168.0.70(sec=sys,rw,subtree_check)\
        @fakenetgroup(sec=sys,rw,subtree_check)
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")
    hosts_to_test = ["192.168.0.69", "192.168.0.70", "@fakenetgroup"]

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
    exports_hosts = [x['host'] for x in parsed[0]['opts']]
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

    """
    setting maproot_user and maproot_group to root should
    cause us to append "not_root_squash" to options.
    """
    payload = {
        'maproot_user': 'root',
        'maproot_group': 'root'
    }
    results = PUT(f"/sharing/nfs/id/{nfsid}/", payload)
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    params = parsed[0]['opts'][0]['parameters']
    assert 'no_root_squash' in params, str(parsed)
    assert not any(filter(lambda x: x.startswith('anon'), params)), str(parsed)

    """
    Second share should have normal (no maproot) params.
    """
    second_share = f'/mnt/{pool_name}/second_share'
    with nfs_dataset('second_share'):
        with nfs_share(second_share):
            parsed = parse_exports()
            assert len(parsed) == 2, str(parsed)

            params = parsed[0]['opts'][0]['parameters']
            assert 'no_root_squash' in params, str(parsed)

            params = parsed[1]['opts'][0]['parameters']
            assert 'no_root_squash' not in params, str(parsed)
            assert not any(filter(lambda x: x.startswith('anon'), params)), str(parsed)

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
    depends(request, ["pool_04"], scope="session")
    tmp_path = f'{NFS_PATH}/sub1'
    results = POST('/filesystem/mkdir', tmp_path)
    assert results.status_code == 200, results.text

    with nfs_share(tmp_path, {'hosts': ['127.0.0.1']}):
        parsed = parse_exports()
        assert len(parsed) == 2, str(parsed)

        assert parsed[0]['path'] == NFS_PATH, str(parsed)
        assert 'no_subtree_check' in parsed[0]['opts'][0]['parameters'], str(parsed)

        assert parsed[1]['path'] == tmp_path, str(parsed)
        assert 'subtree_check' in parsed[1]['opts'][0]['parameters'], str(parsed)


def test_37_check_nfs_allow_nonroot_behavior(request):
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
    depends(request, ["pool_04"], scope="session")
    results = GET("/nfs")
    assert results.status_code == 200, results.text
    assert results.json()['allow_nonroot'] is False, results.text

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


def test_38_check_nfs_service_v4_parameter(request):
    """
    This test verifies that toggling the `v4` option generates expected changes
    in nfs kernel server config.
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")

    results = GET("/nfs")
    assert results.status_code == 200, results.text
    assert results.json()['v4'] is True, results.text

    s = parse_server_config()
    assert "-N 4" not in s["RPCNFSDOPTS"], str(s)

    results = PUT("/nfs/", {"v4": False})
    assert results.status_code == 200, results.text

    s = parse_server_config()
    assert "-N 4" in s["RPCNFSDOPTS"], str(s)

    results = PUT("/nfs/", {"v4": True})
    assert results.status_code == 200, results.text

    s = parse_server_config()
    assert "-N 4" not in s["RPCNFSDOPTS"], str(s)


def test_39_check_nfs_service_udp_parameter(request):
    """
    This test verifies that toggling the `udp` option generates expected changes
    in nfs kernel server config.
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")

    results = GET("/nfs")
    assert results.status_code == 200, results.text
    assert results.json()['udp'] is False, results.text

    s = parse_server_config()
    assert "--no-udp" in s["RPCNFSDOPTS"], str(s)

    results = PUT("/nfs/", {"udp": True})
    assert results.status_code == 200, results.text

    s = parse_server_config()
    assert "--no-udp" not in s["RPCNFSDOPTS"], str(s)

    results = PUT("/nfs/", {"udp": False})
    assert results.status_code == 200, results.text

    s = parse_server_config()
    assert "--no-udp" in s["RPCNFSDOPTS"], str(s)


def test_40_check_nfs_service_ports(request):
    """
    Port options are spread between two files:
    /etc/default/nfs-kernel-server
    /etc/default/nfs-common

    This test verifies that the custom ports we specified in
    earlier NFS tests are set in the relevant files.
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")

    results = GET("/nfs")
    assert results.status_code == 200, results.text
    config = results.json()

    s = parse_server_config()
    assert f'--port {config["mountd_port"]}' in s['RPCMOUNTDOPTS'], str(s)

    s = parse_server_config("nfs-common")
    assert f'--port {config["rpcstatd_port"]}' in s['STATDOPTS'], str(s)
    assert f'--nlm-port {config["rpclockd_port"]}' in s['STATDOPTS'], str(s)


def test_41_check_nfs_client_status(request):
    """
    This test checks the function of API endpoints to list NFSv3 and
    NFSv4 clients by performing loopback mounts on the remote TrueNAS
    server and then checking client counts. Due to inherent imprecision
    of counts over NFSv3 protcol (specifically with regard to decrementing
    sessions) we only verify that count is non-zero for NFSv3.
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")

    with SSH_NFS(ip, NFS_PATH, vers=3, user=user, password=password, ip=ip):
        results = GET('/nfs/get_nfs3_clients/', payload={
            'query-filters': [],
            'query-options': {'count': True}
        })
        assert results.status_code == 200, results.text
        assert results.json() != 0, results.text

    with SSH_NFS(ip, NFS_PATH, vers=4, user=user, password=password, ip=ip):
        results = GET('/nfs/get_nfs4_clients/', payload={
            'query-filters': [],
            'query-options': {'count': True}
        })
        assert results.status_code == 200, results.text
        assert results.json() == 1, results.text


def test_42_check_nfsv4_acl_support(request):
    """
    This test validates reading and setting NFSv4 ACLs through an NFSv4
    mount in the following manner:
    1) Create and locally mount an NFSv4 share on the TrueNAS server
    2) Iterate through all possible permissions options and set them
       via an NFS client, read back through NFS client, and read resulting
       ACL through the filesystem API.
    3) Repeate same process for each of the supported flags.
    """
    depends(request, ["pool_04", "ssh_password"], scope="session")
    acl_nfs_path = f'/mnt/{pool_name}/test_nfs4_acl'
    test_perms = {
        "READ_DATA": True,
        "WRITE_DATA": True,
        "EXECUTE": True,
        "APPEND_DATA": True,
        "DELETE_CHILD": True,
        "DELETE": True,
        "READ_ATTRIBUTES": True,
        "WRITE_ATTRIBUTES": True,
        "READ_NAMED_ATTRS": True,
        "WRITE_NAMED_ATTRS": True,
        "READ_ACL": True,
        "WRITE_ACL": True,
        "WRITE_OWNER": True,
        "SYNCHRONIZE": True
    }
    test_flags = {
        "FILE_INHERIT": True,
        "DIRECTORY_INHERIT": True,
        "INHERIT_ONLY": False,
        "NO_PROPAGATE_INHERIT": False,
        "INHERITED": False
    }
    theacl = [
        {"tag": "owner@", "id": -1, "perms": test_perms, "flags": test_flags, "type": "ALLOW"},
        {"tag": "group@", "id": -1, "perms": test_perms, "flags": test_flags, "type": "ALLOW"},
        {"tag": "everyone@", "id": -1, "perms": test_perms, "flags": test_flags, "type": "ALLOW"},
        {"tag": "USER", "id": 65534, "perms": test_perms, "flags": test_flags, "type": "ALLOW"},
        {"tag": "GROUP", "id": 666, "perms": test_perms.copy(), "flags": test_flags.copy(), "type": "ALLOW"},
    ]
    with nfs_dataset("test_nfs4_acl", {"acltype": "NFSV4", "aclmode": "PASSTHROUGH"}, theacl):
        with nfs_share(acl_nfs_path):
            with SSH_NFS(ip, acl_nfs_path, vers=4, user=user, password=password, ip=ip) as n:
                nfsacl = n.getacl(".")
                for idx, ace in enumerate(nfsacl):
                    assert ace == theacl[idx], str(ace)

                for perm in test_perms.keys():
                    if perm == 'SYNCHRONIZE':
                        # break in SYNCHRONIZE because Linux tool limitation
                        break

                    theacl[4]['perms'][perm] = False
                    n.setacl(".", theacl)
                    nfsacl = n.getacl(".")
                    for idx, ace in enumerate(nfsacl):
                        assert ace == theacl[idx], str(ace)

                    payload = {
                        'path': acl_nfs_path,
                        'simplified': False
                    }
                    result = POST('/filesystem/getacl/', payload)
                    assert result.status_code == 200, result.text

                    for idx, ace in enumerate(result.json()['acl']):
                        assert ace == nfsacl[idx], str(ace)

                for flag in ("INHERIT_ONLY", "NO_PROPAGATE_INHERIT"):
                    theacl[4]['flags'][flag] = True
                    n.setacl(".", theacl)
                    nfsacl = n.getacl(".")
                    for idx, ace in enumerate(nfsacl):
                        assert ace == theacl[idx], str(ace)

                    payload = {
                        'path': acl_nfs_path,
                        'simplified': False
                    }
                    result = POST('/filesystem/getacl/', payload)
                    assert result.status_code == 200, result.text

                    for idx, ace in enumerate(result.json()['acl']):
                        assert ace == nfsacl[idx], str(ace)


def test_44_check_nfs_xattr_support(request):
    """
    Perform basic validation of NFSv4.2 xattr support.
    Mount path via NFS 4.2, create a file and dir,
    and write + read xattr on each.
    """
    depends(request, ["pool_04"], scope="session")
    xattr_nfs_path = f'/mnt/{pool_name}/test_nfs4_xattr'
    with nfs_dataset("test_nfs4_xattr"):
        with nfs_share(xattr_nfs_path):
            with SSH_NFS(ip, xattr_nfs_path, vers=4.2, user=user, password=password, ip=ip) as n:
                n.create("testfile")
                n.setxattr("testfile", "user.testxattr", "the_contents")
                xattr_val = n.getxattr("testfile", "user.testxattr")
                assert xattr_val == "the_contents" 

                n.create("testdir", True)
                n.setxattr("testdir", "user.testxattr2", "the_contents2")
                xattr_val = n.getxattr("testdir", "user.testxattr2")
                assert xattr_val == "the_contents2" 


def test_45_check_setting_runtime_debug(request):
    """
    This validates that the private NFS debugging API works correctly.
    """
    depends(request, ["pool_04"], scope="session")
    disabled = {"NFS": ["NONE"], "NFSD": ["NONE"], "NLM": ["NONE"], "RPC": ["NONE"]}

    get_payload = {'msg': 'method', 'method': 'nfs.get_debug', 'params': []}
    set_payload = {'msg': 'method', 'method': 'nfs.set_debug', 'params': [["NFSD"], ["ALL"]]}
    res = make_ws_request(ip, get_payload)
    assert res['result'] == disabled, res
    
    make_ws_request(ip, set_payload)
    res = make_ws_request(ip, get_payload)
    assert res['result']['NFSD'] == ["ALL"], res

    set_payload['params'][1] = ["NONE"]
    make_ws_request(ip, set_payload)
    res = make_ws_request(ip, get_payload)
    assert res['result'] == disabled, res


def test_50_stoping_nfs_service(request):
    depends(request, ["pool_04"], scope="session")
    payload = {"service": "nfs"}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_51_checking_to_see_if_nfs_service_is_stop(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/service?service=nfs")
    assert results.json()[0]["state"] == "STOPPED", results.text


def test_52_check_adjusting_threadpool_mode(request):
    """
    Verify that NFS thread pool configuration can be adjusted
    through private API endpoints.

    This request will fail if NFS server is still running.
    """
    supported_modes = ["AUTO", "PERCPU", "PERNODE", "GLOBAL"]
    payload = {'msg': 'method', 'method': None, 'params': []}

    for m in supported_modes:
        payload.update({'method': 'nfs.set_threadpool_mode', 'params': [m]})
        make_ws_request(ip, payload)

        payload.update({'method': 'nfs.get_threadpool_mode', 'params': []})
        res = make_ws_request(ip, payload)
        assert res['result'] == m, res


def test_53_set_bind_ip():
    res = GET("/nfs/bindip_choices")
    assert res.status_code == 200, res.text
    assert ip in res.json(), res.text

    res = PUT("/nfs/", {"bindip": [ip]})
    assert res.status_code == 200, res.text


def test_54_disable_nfs_service_at_boot(request):
    depends(request, ["pool_04"], scope="session")
    results = PUT("/service/id/nfs/", {"enable": False})
    assert results.status_code == 200, results.text


def test_55_checking_nfs_disable_at_boot(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/service?service=nfs")
    assert results.json()[0]['enable'] is False, results.text


def test_56_destroying_smb_dataset(request):
    depends(request, ["pool_04"], scope="session")
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
