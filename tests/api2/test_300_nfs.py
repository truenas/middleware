import contextlib
import errno
import ipaddress
import os
import urllib.parse
from copy import copy
from time import sleep

import pytest
from pytest_dependency import depends

from middlewared.service_exception import ValidationError, ValidationErrors
from middlewared.test.integration.assets.account import group as create_group
from middlewared.test.integration.assets.account import user as create_user
from middlewared.test.integration.assets.filesystem import directory
from middlewared.test.integration.utils import call, mock, ssh
from middlewared.test.integration.utils.client import truenas_server
from middlewared.test.integration.utils.system import reset_systemd_svcs as reset_svcs

from auto_config import hostname, password, pool_name, user
from functions import DELETE, GET, POST, PUT, SSH_TEST, wait_on_job
from protocols import SSH_NFS, nfs_share

MOUNTPOINT = f"/tmp/nfs-{hostname}"
dataset = f"{pool_name}/nfs"
dataset_url = dataset.replace('/', '%2F')
NFS_PATH = "/mnt/" + dataset

# Supported configuration files
conf_file = {
    "nfs": {
        "pname": "/etc/nfs.conf.d/local.conf",
        "sections": {
            'nfsd': {},
            'exportd': {},
            'nfsdcld': {},
            'nfsdcltrack': {},
            'mountd': {},
            'statd': {},
            'lockd': {}}
    },
    "idmapd": {
        "pname": "/etc/idmapd.conf",
        "sections": {"General": {}, "Mapping": {}, "Translation": {}}
    }
}


def parse_exports():
    results = SSH_TEST("cat /etc/exports", user, password)
    assert results['result'] is True, f"rc={results['returncode']}, {results['output']}, {results['stderr']}"
    exp = results['stdout'].splitlines()
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


def parse_server_config(conf_type="nfs"):
    '''
    Parse known 'ini' style conf files.  See definition of conf_file above.

    Debian will read to /etc/default/nfs-common and then /etc/nfs.conf
    All TrueNAS NFS settings are in /etc/nfs.conf.d/local.conf as overrides
    '''
    assert conf_type in conf_file.keys(), f"{conf_type} is not a supported conf type"
    pathname = conf_file[conf_type]['pname']
    rv = conf_file[conf_type]['sections']
    expected_sections = rv.keys()

    # Read the file and parse it
    res = ssh(f"cat {pathname}")
    conf = res.splitlines()
    section = ''

    for line in conf:
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            section = line.split('[')[1].split(']')[0]
            assert section in expected_sections, f"Unexpected section found: {section}"
            continue

        k, v = line.split(" = ", 1)
        rv[section].update({k: v})

    return rv


def parse_rpcbind_config():
    '''
    In Debian 12 (Bookwork) rpcbind uses /etc/default/rpcbind.
    Look for /etc/rpcbind.conf in future releases.
    '''
    results = SSH_TEST("cat /etc/default/rpcbind", user, password)
    assert results['result'] is True, f"rc={results['returncode']}, {results['output']}, {results['stderr']}"
    conf = results['stdout'].splitlines()
    rv = {}

    # With bindip the line of intrest looks like: OPTIONS=-w -h 192.168.40.156
    for line in conf:
        if not line or line.startswith("#"):
            continue
        if line.startswith("OPTIONS"):
            opts = line.split('=')[1].split()
            # '-w' is hard-wired, lets confirm that
            assert len(opts) > 0
            assert '-w' == opts[0]
            rv['-w'] = ''
            # If there are more opts they must the bindip settings
            if len(opts) == 3:
                rv[opts[1]] = opts[2]

    return rv


def get_nfs_service_state():
    nfs_service = call('service.query', [['service', '=', 'nfs']], {'get': True})
    return nfs_service['state']


def set_nfs_service_state(do_what=None, expect_to_pass=True, fail_check=None):
    '''
    Start or Stop NFS service
    expect_to_pass parameter is optional
    fail_check parameter is optional
    '''
    assert do_what in ['start', 'stop'], f"Requested invalid service state: {do_what}"
    test_res = {'start': True, 'stop': False}

    try:
        call(f'service.{do_what}', 'nfs', {'silent': False})
    except Exception as e:
        if expect_to_pass:
            assert False, f'Unexpected failure {do_what}ing nfs: {e!r}'
        if fail_check is not None:
            assert fail_check in str(e)
    else:
        if expect_to_pass:
            res = call('service.started', 'nfs')
            assert res == test_res[do_what], f'Expected {test_res[do_what]} for NFS started result, but found {res}'


def confirm_nfsd_processes(expected):
    '''
    Confirm the expected number of nfsd processes are running
    '''
    result = SSH_TEST("cat /proc/fs/nfsd/threads", user, password)
    assert int(result['stdout']) == expected, result


def confirm_mountd_processes(expected):
    '''
    Confirm the expected number of mountd processes are running
    '''
    rx_mountd = r"rpc\.mountd"
    result = SSH_TEST(f"ps -ef | grep '{rx_mountd}' | wc -l", user, password)

    # If there is more than one, we subtract one to account for the rpc.mountd thread manager
    num_detected = int(result['stdout'])
    assert (num_detected - 1 if num_detected > 1 else num_detected) == expected


def confirm_rpc_processes(expected=['idmapd', 'bind', 'statd']):
    '''
    Confirm the expected rpc processes are running
    NB: This only supports the listed names
    '''
    prepend = {'idmapd': 'rpc.', 'bind': 'rpc', 'statd': 'rpc.'}
    for n in expected:
        procname = prepend[n] + n
        result = SSH_TEST(f"pgrep {procname}", user, password)
        assert len(result['output'].splitlines()) > 0


def confirm_nfs_version(expected=[]):
    '''
    Confirm the expected NFS versions are 'enabled and supported'
    Possible values for expected:
        ["3"] means NFSv3 only
        ["4"] means NFSv4 only
        ["3","4"] means both NFSv3 and NFSv4
    '''
    results = SSH_TEST("rpcinfo -s | grep ' nfs '", user, password)
    for v in expected:
        assert v in results['stdout'].strip().split()[1], results


def confirm_rpc_port(rpc_name, port_num):
    '''
    Confirm the expected port for the requested rpc process
    rpc_name = ('mountd', 'status', 'nlockmgr')
    '''
    line = ssh(f"rpcinfo -p | grep {rpc_name} | grep tcp")
    # example:    '100005    3   tcp    618  mountd'
    assert int(line.split()[3]) == port_num, str(line)


class NFS_CONFIG:
    '''This is used to restore the NFS config to it's original state'''
    default_nfs_config = {}


def save_nfs_config():
    '''
    Save the NFS configuration DB at the start of this test module.
    This is used to restore the settings _before_ NFS is disabled near
    the end of the testing. There might be a way to do this with a fixture,
    but it also might require refactoring of the tests.
    This is called at the start of test_01_creating_the_nfs_server.
    '''
    exclude = ('id', 'v4_krb_enabled', 'v4_owner_major', 'keytab_has_nfs_spn', 'managed_nfsd')
    for k, v in filter(lambda x: x[0] not in exclude, call('nfs.config').items()):
        NFS_CONFIG.default_nfs_config[k] = v


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
        retry = 6
        # Under some circumstances, the dataset can balk at being deleted
        # leaving the dataset mounted which then buggers up subsequent tests
        while result.status_code != 200 and retry > 0:
            sleep(10)
            result = DELETE(f"/pool/dataset/id/{urllib.parse.quote(dataset, '')}/")
            retry -= 1
        assert result.status_code == 200, result.text


@contextlib.contextmanager
def nfs_config(options=None):
    '''
    Use this to restore settings when changed within a test function.
    Example usage:
    with nfs_config():
        <code that modifies NFS config>
    '''
    try:
        nfs_db_conf = call("nfs.config")
        excl = ['id', 'v4_krb_enabled', 'v4_owner_major', 'keytab_has_nfs_spn', 'managed_nfsd']
        [nfs_db_conf.pop(key) for key in excl]
        yield copy(nfs_db_conf)
    finally:
        call("nfs.update", nfs_db_conf)


# Enable NFS server
def test_01_init_the_nfs_config():
    # initialize default_nfs_config for later restore
    save_nfs_config()

    # Confirm NFS is not running
    nfs_state = get_nfs_service_state()
    assert nfs_state == 'STOPPED', f'Before update, expected NFS to be STOPPED, but found {nfs_state}'

    payload = {
        "mountd_port": 618,
        "allow_nonroot": False,
        "rpcstatd_port": 871,
        "rpclockd_port": 32803,
        "protocols": ["NFSV3", "NFSV4"]
    }
    nfs_conf = call("nfs.update", payload)
    assert nfs_conf['mountd_port'] == 618
    assert nfs_conf['rpcstatd_port'] == 871
    assert nfs_conf['rpclockd_port'] == 32803

    # Confirm NFS remains not running
    nfs_state = get_nfs_service_state()
    assert nfs_state == 'STOPPED', f'After update, xpected NFS to be STOPPED, but found {nfs_state}'


@pytest.mark.dependency(name='NFS_DATASET_CREATED')
def test_02_creating_dataset_nfs(request):
    payload = {"name": dataset}
    results = POST("/pool/dataset/", payload)
    assert results.status_code == 200, results.text


def test_03_changing_dataset_permissions_of_nfs_dataset(request):
    depends(request, ["NFS_DATASET_CREATED"], scope="session")
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
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


@pytest.mark.dependency(name='NFSID_SHARE_CREATED')
def test_05_creating_a_nfs_share_on_nfs_PATH(request):
    depends(request, ["NFS_DATASET_CREATED"], scope="session")
    global nfsid
    paylaod = {"comment": "My Test Share",
               "path": NFS_PATH,
               "security": ["SYS"]}
    results = POST("/sharing/nfs/", paylaod)
    assert results.status_code == 200, results.text
    nfsid = results.json()['id']


def test_06_starting_nfs_service_at_boot(request):
    results = PUT("/service/id/nfs/", {"enable": True})
    assert results.status_code == 200, results.text


def test_07_checking_to_see_if_nfs_service_is_enabled_at_boot(request):
    results = GET("/service?service=nfs")
    assert results.json()[0]["enable"] is True, results.text


@pytest.mark.dependency(name='NFS_SERVICE_STARTED')
def test_08_starting_nfs_service(request):
    set_nfs_service_state('start')


def test_09_checking_to_see_if_nfs_service_is_running(request):
    results = GET("/service?service=nfs")
    assert results.json()[0]["state"] == "RUNNING", results.text


def test_10_confirm_state_directory(request):
    """
    By default, the NFS state directory is at /var/lib/nfs.
    To support HA systems, we moved this to the system dataset
    at /var/db/system/nfs.  In support of this we updated the
    NFS conf file settings
    """
    depends(request, ["NFS_SERVICE_STARTED"], scope="session")

    # Make sure the conf file has the expected settings
    nfs_state_dir = '/var/db/system/nfs'
    s = parse_server_config()
    assert s['exportd']['state-directory-path'] == nfs_state_dir, str(s)
    assert s['nfsdcld']['storagedir'] == os.path.join(nfs_state_dir, 'nfsdcld'), str(s)
    assert s['nfsdcltrack']['storagedir'] == os.path.join(nfs_state_dir, 'nfsdcltrack'), str(s)
    assert s['nfsdcld']['storagedir'] == os.path.join(nfs_state_dir, 'nfsdcld'), str(s)
    assert s['mountd']['state-directory-path'] == nfs_state_dir, str(s)
    assert s['statd']['state-directory-path'] == nfs_state_dir, str(s)
    # Confirm we have the mount point in the system dataset
    # ----------------------------------------------------------------------
    # NOTE: Update test_001_ssh.py: test_002_first_boot_checks.
    # NOTE: Test fresh-install and upgrade.
    # ----------------------------------------------------------------------


@pytest.mark.parametrize('vers', [3, 4])
def test_11_perform_basic_nfs_ops(request, vers):
    with SSH_NFS(truenas_server.ip, NFS_PATH, vers=vers, user=user, password=password, ip=truenas_server.ip) as n:
        n.create('testfile')
        n.mkdir('testdir')
        contents = n.ls('.')
        assert 'testdir' in contents
        assert 'testfile' in contents

        n.unlink('testfile')
        n.rmdir('testdir')
        contents = n.ls('.')
        assert 'testdir' not in contents
        assert 'testfile' not in contents


def test_12_perform_server_side_copy(request):
    with SSH_NFS(truenas_server.ip, NFS_PATH, vers=4, user=user, password=password, ip=truenas_server.ip) as n:
        n.server_side_copy('ssc1', 'ssc2')


@pytest.mark.parametrize('nfsd,cores,expected', [
    # User specifies number of nfsd, expect: 50 nfsd, 12 mountd
    (50, 1, {'nfsd': 50, 'mountd': 12, 'managed': False}),
    # Dynamic, expect 12 nfsd and 3 mountd
    (None, 12, {'nfsd': 12, 'mountd': 3, 'managed': True}),
    # Dynamic, expect 4 nfsd and 1 mountd
    (None, 4, {'nfsd': 4, 'mountd': 1, 'managed': True}),
    # Dynamic, expect 2 nfsd and 1 mountd
    (None, 2, {'nfsd': 2, 'mountd': 1, 'managed': True}),
    # Dynamic, expect 1 nfsd and 1 mountd
    (None, 1, {'nfsd': 1, 'mountd': 1, 'managed': True}),
    # Should be trapped by validator: Illegal input
    (0, 4, {'nfsd': 4, 'mountd': 1, 'managed': True}),
    # Should be trapped by validator: Illegal input
    (257, 4, {'nfsd': 4, 'mountd': 1, 'managed': True}),
    # Dynamic, max nfsd via calculation is 32
    (None, 48, {'nfsd': 32, 'mountd': 8, 'managed': True}),
    # -1 is a flag to set bindip and confirm 'managed' stays True,
    (-1, 48, {'nfsd': 32, 'mountd': 8, 'managed': True}),
])
def test_19_updating_the_nfs_service(request, nfsd, cores, expected):
    """
    This test verifies that service can be updated in general,
    and also that the 'servers' key can be altered.
    Latter goal is achieved by reading the nfs config file
    and verifying that the value here was set correctly.

    Update:
    The default setting for 'servers' is None. This specifies that we dynamically
    determine the number of nfsd to start based on the capabilities of the system.
    In this state, we choose one nfsd for each CPU core.
    The user can override the dynamic calculation by specifying a
    number greater than zero.

    The number of mountd will be 1/4 the number of nfsd.
    """
    depends(request, ["NFS_SERVICE_STARTED"], scope="session")

    with mock("system.cpu_info", return_value={"core_count": cores}):

        # Use 0 as 'null' flag
        if nfsd is None or nfsd in range(1, 257):
            call("nfs.update", {"servers": nfsd})

            s = parse_server_config()
            assert int(s['nfsd']['threads']) == expected['nfsd'], str(s)
            assert int(s['mountd']['threads']) == expected['mountd'], str(s)

            confirm_nfsd_processes(expected['nfsd'])
            confirm_mountd_processes(expected['mountd'])
            confirm_rpc_processes()

            # In all passing cases, the 'servers' field represents the number of expected nfsd
            nfs_conf = call("nfs.config")
            assert nfs_conf['servers'] == expected['nfsd']
            assert nfs_conf['managed_nfsd'] == expected['managed']
        else:
            if nfsd == -1:
                # We know apriori that the current state is managed_nfsd == True
                with nfs_config():
                    # Test making change to non-'server' setting does not change managed_nfsd
                    call("nfs.update", {"bindip": [truenas_server.ip]})
                    assert call("nfs.config")['managed_nfsd'] == expected['managed']
            else:
                with pytest.raises(ValidationErrors) as ve:
                    assert call("nfs.config")['managed_nfsd'] == expected['managed']
                    call("nfs.update", {"servers": nfsd})

                assert ve.value.errors == [ValidationError('nfs_update.servers', 'Should be between 1 and 256', 22)]


def test_20_update_nfs_share(request):
    depends(request, ["NFSID_SHARE_CREATED"], scope="session")
    nfsid = GET('/sharing/nfs?comment=My Test Share').json()[0]['id']
    payload = {"security": []}
    results = PUT(f"/sharing/nfs/id/{nfsid}/", payload)
    assert results.status_code == 200, results.text


def test_21_checking_to_see_if_nfs_service_is_enabled(request):
    results = GET("/service?service=nfs")
    assert results.json()[0]["state"] == "RUNNING", results.text


networks_to_test = [
    # IPv4
    (["192.168.0.0/24", "192.168.1.0/24"], True),       # Non overlap
    (["192.168.0.0/16", "192.168.1.0/24"], False),      # Ranges overlap
    (["192.168.0.0/24", "192.168.0.211/32"], False),    # Ranges overlap
    (["192.168.0.0/64"], False),    # Invalid range
    (["bogus_network"], False),     # Invalid
    (["192.168.27.211"], True),     # Non-CIDR format
    # IPv6
    (["2001:0db8:85a3:0000:0000:8a2e::/96", "2001:0db8:85a3:0000:0000:8a2f::/96"], True),            # Non overlap
    (["2001:0db8:85a3:0000:0000:8a2e::/96", "2001:0db8:85a3:0000:0000:8a2f::/88"], False),           # Ranges overlap
    (["2001:0db8:85a3:0000:0000:8a2e::/96", "2001:0db8:85a3:0000:0000:8a2e:0370:7334/128"], False),  # Ranges overlap
    (["2001:0db8:85a3:0000:0000:8a2e:0370:7334/256"], False),   # Invalid range
    (["2001:0db8:85a3:0000:0000:8a2e:0370:7334"], True),        # Non-CIDR format
]


@pytest.mark.parametrize("networklist,ExpectedToPass", networks_to_test)
def test_31_check_nfs_share_network(request, networklist, ExpectedToPass):
    """
    Verify that adding a network generates an appropriate line in exports
    file for same path. Sample:

    "/mnt/dozer/nfs"\
        192.168.0.0/24(sec=sys,rw,subtree_check)\
        192.168.1.0/24(sec=sys,rw,subtree_check)
    """
    depends(request, ["NFSID_SHARE_CREATED", "NFS_SERVICE_STARTED"], scope="session")

    results = PUT(f"/sharing/nfs/id/{nfsid}/", {'networks': networklist})
    if ExpectedToPass:
        assert results.status_code == 200, results.text
    else:
        assert results.status_code != 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)

    exports_networks = [x['host'] for x in parsed[0]['opts']]
    if ExpectedToPass:
        # The input is converted to CIDR format which often will
        # look different from the input. e.g. 1.2.3.4/16 -> 1.2.0.0/16
        cidr_list = [str(ipaddress.ip_network(x, strict=False)) for x in networklist]
        # The entry should be present
        diff = set(cidr_list) ^ set(exports_networks)
        assert len(diff) == 0, f'diff: {diff}, exports: {parsed}'
    else:
        # The entry should not be present
        assert len(exports_networks) == 1, str(parsed)

    # Reset to default
    results = PUT(f"/sharing/nfs/id/{nfsid}/", {'networks': []})
    assert results.status_code == 200, results.text

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    exports_networks = [x['host'] for x in parsed[0]['opts']]
    assert len(exports_networks) == 1, str(parsed)
    assert exports_networks[0] == '*', str(parsed)


# Parameters for test_32
hostnames_to_test = [
    # Valid hostnames (IP addresses) and netgroup
    (["192.168.0.69", "192.168.0.70", "@fakenetgroup"], True),
    # Valid wildcarded hostnames
    (["asdfnm-*", "?-asdfnm-*", "asdfnm[0-9]", "nmix?-*dev[0-9]"], True),
    # Valid wildcarded hostname with valid 'domains'
    (["asdfdm-*.example.com", "?-asdfdm-*.ixsystems.com",
      "asdfdm[0-9].example.com", "dmix?-*dev[0-9].ixsystems.com"], True),
    # Invalid hostnames
    (["-asdffail", "*.asdffail.com", "*.*.com", "bozofail.?.*"], False),
    (["bogus/name"], False),
    (["192.168.1.0/24"], False),
    # Mix of valid and invalid hostnames
    (["asdfdm[0-9].example.com", "-asdffail",
      "devteam-*.ixsystems.com", "*.asdffail.com"], False),
    # Duplicate names (not allowed)
    (["192.168.1.0", "192.168.1.0"], False),
    (["ixsystems.com", "ixsystems.com"], False),
    # Mixing 'everybody' and named host
    (["ixsystems.com", "*"], False),    # Test NAS-123042, export collision, same path and entry
    (["*", "*.ixsystems.com"], False),  # Test NAS-123042, export collision, same path and entry
    # Invalid IP address
    (["192.168.1.o"], False),
    # Hostname with spaces
    (["bad host"], False),
    # IPv6
    (["2001:0db8:85a3:0000:0000:8a2e:0370:7334"], True)
]


@pytest.mark.parametrize("hostlist,ExpectedToPass", hostnames_to_test)
def test_32_check_nfs_share_hosts(request, hostlist, ExpectedToPass):
    """
    Verify that adding a network generates an appropriate line in exports
    file for same path. Sample:

    "/mnt/dozer/nfs"\
        192.168.0.69(sec=sys,rw,subtree_check)\
        192.168.0.70(sec=sys,rw,subtree_check)\
        @fakenetgroup(sec=sys,rw,subtree_check)

    host name handling in middleware:
        If the host name contains no wildcard or special chars,
            then we test it with a look up
        else we apply the host name rules and skip the look up

    The rules for the host field are:
    - Dashes are allowed, but a level cannot start or end with a dash, '-'
    - Only the left most level may contain special characters: '*','?' and '[]'
    """
    depends(request, ["NFSID_SHARE_CREATED", "NFS_SERVICE_STARTED"], scope="session")
    results = PUT(f"/sharing/nfs/id/{nfsid}/", {'hosts': hostlist})
    if ExpectedToPass:
        assert results.status_code == 200, results.text
    else:
        assert results.status_code != 200, results.text

    # Check the exports file
    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    exports_hosts = [x['host'] for x in parsed[0]['opts']]
    if ExpectedToPass:
        # The entry should be present
        diff = set(hostlist) ^ set(exports_hosts)
        assert len(diff) == 0, f'diff: {diff}, exports: {parsed}'
    else:
        # The entry should not be present
        assert len(exports_hosts) == 1, str(parsed)

    # Reset to default should always pass
    cleanup_results = PUT(f"/sharing/nfs/id/{nfsid}/", {'hosts': []})
    assert cleanup_results.status_code == 200, results.text
    # Check the exports file to confirm it's clear
    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    exports_hosts = [x['host'] for x in parsed[0]['opts']]
    assert len(exports_hosts) == 1, str(parsed)


def test_33_check_nfs_share_ro(request):
    """
    Verify that toggling `ro` will cause appropriate change in
    exports file. We also verify with write tests on a local mount.
    """

    depends(request, ["NFSID_SHARE_CREATED"], scope="session")
    # Make sure we end up in the original state with 'rw'
    try:
        # Confirm 'rw' initial state and create a file and dir
        parsed = parse_exports()
        assert len(parsed) == 1, str(parsed)
        assert "rw" in parsed[0]['opts'][0]['parameters'], str(parsed)

        # Create the file and dir
        with SSH_NFS(truenas_server.ip, NFS_PATH, user=user, password=password, ip=truenas_server.ip) as n:
            n.create("testfile_should_pass")
            n.mkdir("testdir_should_pass")

        # Change to 'ro'
        results = PUT(f"/sharing/nfs/id/{nfsid}/", {'ro': True})
        assert results.status_code == 200, results.text

        # Confirm 'ro' state and behavior
        parsed = parse_exports()
        assert len(parsed) == 1, str(parsed)
        assert "rw" not in parsed[0]['opts'][0]['parameters'], str(parsed)

        # Attempt create and delete
        with SSH_NFS(truenas_server.ip, NFS_PATH, user=user, password=password, ip=truenas_server.ip) as n:
            with pytest.raises(RuntimeError) as re:
                n.create("testfile_should_fail")
                assert False, "Should not have been able to create a new file"
            assert 'cannot touch' in str(re), re

            with pytest.raises(RuntimeError) as re:
                n.mkdir("testdir_should_fail")
                assert False, "Should not have been able to create a new directory"
            assert 'cannot create directory' in str(re), re

    finally:
        results = PUT(f"/sharing/nfs/id/{nfsid}/", {'ro': False})
        assert results.status_code == 200, results.text

        parsed = parse_exports()
        assert len(parsed) == 1, str(parsed)
        assert "rw" in parsed[0]['opts'][0]['parameters'], str(parsed)

        # Cleanup the file and dir
        with SSH_NFS(truenas_server.ip, NFS_PATH, user=user, password=password, ip=truenas_server.ip) as n:
            n.unlink("testfile_should_pass")
            n.rmdir("testdir_should_pass")


def test_34_check_nfs_share_maproot(request):
    """
    root squash is always enabled, and so maproot accomplished through
    anonuid and anongid

    Sample:
    "/mnt/dozer/NFSV4"\
        *(sec=sys,rw,anonuid=65534,anongid=65534,subtree_check)
    """
    depends(request, ["NFSID_SHARE_CREATED"], scope="session")

    call('sharing.nfs.update', nfsid, {
        'maproot_user': 'nobody',
        'maproot_group': 'nogroup'
    })

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)

    params = parsed[0]['opts'][0]['parameters']
    assert 'anonuid=65534' in params, str(parsed)
    assert 'anongid=65534' in params, str(parsed)

    """
    setting maproot_user and maproot_group to root should
    cause us to append "no_root_squash" to options.
    """
    call('sharing.nfs.update', nfsid, {
        'maproot_user': 'root',
        'maproot_group': 'root'
    })

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

    call('sharing.nfs.update', nfsid, {
        'maproot_user': '',
        'maproot_group': ''
    })

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
    depends(request, ["NFSID_SHARE_CREATED"], scope="session")

    call('sharing.nfs.update', nfsid, {
        'mapall_user': 'nobody',
        'mapall_group': 'nogroup'
    })

    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)

    params = parsed[0]['opts'][0]['parameters']
    assert 'anonuid=65534' in params, str(parsed)
    assert 'anongid=65534' in params, str(parsed)
    assert 'all_squash' in params, str(parsed)

    call('sharing.nfs.update', nfsid, {
        'mapall_user': '',
        'mapall_group': ''
    })

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
    depends(request, ["NFSID_SHARE_CREATED"], scope="session")

    with directory(f'{NFS_PATH}/sub1') as tmp_path:
        with nfs_share(tmp_path, {'hosts': ['127.0.0.1']}):
            parsed = parse_exports()
            assert len(parsed) == 2, str(parsed)

            assert parsed[0]['path'] == NFS_PATH, str(parsed)
            assert 'no_subtree_check' in parsed[0]['opts'][0]['parameters'], str(parsed)

            assert parsed[1]['path'] == tmp_path, str(parsed)
            assert 'subtree_check' in parsed[1]['opts'][0]['parameters'], str(parsed)


class Test37WithFixture:
    """
    Wrap a class around test_37 to allow calling the fixture only once
    in the parametrized test
    """

    # TODO: Work up a valid IPv6 test
    # res = SSH_TEST(f"ip address show {interface} | grep inet6", user, password, ip)
    # ipv6_network = str(res['output'].split()[1])
    # ipv6_host = ipv6_network.split('/')[0]

    @pytest.fixture(scope='class')
    def dataset_and_dirs(self):
        """
        Create a dataset and an NFS share for it for host 127.0.0.1 only
        In the dataset, create directories: dir1, dir2, dir3
        In each directory, create subdirs: subdir1, subdir2, subdir3
        """

        # Characteristics of expected error messages
        err_strs = [
            ["Another share", "everybody"],
            ["exported to everybody", "another share"],
            ["Another share", "same path"],
            ["This or another", "overlaps"],
            ["Another NFS share already exports"],
            ["Symbolic links"]
        ]

        vol0 = f'/mnt/{pool_name}/VOL0'
        with nfs_dataset('VOL0'):
            # Top level shared to narrow host
            with nfs_share(vol0, {'hosts': ['127.0.0.1']}):
                # Get the initial list of entries for the cleanup test
                contents = GET('/sharing/nfs').json()
                startIdList = [item.get('id') for item in contents]

                # Create the dirs
                dirs = ["everybody_1", "everybody_2",
                        "limited_1", "limited_2",
                        "dir_1", "dir_2"]
                subdirs = ["subdir1", "subdir2", "subdir3"]
                try:
                    for dir in dirs:
                        results = SSH_TEST(f"mkdir -p {vol0}/{dir}", user, password)
                        assert results['result'] is True
                        for subdir in subdirs:
                            results = SSH_TEST(f"mkdir -p {vol0}/{dir}/{subdir}", user, password)
                            assert results['result'] is True
                            # And symlinks
                            results = SSH_TEST(
                                f"ln -sf {vol0}/{dir}/{subdir} {vol0}/{dir}/symlink2{subdir}",
                                user, password
                            )
                            assert results['result'] is True

                    yield vol0, err_strs
                finally:
                    # Remove the created dirs
                    for dir in dirs:
                        SSH_TEST(f"rm -rf {vol0}/{dir}", user, password)
                        assert results['result'] is True

                    # Remove the created shares
                    contents = GET('/sharing/nfs').json()
                    endIdList = [item.get('id') for item in contents]
                    for id in endIdList:
                        if id not in startIdList:
                            result = DELETE(f"/sharing/nfs/id/{id}/")
                            assert result.status_code == 200, result.text

    # Parameters for test_37
    # Directory (dataset share VOL0), isHost, HostOrNet, ExpectedToPass, ErrFormat
    dirs_to_export = [
        ("everybody_1", True, ["*"], True, None),                    # 0: Host - Test NAS-120957
        ("everybody_2", True, ["*"], True, None),                    # 1: Host - Test NAS-120957, allow non-related paths to same hosts
        ("everybody_2", False, ["192.168.1.0/22"], False, 2),        # 2: Network - Already exported to everybody in test 1
        ("limited_1", True, ["127.0.0.1"], True, None),              # 3: Host - Test NAS-123042, allow export of subdirs
        ("limited_2", True, ["127.0.0.1"], True, None),              # 4: Host - Test NAS-120957, NAS-123042
        ("limited_2", True, ["127.0.0.1"], False, 3),                # 4: Host - Test NAS-127220, exact repeat to host
        ("limited_2", True, ["*"], False, 1),                        # 5: Host - Test NAS-123042, export collision, same path, different entry
        ("dir_1", True, ["*.example.com"], True, None),              # 6: Host - Setup for test 7: Host with wildcard
        ("dir_1", True, ["*.example.com"], False, 2),                # 7: Host - Already exported in test 6
        ("dir_1/subdir1", True, ["192.168.0.0"], True, None),        # 8: Host - Setup for test 9: Host as IP address
        ("dir_1/subdir1", True, ["192.168.0.0"], False, 3),          # 9: Host - Alread exported in test 8
        ("dir_1/subdir2", False, ["2001:0db8:85a3:0000:0000:8a2e::/96"], True, None),    # 10: Network - Setup for test 11: IPv6 network range
        ("dir_1/subdir2", True, ["2001:0db8:85a3:0000:0000:8a2e:0370:7334"], False, 3),  # 11: Host - IPv6 network overlap
        ("dir_1/subdir3", True, ["192.168.27.211"], True, None),     # 12: Host - Test NAS-124269, setup for test 13
        ("dir_1/subdir3", False, ["192.168.24.0/22"], False, 3),     # 13: Network - Test NAS-124269, trap network overlap
        ("limited_2/subdir2", True, ["127.0.0.1"], True, None),      # 14: Host - Test NAS-123042, allow export of subdirs
        ("limited_1/subdir2", True, ["*"], True, None),              # 15: Host - Test NAS-123042, everybody
        ("limited_1/subdir2", True, ["*"], False, 4),                # 16: Host - Test NAS-127220, exact repeat to everybody
        ("dir_2/subdir2", False, ["192.168.1.0/24"], True, None),    # 17: Network - Setup for test 17: Wide network range
        ("dir_2/subdir2", False, ["192.168.1.0/32"], False, 3),      # 18: Network - Test NAS-123042 - export collision, overlaping networks
        ("limited_1/subdir3", True, ["192.168.1.0", "*.ixsystems.com"], True, None),  # 19: Host - Test NAS-123042
        ("dir_1/symlink2subdir3", True, ["192.168.0.0"], False, 5),  # 20: Host - Block exporting symlinks
    ]

    @pytest.mark.parametrize("dirname,isHost,HostOrNet,ExpectedToPass, ErrFormat", dirs_to_export)
    def test_37_check_nfsdir_subtree_share(self, request, dataset_and_dirs, dirname, isHost, HostOrNet, ExpectedToPass, ErrFormat):
        """
        Sharing subtrees to the same host can cause problems for
        NFSv3.  This check makes sure a share creation follows
        the rules.
            * First match is applied
            * A new path that is _the same_ as existing path cannot be shared to same 'host'

        For example, the following is not allowed:
        "/mnt/dozer/NFS"\
            fred(rw)
        "/mnt/dozer/NFS"\
            fred(ro)

        Also not allowed are collisions that may result in unexpected share permissions.
        For example, the following is not allowed:
        "/mnt/dozer/NFS"\
            *(rw)
        "/mnt/dozer/NFS"\
            marketing(ro)
        """

        vol, err_strs = dataset_and_dirs
        dirpath = f'{vol}/{dirname}'
        if isHost:
            payload = {"path": dirpath, "hosts": HostOrNet}
        else:
            payload = {"path": dirpath, "networks": HostOrNet}

        if ExpectedToPass:
            call("sharing.nfs.create", payload)
        else:
            with pytest.raises(ValidationErrors) as ve:
                call("sharing.nfs.create", payload)
            errStr = str(ve.value.errors[0])
            # Confirm we have the expected error message format
            for this_substr in err_strs[ErrFormat]:
                assert this_substr in errStr


def test_38_check_nfs_allow_nonroot_behavior(request):
    """
    If global configuration option "allow_nonroot" is set, then
    we append "insecure" to each exports line.
    Since this is a global option, it triggers an nfsd restart
    even though it's not technically required.
    Linux will, by default, mount using a priviledged port (1..1023)
    MacOS NFS mounts do not follow this 'standard' behavior.

    Four conditions to test:
        server:  secure       (e.g. allow_nonroot is False)
            client: resvport   -> expect to pass.
            client: noresvport -> expect to fail.
        server: insecure    (e.g. allow_nonroot is True)
            client: resvport   -> expect to pass.
            client: noresvport -> expect to pass

    Sample:
    "/mnt/dozer/NFSV4"\
        *(sec=sys,rw,insecure,no_subtree_check)
    """

    def get_client_nfs_port():
        '''
        Output from netstat -nt looks like:
            tcp        0      0 127.0.0.1:50664         127.0.0.1:6000          ESTABLISHED
        The client port is the number after the ':' in the 5th column
        '''
        rv = (None, None)
        res = ssh("netstat -nt")
        for line in str(res).splitlines():
            # The server will listen on port 2049
            if f"{truenas_server.ip}:2049" == line.split()[3]:
                rv = (line, line.split()[4].split(':')[1])
        return rv

    depends(request, ["NFSID_SHARE_CREATED"], scope="session")

    # Verify that NFS server configuration is as expected
    with nfs_config() as nfs_conf_orig:

        # --- Test: allow_nonroot is False
        assert nfs_conf_orig['allow_nonroot'] is False, nfs_conf_orig

        # Confirm setting in /etc/exports
        parsed = parse_exports()
        assert len(parsed) == 1, str(parsed)
        assert 'insecure' not in parsed[0]['opts'][0]['parameters'], str(parsed)

        # Confirm we allow mounts from 'root' ports
        with SSH_NFS(truenas_server.ip, NFS_PATH, vers=4, user=user, password=password, ip=truenas_server.ip):
            client_port = get_client_nfs_port()
            assert client_port[1] is not None, f"Failed to get client port: f{client_port[0]}"
            assert int(client_port[1]) < 1024, \
                f"client_port is not in 'root' range: {client_port[1]}\n{client_port[0]}"

        # Confirm we block mounts from 'non-root' ports
        with pytest.raises(RuntimeError) as re:
            with SSH_NFS(truenas_server.ip, NFS_PATH, vers=4, options=['noresvport'],
                         user=user, password=password, ip=truenas_server.ip):
                pass
            # We should not get to this assert
            assert False, "Unexpected success with mount"
        assert 'Operation not permitted' in str(re), re

        # --- Test: allow_nonroot is True
        new_nfs_conf = call('nfs.update', {"allow_nonroot": True})
        assert new_nfs_conf['allow_nonroot'] is True, new_nfs_conf

        parsed = parse_exports()
        assert len(parsed) == 1, str(parsed)
        assert 'insecure' in parsed[0]['opts'][0]['parameters'], str(parsed)

        # Confirm we allow mounts from 'root' ports
        with SSH_NFS(truenas_server.ip, NFS_PATH, vers=4, user=user, password=password, ip=truenas_server.ip):
            client_port = get_client_nfs_port()
            assert client_port[1] is not None, "Failed to get client port"
            assert int(client_port[1]) < 1024, \
                f"client_port is not in 'root' range: {client_port[1]}\n{client_port[0]}"

        # Confirm we allow mounts from 'non-root' ports
        with SSH_NFS(truenas_server.ip, NFS_PATH, vers=4, options=['noresvport'],
                     user=user, password=password, ip=truenas_server.ip):
            client_port = get_client_nfs_port()
            assert client_port[1] is not None, "Failed to get client port"
            assert int(client_port[1]) >= 1024, \
                f"client_port is not in 'non-root' range: {client_port[1]}\n{client_port[0]}"

    # Confirm setting was returned to original state
    parsed = parse_exports()
    assert len(parsed) == 1, str(parsed)
    assert 'insecure' not in parsed[0]['opts'][0]['parameters'], str(parsed)


def test_39_check_nfs_service_protocols_parameter(request):
    """
    This test verifies that changing the `protocols` option generates expected
    changes in nfs kernel server config.  In most cases we will also confirm
    the settings have taken effect.

    For the time being this test will also exercise the deprecated `v4` option
    to the same effect, but this will later be removed.

    NFS must be enabled for this test to succeed as while the config (i.e.
    database) will be updated regardless, the server config file will not
    be updated.
    """
    results = GET("/service?service=nfs")
    assert results.json()[0]["state"] == "RUNNING", results

    # Multiple restarts cause systemd failures.  Reset the systemd counters.
    reset_svcs("nfs-idmapd nfs-mountd nfs-server rpcbind rpc-statd")

    # Check existing config (both NFSv3 & NFSv4 configured)
    results = GET("/nfs")
    assert results.status_code == 200, results.text
    protocols = results.json()['protocols']
    assert "NFSV3" in protocols, results.text
    assert "NFSV4" in protocols, results.text

    s = parse_server_config()
    assert s['nfsd']["vers3"] == 'y', str(s)
    assert s['nfsd']["vers4"] == 'y', str(s)
    confirm_nfs_version(['3', '4'])

    # Turn off NFSv4 (v3 on)
    results = PUT("/nfs/", {"protocols": ["NFSV3"]})
    assert results.status_code == 200, results.text

    results = GET("/nfs")
    assert results.status_code == 200, results.text
    protocols = results.json()['protocols']
    assert "NFSV3" in protocols, results.text
    assert "NFSV4" not in protocols, results.text

    s = parse_server_config()
    assert s['nfsd']["vers3"] == 'y', str(s)
    assert s['nfsd']["vers4"] == 'n', str(s)

    # Confirm setting has taken effect: v4->off, v3->on
    confirm_nfs_version(['3'])

    # Try (and fail) to turn off both
    results = PUT("/nfs/", {"protocols": []})
    assert results.status_code != 200, results.text

    # Turn off NFSv3 (v4 on)
    results = PUT("/nfs/", {"protocols": ["NFSV4"]})
    assert results.status_code == 200, results.text

    results = GET("/nfs")
    assert results.status_code == 200, results.text
    protocols = results.json()['protocols']
    assert "NFSV3" not in protocols, results.text
    assert "NFSV4" in protocols, results.text

    s = parse_server_config()
    assert s['nfsd']["vers3"] == 'n', str(s)
    assert s['nfsd']["vers4"] == 'y', str(s)

    # Confirm setting has taken effect: v4->on, v3->off
    confirm_nfs_version(['4'])

    # Finally turn both back on again
    results = PUT("/nfs/", {"protocols": ["NFSV3", "NFSV4"]})
    assert results.status_code == 200, results.text

    results = GET("/nfs")
    assert results.status_code == 200, results.text
    protocols = results.json()['protocols']
    assert "NFSV3" in protocols, results.text
    assert "NFSV4" in protocols, results.text

    s = parse_server_config()
    assert s['nfsd']["vers3"] == 'y', str(s)
    assert s['nfsd']["vers4"] == 'y', str(s)

    # Confirm setting has taken effect: v4->on, v3->on
    confirm_nfs_version(['3', '4'])


def test_40_check_nfs_service_udp_parameter(request):
    """
    This test verifies the udp config is NOT in the DB and
    that it is NOT in the etc file.
    """
    depends(request, ["NFS_SERVICE_STARTED"], scope="session")

    # The 'udp' setting should have been removed
    nfs_conf = call('nfs.config')
    assert nfs_conf.get('udp') is None, nfs_conf

    s = parse_server_config()
    assert s.get('nfsd', {}).get('udp') is None, s


def test_41_check_nfs_service_ports(request):
    """
    This test verifies that the custom ports we specified in
    earlier NFS tests are set in the relevant files and are active.
    """
    with nfs_config() as config_db:
        # Compare DB with setting in /etc/nfs.conf.d/local.conf
        s = parse_server_config()
        assert int(s['mountd']['port']) == config_db["mountd_port"], str(s)
        assert int(s['statd']['port']) == config_db["rpcstatd_port"], str(s)
        assert int(s['lockd']['port']) == config_db["rpclockd_port"], str(s)

        # Confirm port settings are active
        confirm_rpc_port('mountd', config_db["mountd_port"])
        confirm_rpc_port('status', config_db["rpcstatd_port"])
        confirm_rpc_port('nlockmgr', config_db["rpclockd_port"])


def test_42_check_nfs_client_status(request):
    """
    This test checks the function of API endpoints to list NFSv3 and
    NFSv4 clients by performing loopback mounts on the remote TrueNAS
    server and then checking client counts. Due to inherent imprecision
    of counts over NFSv3 protcol (specifically with regard to decrementing
    sessions) we only verify that count is non-zero for NFSv3.
    """

    depends(request, ["NFSID_SHARE_CREATED"], scope="session")
    with SSH_NFS(truenas_server.ip, NFS_PATH, vers=3, user=user, password=password, ip=truenas_server.ip):
        results = GET('/nfs/get_nfs3_clients/', payload={
            'query-filters': [],
            'query-options': {'count': True}
        })
        assert results.status_code == 200, results.text
        assert results.json() != 0, results.text

    with SSH_NFS(truenas_server.ip, NFS_PATH, vers=4, user=user, password=password, ip=truenas_server.ip):
        results = GET('/nfs/get_nfs4_clients/', payload={
            'query-filters': [],
            'query-options': {'count': True}
        })
        assert results.status_code == 200, results.text
        assert results.json() == 1, results.text


def test_43_check_nfsv4_acl_support(request):
    """
    This test validates reading and setting NFSv4 ACLs through an NFSv4
    mount in the following manner for NFSv4.2, NFSv4.1 & NFSv4.0:
    1) Create and locally mount an NFSv4 share on the TrueNAS server
    2) Iterate through all possible permissions options and set them
       via an NFS client, read back through NFS client, and read resulting
       ACL through the filesystem API.
    3) Repeat same process for each of the supported ACE flags.
    4) For NFSv4.1 or NFSv4.2, repeat same process for each of the
       supported acl_flags.
    """
    depends(request, ["NFS_SERVICE_STARTED"], scope="session")
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
    for (version, test_acl_flag) in [(4, True), (4.1, True), (4.0, False)]:
        theacl = [
            {"tag": "owner@", "id": -1, "perms": test_perms, "flags": test_flags, "type": "ALLOW"},
            {"tag": "group@", "id": -1, "perms": test_perms, "flags": test_flags, "type": "ALLOW"},
            {"tag": "everyone@", "id": -1, "perms": test_perms, "flags": test_flags, "type": "ALLOW"},
            {"tag": "USER", "id": 65534, "perms": test_perms, "flags": test_flags, "type": "ALLOW"},
            {"tag": "GROUP", "id": 666, "perms": test_perms.copy(), "flags": test_flags.copy(), "type": "ALLOW"},
        ]
        with nfs_dataset("test_nfs4_acl", {"acltype": "NFSV4", "aclmode": "PASSTHROUGH"}, theacl):
            with nfs_share(acl_nfs_path):
                with SSH_NFS(truenas_server.ip, acl_nfs_path, vers=version, user=user, password=password, ip=truenas_server.ip) as n:
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
                    if test_acl_flag:
                        assert 'none' == n.getaclflag(".")
                        for acl_flag in ['auto-inherit', 'protected', 'defaulted']:
                            n.setaclflag(".", acl_flag)
                            assert acl_flag == n.getaclflag(".")
                            payload = {
                                'path': acl_nfs_path,
                                'simplified': False
                            }
                            result = POST('/filesystem/getacl/', payload)
                            assert result.status_code == 200, result.text
                            # Normalize the flag_is_set name for comparision to plugin equivalent
                            # (just remove the '-' from auto-inherit)
                            if acl_flag == 'auto-inherit':
                                flag_is_set = 'autoinherit'
                            else:
                                flag_is_set = acl_flag
                            # Now ensure that only the expected flag is set
                            nfs41_flags = result.json()['nfs41_flags']
                            for flag in ['autoinherit', 'protected', 'defaulted']:
                                if flag == flag_is_set:
                                    assert nfs41_flags[flag], nfs41_flags
                                else:
                                    assert not nfs41_flags[flag], nfs41_flags


def test_44_check_nfs_xattr_support(request):
    """
    Perform basic validation of NFSv4.2 xattr support.
    Mount path via NFS 4.2, create a file and dir,
    and write + read xattr on each.
    """
    xattr_nfs_path = f'/mnt/{pool_name}/test_nfs4_xattr'
    with nfs_dataset("test_nfs4_xattr"):
        with nfs_share(xattr_nfs_path):
            with SSH_NFS(truenas_server.ip, xattr_nfs_path, vers=4.2, user=user, password=password, ip=truenas_server.ip) as n:
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
    disabled = {
        "NFS": ["NONE"],
        "NFSD": ["NONE"],
        "NLM": ["NONE"],
        "RPC": ["NONE"]
    }
    enabled = {
        "NFS": ["PROC", "XDR", "CLIENT", "MOUNT", "XATTR_CACHE"],
        "NFSD": ["ALL"],
        "NLM": ["CLIENT", "CLNTLOCK", "SVC"],
        "RPC": ["CALL", "NFS", "TRANS"]
    }
    failure = {"RPC": ["CALL", "NFS", "TRANS", "NONE"]}

    try:
        assert call('nfs.get_debug') == disabled
        assert call('nfs.set_debug', enabled)
        debug_values = call('nfs.get_debug')
        assert all((set(enabled[i]) == set(debug_values[i]) for i in debug_values)), debug_values

        with pytest.raises(Exception) as ve:
            # This should generate an ValueError exception on the system
            call('nfs.set_debug', failure)
            assert ve.value.errno == errno.EINVAL, ve
    finally:
        assert call('nfs.set_debug', disabled)
        debug_values = call('nfs.get_debug')
        assert all((set(disabled[i]) == set(debug_values[i]) for i in debug_values)), debug_values


def test_46_set_bind_ip():
    '''
    This test requires a static IP address
    * Test the private nfs.bindip call
    * Test the actual bindip config setting
      - Confirm setting in conf files
      - Confirm service on IP address
    '''
    choices = call("nfs.bindip_choices")
    assert truenas_server.ip in choices

    call("nfs.bindip", {"bindip": [truenas_server.ip]})
    call("nfs.bindip", {"bindip": []})

    # Test config with bindip.  Use choices from above
    # TODO: check with 'nmap -sT <IP>' from the runner.
    with nfs_config() as db_conf:

        # Should have no bindip setting
        nfs_conf = parse_server_config()
        rpc_conf = parse_rpcbind_config()
        assert db_conf['bindip'] == []
        assert nfs_conf['nfsd'].get('host') is None
        assert rpc_conf.get('-h') is None

        # Set bindip
        call("nfs.update", {"bindip": [truenas_server.ip]})

        # Confirm we see it in the nfs and rpc conf files
        nfs_conf = parse_server_config()
        rpc_conf = parse_rpcbind_config()
        assert truenas_server.ip in nfs_conf['nfsd'].get('host'), f"nfs_conf = {nfs_conf}"
        assert truenas_server.ip in rpc_conf.get('-h'), f"rpc_conf = {rpc_conf}"


def test_48_syslog_filters(request):
    """
    This test checks the function of the mountd_log setting to filter
    rpc.mountd messages that have priority DEBUG to NOTICE.
    We performing loopback mounts on the remote TrueNAS server and
    then check the syslog for rpc.mountd messages.  Outside of SSH_NFS
    we test the umount case.
    """
    depends(request, ["NFSID_SHARE_CREATED"], scope="session")
    with nfs_config():

        # The effect is much more clear if there are many mountd.
        # We can force this by configuring many nfsd
        call("nfs.update", {"servers": 24})

        # Confirm default setting: mountd logging enabled
        call("nfs.update", {"mountd_log": True})

        # Add dummy entries to avoid false positives
        for i in range(10):
            ssh(f'logger "====== {i}: NFS test_48_syslog_filters (with) ======"')
        with SSH_NFS(truenas_server.ip, NFS_PATH, vers=4, user=user, password=password, ip=truenas_server.ip):
            num_tries = 10
            found = False
            res = ""
            while not found and num_tries > 0:
                numlines = 3 * (10 - num_tries) + 5
                res = ssh(f"tail -{numlines} /var/log/syslog")
                if "rpc.mountd" in res:
                    found = True
                    break
                num_tries -= 1
                sleep(10 - num_tries)

            assert found, f"Expected to find 'rpc.mountd' in the output but found:\n{res}"

        # NOTE: Additional mountd messages will get logged on unmount at the exit of the 'with'

        # Disable mountd logging
        call("nfs.update", {"mountd_log": False})

        # Add dummy entries to avoid false positives
        for i in range(10):
            ssh(f'logger "====== {i}: NFS test_48_syslog_filters (without) ======"')
        with SSH_NFS(truenas_server.ip, NFS_PATH, vers=4, user=user, password=password, ip=truenas_server.ip):
            # wait a few seconds to make sure syslog has a chance to flush log messages
            sleep(4)
            res = ssh("tail -10 /var/log/syslog")
            assert "rpc.mountd" not in res, f"Did not expect to find 'rpc.mountd' in the output but found:\n{res}"

        # Get a second chance to catch mountd messages on the umount.  They should not be present.
        sleep(4)
        res = ssh("tail -10 /var/log/syslog")
        assert "rpc.mountd" not in res, f"Did not expect to find 'rpc.mountd' in the output but found:\n{res}"


@pytest.mark.parametrize('type,data', [
    ('InvalidAssignment', [
        {'maproot_user': 'baduser'}, 'maproot_user', 'User not found: baduser'
    ]),
    ('InvalidAssignment', [
        {'maproot_group': 'badgroup'}, 'maproot_user', 'This field is required when map group is specified'
    ]),
    ('InvalidAssignment', [
        {'mapall_user': 'baduser'}, 'mapall_user', 'User not found: baduser'
    ]),
    ('InvalidAssignment', [
        {'mapall_group': 'badgroup'}, 'mapall_user', 'This field is required when map group is specified'
    ]),
    ('MissingUser', [
        'maproot_user', 'missinguser'
    ]),
    ('MissingUser', [
        'mapall_user', 'missinguser'
    ]),
    ('MissingGroup', [
        'maproot_group', 'missingroup'
    ]),
    ('MissingGroup', [
        'mapall_group', 'missingroup'
    ]),
])
def test_50_nfs_invalid_user_group_mapping(request, type, data):
    '''
    Verify we properly trap and handle invalid user and group mapping
    Two conditions:
        1) Catch invalid assignments
        2) Catch invalid settings at NFS start
    '''
    depends(request, ["NFSID_SHARE_CREATED"], scope="session")

    ''' Local helper routine '''
    def run_missing_usrgrp_test(usrgrp, tmp_path, share, usrgrpInst):
        parsed = parse_exports()
        assert len(parsed) == 2, str(parsed)
        this_share = [entry for entry in parsed if entry['path'] == f'{tmp_path}']
        assert len(this_share) == 1, f"Did not find share {tmp_path}.\nexports = {parsed}"

        # Remove the user/group and restart nfs
        call(f'{usrgrp}.delete', usrgrpInst['id'])
        call('service.restart', 'nfs')

        # An alert should be generated
        alerts = call('alert.list')
        this_alert = [entry for entry in alerts if entry['klass'] == "NFSexportMappingInvalidNames"]
        assert len(this_alert) == 1, f"Did not find alert for 'NFSexportMappingInvalidNames'.\n{alerts}"

        # The NFS export should have been removed
        parsed = parse_exports()
        assert len(parsed) == 1, str(parsed)
        this_share = [entry for entry in parsed if entry['path'] == f'{tmp_path}']
        assert len(this_share) == 0, f"Unexpectedly found share {tmp_path}.\nexports = {parsed}"

        # Modify share to map with a built-in user or group and restart NFS
        call('sharing.nfs.update', share, {data[0]: "ftp"})
        call('service.restart', 'nfs')

        # The alert should be cleared
        alerts = call('alert.list')
        this_alert = [entry for entry in alerts if entry['key'] == "NFSexportMappingInvalidNames"]
        assert len(this_alert) == 0, f"Unexpectedly found alert 'NFSexportMappingInvalidNames'.\n{alerts}"

        # Share should have been restored
        parsed = parse_exports()
        assert len(parsed) == 2, str(parsed)
        this_share = [entry for entry in parsed if entry['path'] == f'{tmp_path}']
        assert len(this_share) == 1, f"Did not find share {tmp_path}.\nexports = {parsed}"

    ''' Test Processing '''
    with directory(f'{NFS_PATH}/sub1') as tmp_path:

        if type == 'InvalidAssignment':
            payload = {'path': tmp_path} | data[0]
            with pytest.raises(ValidationErrors) as ve:
                call("sharing.nfs.create", payload)
            assert ve.value.errors == [ValidationError('sharingnfs_create.' + f'{data[1]}', data[2], 22)]

        elif type == 'MissingUser':
            usrname = data[1]
            testkey, testval = data[0].split('_')

            usr_payload = {'username': usrname, 'full_name': usrname,
                           'group_create': True, 'password': 'abadpassword'}
            mapping = {data[0]: usrname}
            with create_user(usr_payload) as usrInst:
                with nfs_share(tmp_path, mapping) as share:
                    run_missing_usrgrp_test(testval, tmp_path, share, usrInst)

        elif type == 'MissingGroup':
            # Use a built-in user for the group test
            grpname = data[1]
            testkey, testval = data[0].split('_')

            mapping = {f"{testkey}_user": 'ftp', data[0]: grpname}
            with create_group({'name': grpname}) as grpInst:
                with nfs_share(tmp_path, mapping) as share:
                    run_missing_usrgrp_test(testval, tmp_path, share, grpInst)


@pytest.mark.parametrize('state,expected', [
    (None, 'n'),   # Test default state
    (True, 'y'),
    (False, 'n')
])
def test_52_manage_gids(request, state, expected):
    '''
    The nfsd_manage_gids setting is called "Support > 16 groups" in the webui.
    It is that and, to a greater extent, defines the GIDs that are used for permissions.

    If NOT enabled, then the expectation is that the groups to which the user belongs
    are defined on the _client_ and NOT the server.  It also means groups to which the user
    belongs are passed in on the NFS commands from the client.  The file object GID is
    checked against the passed in list of GIDs.  This is also where the 16 group
    limitation is enforced.  The NFS protocol allows passing up to 16 groups per user.

    If nfsd_manage_gids is enabled, the groups to which the user belong are defined
    on the server.  In this condition, the server confirms the user is a member of
    the file object GID.

    NAS-126067:  Debian changed the 'default' setting to manage_gids in /etc/nfs.conf
    from undefined to "manage_gids = y".

    TEST:   Confirm manage_gids is set in /etc/nfs.conf.d/local/conf for
            both the enable and disable states

    TODO: Add client-side and server-side test from client when available
    '''
    with nfs_config():

        if state is not None:
            sleep(3)  # In Cobia: Prevent restarting NFS too quickly.
            call("nfs.update", {"userd_manage_gids": state})

        s = parse_server_config()
        assert s['mountd']['manage-gids'] == expected, str(s)


def test_54_v4_domain(request):
    '''
    The v4_domain configuration item maps to the 'Domain' setting in
    the [General] section of /etc/idmapd.conf.
    It is described as:
        The local NFSv4 domain name. An NFSv4 domain is a namespace
        with a unique username<->UID and groupname<->GID mapping.
        (Default: Host's fully-qualified DNS domain name)
    '''
    depends(request, ["NFS_SERVICE_STARTED"], scope="session")

    with nfs_config() as nfs_db:
        # By default, v4_domain is not set
        assert nfs_db['v4_domain'] == "", f"Expected zero-len string, but found {nfs_db['v4_domain']}"
        s = parse_server_config("idmapd")
        assert s['General'].get('Domain') is None, f"'Domain' was not expected to be set: {s}"

        # Make a setting change and confirm
        db = call('nfs.update', {"v4_domain": "ixsystems.com"})
        assert db['v4_domain'] == 'ixsystems.com', f"v4_domain failed to be updated in nfs DB: {db}"
        s = parse_server_config("idmapd")
        assert s['General'].get('Domain') == 'ixsystems.com', f"'Domain' failed to be updated in idmapd.conf: {s}"


def test_70_stopping_nfs_service(request):
    # Restore original settings before we stop
    call('nfs.update', NFS_CONFIG.default_nfs_config)
    payload = {"service": "nfs"}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_71_checking_to_see_if_nfs_service_is_stop(request):
    results = GET("/service?service=nfs")
    assert results.json()[0]["state"] == "STOPPED", results.text


def test_72_check_adjusting_threadpool_mode(request):
    """
    Verify that NFS thread pool configuration can be adjusted
    through private API endpoints.

    This request will fail if NFS server (or NFS client) is
    still running.
    """
    for m in ('AUTO', 'PERCPU', 'PERNODE', 'GLOBAL'):
        call('nfs.set_threadpool_mode', m)
        assert call('nfs.get_threadpool_mode') == m


def test_74_disable_nfs_service_at_boot(request):
    results = PUT("/service/id/nfs/", {"enable": False})
    assert results.status_code == 200, results.text


def test_75_checking_nfs_disable_at_boot(request):
    results = GET("/service?service=nfs")
    assert results.json()[0]['enable'] is False, results.text


def test_76_destroying_smb_dataset(request):
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('exports', ['missing', 'empty'])
def test_80_start_nfs_service_with_missing_or_empty_exports(request, exports):
    '''
    NAS-123498: Eliminate conditions on exports for service start
    The goal is to make the NFS server behavior similar to the other protocols
    '''
    if exports == 'empty':
        results = SSH_TEST("echo '' > /etc/exports", user, password)
    else:  # 'missing'
        results = SSH_TEST("rm -f /etc/exports", user, password)
    assert results['result'] is True

    with nfs_config() as nfs_conf:
        # Start NFS
        call('service.start', 'nfs', {'silent': False})
        sleep(1)
        confirm_nfsd_processes(nfs_conf['servers'])

        # Return NFS to stopped condition
        payload = {"service": "nfs"}
        results = POST("/service/stop/", payload)
        assert results.status_code == 200, results.text
        sleep(1)

        # Confirm stopped
        results = GET("/service?service=nfs")
        assert results.json()[0]["state"] == "STOPPED", results.text


@pytest.mark.parametrize('expect_NFS_start', [False, True])
def test_82_files_in_exportsd(request, expect_NFS_start):
    '''
    Any files in /etc/exports.d are potentially dangerous, especially zfs.exports.
    We implemented protections against rogue exports files.
    - We block starting NFS if there are any files in /etc/exports.d
    - We generate an alert when we detect this condition
    - We clear the alert when /etc/exports.d is empty
    '''
    fail_check = {False: 'ConditionDirectoryNotEmpty=!/etc/exports.d', True: None}

    # Simple helper function for this test
    def set_immutable_state(want_immutable=True):
        call('filesystem.set_immutable', want_immutable, '/etc/exports.d')
        assert call('filesystem.is_immutable', '/etc/exports.d') is want_immutable

    try:
        # Setup the test
        set_immutable_state(want_immutable=False)  # Disable immutable

        # Do the 'failing' case first to end with a clean condition
        if not expect_NFS_start:
            results = SSH_TEST("echo 'bogus data' > /etc/exports.d/persistent.file", user, password)
            assert results['result'] is True
            results = SSH_TEST("chattr +i /etc/exports.d/persistent.file", user, password)
            assert results['result'] is True
        else:
            # Restore /etc/exports.d directory to a clean state
            results = SSH_TEST("chattr -i /etc/exports.d/persistent.file", user, password)
            assert results['result'] is True
            results = SSH_TEST("rm -rf /etc/exports.d/*", user, password)
            assert results['result'] is True

        set_immutable_state(want_immutable=True)  # Enable immutable

        set_nfs_service_state('start', expect_NFS_start, fail_check[expect_NFS_start])

    finally:
        # In all cases we want to end with NFS stopped
        set_nfs_service_state('stop')

        # If NFS start is blocked, then an alert should have been raised
        alerts = call('alert.list')
        if not expect_NFS_start:
            # Find alert
            assert any(alert["klass"] == "NFSblockedByExportsDir" for alert in alerts), alerts
        else:  # Alert should have been cleared
            assert not any(alert["klass"] == "NFSblockedByExportsDir" for alert in alerts), alerts
