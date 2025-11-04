import contextlib
import ipaddress
import os
from copy import copy
from time import sleep

import pytest

from middlewared.service_exception import (
    ValidationError, ValidationErrors, InstanceNotFound
)
from middlewared.test.integration.assets.account import group as create_group
from middlewared.test.integration.assets.account import user as create_user
from middlewared.test.integration.assets.filesystem import directory
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, mock, ssh
from middlewared.test.integration.utils.client import truenas_server
from middlewared.test.integration.utils.failover import wait_for_standby
from middlewared.test.integration.utils.system import reset_systemd_svcs as reset_svcs

from auto_config import hostname, password, pool_name, user, ha
from functions import async_SSH_done, async_SSH_start
from protocols import SSH_NFS, nfs_share
from truenas_api_client import ClientException

MOUNTPOINT = f"/tmp/nfs-{hostname}"
dataset = f"{pool_name}/nfs"
dataset_url = dataset.replace('/', '%2F')
NFS_PATH = "/mnt/" + dataset

# Alias
pp = pytest.param

# Supported configuration files
conf_file = {
    "nfs": {
        "pname": "/etc/nfs.conf",
        "sections": {
            'general': {},
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


# =====================================================================
#                     Fixtures and utilities
# =====================================================================

class NFS_CONFIG:
    '''This is used to restore the NFS config to it's original state'''
    initial_nfs_config = {}

    # These are the expected default config values
    default_config = {
        "allow_nonroot": False,
        "protocols": ["NFSV3", "NFSV4"],
        "v4_krb": False,
        "v4_domain": "",
        "bindip": [],
        "mountd_port": None,
        "rpcstatd_port": None,
        "rpclockd_port": None,
        "mountd_log": False,  # nfs.py indicates this should be True, but db says False
        "statd_lockd_log": False,
        "v4_krb_enabled": False,
        "userd_manage_gids": False,
        "keytab_has_nfs_spn": False,
        "managed_nfsd": True,
        "rdma": False,
    }

    initial_service_state = {}

    # These are the expected default run state values
    default_service_state = {
        "service": "nfs",
        "enable": False,
        "state": "STOPPED",
        "pids": []
    }


def parse_exports():
    exp = ssh("cat /etc/exports").splitlines()
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
    All TrueNAS NFS settings are in /etc/nfs.conf
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

        try:
            k, v = line.split(" = ", 1)
        except ValueError as ve:
            raise ValueError(f"Error detected in: {line}") from ve

        rv[section].update({k: v})

    return rv


def parse_db():
    '''
    Convert the NFS config DB to a dictionary
    '''
    raw_db = ssh("sqlite3 /data/freenas-v1.db '.mode line' 'SELECT * FROM services_nfs'")
    cols = [col.strip().replace(" ", "") for col in raw_db.splitlines()]
    dict_db = {item.split('=')[0]: item.split('=')[1] for item in cols}

    return dict_db


def parse_rpcbind_config():
    '''
    In Debian 12 (Bookwork) rpcbind uses /etc/default/rpcbind.
    Look for /etc/rpcbind.conf in future releases.
    '''
    conf = ssh("cat /etc/default/rpcbind").splitlines()
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


def set_nfs_service_state(do_what=None, expect_to_pass=True, fail_check=False):
    """
    Start or Stop NFS service
    expect_to_pass parameter is optional
    fail_check parameter is optional
    """
    assert do_what in ['start', 'stop'], f"Requested invalid service state: {do_what}"
    test_res = {'start': True, 'stop': False}

    retval = None
    if expect_to_pass:
        call('service.control', do_what.upper(), 'nfs', {'silent': False}, job=True)
        sleep(1)
    else:
        with pytest.raises(ClientException) as e:
            call('service.control', do_what.upper(), 'nfs', {'silent': False}, job=True)
        if fail_check:
            assert fail_check in str(e.value)

    # Confirm requested state
    if expect_to_pass:
        retval = call('service.started', 'nfs')
        assert retval == test_res[do_what], f"Expected {test_res[do_what]} for NFS started result, but found {retval}"

    return retval


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


def set_immutable_state(path: str, want_immutable=True):
    '''
    Used by exportsd test
    '''
    call('filesystem.set_zfs_attributes', {
        'path': path,
        'zfs_file_attributes': {'immutable': want_immutable}
    })
    is_immutable = 'IMMUTABLE' in call('filesystem.stat', '/etc/exports.d')['attributes']

    assert is_immutable is want_immutable, f"Expected mutable filesystem: {want_immutable}"


def confirm_nfsd_processes(expected):
    '''
    Confirm the expected number of nfsd processes are running
    '''
    result = ssh("cat /proc/fs/nfsd/threads")
    assert int(result) == expected, result


def confirm_mountd_processes(expected):
    '''
    Confirm the expected number of mountd processes are running
    '''
    rx_mountd = r"rpc\.mountd"
    result = ssh(f"ps -ef | grep '{rx_mountd}' | wc -l")

    # If there is more than one, we subtract one to account for the rpc.mountd thread manager
    num_detected = int(result)
    assert (num_detected - 1 if num_detected > 1 else num_detected) == expected


def confirm_rpc_processes(expected=['idmapd', 'bind', 'statd']):
    '''
    Confirm the expected rpc processes are running
    NB: This only supports the listed names
    '''
    prepend = {'idmapd': 'rpc.', 'bind': 'rpc', 'statd': 'rpc.'}
    for n in expected:
        procname = prepend[n] + n
        assert len(ssh(f"pgrep {procname}").splitlines()) > 0


def confirm_nfs_version(expected=[]):
    '''
    Confirm the expected NFS versions are 'enabled and supported'
    Possible values for expected:
        ["3"] means NFSv3 only
        ["4"] means NFSv4 only
        ["3","4"] means both NFSv3 and NFSv4
    '''
    result = ssh("rpcinfo -s | grep ' nfs '").strip().split()[1]
    for v in expected:
        assert v in result, result


def confirm_rpc_port(rpc_name, port_num):
    '''
    Confirm the expected port for the requested rpc process
    rpc_name = ('mountd', 'status', 'nlockmgr')
    '''
    line = ssh(f"rpcinfo -p | grep {rpc_name} | grep tcp")
    # example:    '100005    3   tcp    618  mountd'
    assert int(line.split()[3]) == port_num, str(line)


def run_missing_usrgrp_mapping_test(data: list[str], usrgrp, tmp_path, share, usrgrpInst):
    ''' Used by test_invalid_user_group_mapping '''
    parsed = parse_exports()
    assert len(parsed) == 2, str(parsed)
    this_share = [entry for entry in parsed if entry['path'] == f'{tmp_path}']
    assert len(this_share) == 1, f"Did not find share {tmp_path}.\nexports = {parsed}"

    # Remove the user/group and restart nfs
    call(f'{usrgrp}.delete', usrgrpInst['id'])
    call('service.control', 'RESTART', 'nfs', job=True)

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
    call('service.control', 'RESTART', 'nfs', job=True)

    # The alert should be cleared
    alerts = call('alert.list')
    this_alert = [entry for entry in alerts if entry['key'] == "NFSexportMappingInvalidNames"]
    assert len(this_alert) == 0, f"Unexpectedly found alert 'NFSexportMappingInvalidNames'.\n{alerts}"

    # Share should have been restored
    parsed = parse_exports()
    assert len(parsed) == 2, str(parsed)
    this_share = [entry for entry in parsed if entry['path'] == f'{tmp_path}']
    assert len(this_share) == 1, f"Did not find share {tmp_path}.\nexports = {parsed}"


@contextlib.contextmanager
def manage_start_nfs():
    """ The exit state is managed by init_nfs """
    try:
        yield set_nfs_service_state('start')
    finally:
        set_nfs_service_state('stop')


def move_systemdataset(new_pool_name):
    ''' Move the system dataset to the requested pool '''
    try:
        call('systemdataset.update', {'pool': new_pool_name}, job=True)
    except Exception as e:
        raise e
    else:
        if ha:
            wait_for_standby()

    return call('systemdataset.config')


@contextlib.contextmanager
def system_dataset(new_pool_name):
    '''
    Temporarily move the system dataset to the new_pool_name
    '''
    orig_sysds = call('systemdataset.config')
    try:
        sysds = move_systemdataset(new_pool_name)
        yield sysds
    finally:
        move_systemdataset(orig_sysds['pool'])


@contextlib.contextmanager
def nfs_dataset(name, options=None, acl=None, mode=None, pool=None):
    """
    NOTE: This is _nearly_ the same as the 'dataset' test asset. The difference
          is the retry loop.
    TODO: Enhance the 'dataset' test asset to include a retry loop
    """
    assert "/" not in name
    _pool_name = pool if pool else pool_name

    _dataset = f"{_pool_name}/{name}"

    try:
        call("pool.dataset.create", {"name": _dataset, **(options or {})})

        if acl is None:
            call("filesystem.setperm", {'path': f"/mnt/{_dataset}", "mode": mode or "777"}, job=True)
        else:
            call("filesystem.setacl", {'path': f"/mnt/{_dataset}", "dacl": acl}, job=True)

        yield _dataset

    finally:
        # dataset may be busy
        sleep(2)
        for _ in range(6):
            try:
                call("pool.dataset.delete", _dataset)
                # Success
                break
            except InstanceNotFound:
                # Also success
                break
            except Exception:
                # Cannot yet delete
                sleep(10)


@contextlib.contextmanager
def nfs_db():
    ''' Use this to monkey with the db '''
    try:
        restore_db = parse_db()
        yield restore_db
    finally:
        # Restore any changed settings
        cur_db = parse_db()
        for key in restore_db:
            if cur_db[key] != restore_db[key]:
                ssh(f"sqlite3 /data/freenas-v1.db 'UPDATE services_nfs set {key}={restore_db[key]}'")


@contextlib.contextmanager
def nfs_config():
    ''' Use this to restore NFS settings '''
    try:
        nfs_db_conf = call("nfs.config")
        excl = ['id', 'v4_krb_enabled', 'keytab_has_nfs_spn', 'managed_nfsd']
        [nfs_db_conf.pop(key) for key in excl]
        yield copy(nfs_db_conf)
    finally:
        call("nfs.update", nfs_db_conf)


@contextlib.contextmanager
def nfs_share_config(nfsid: int):
    ''' Use this to restore NFS share settings '''
    try:
        configs = call("sharing.nfs.query", [["id", "=", nfsid]])
        assert configs != []
        share_config = configs[0]
        yield copy(share_config)
    finally:
        excl = ['id', 'path', 'locked']
        [share_config.pop(key) for key in excl]
        call("sharing.nfs.update", nfsid, share_config)


@pytest.fixture(scope="module")
def init_nfs():
    """ Will restore to _default_ config and state at module exit """
    try:
        initial_config = call("nfs.config")
        NFS_CONFIG.initial_nfs_config = copy(initial_config)

        initial_service_state = call('service.query', [['service', '=', 'nfs']], {'get': True})
        NFS_CONFIG.initial_service_state = copy(initial_service_state)

        yield {"config": initial_config, "service_state": initial_service_state}
    finally:
        # Restore to -default- state  (some might be redundant, but ensures clean state at exit)
        call('service.update', 'nfs', {'enable': NFS_CONFIG.default_service_state['enable']})
        state_cmd = {'RUNNING': 'start', 'STOPPED': 'stop'}
        set_nfs_service_state(state_cmd[NFS_CONFIG.default_service_state['state']])

        # Restore to -default- config
        exclude = ['servers', 'v4_krb_enabled', 'keytab_has_nfs_spn', 'managed_nfsd']
        default_config_payload = {k: v for k, v in NFS_CONFIG.default_config.items() if k not in exclude}
        if NFS_CONFIG.default_config['managed_nfsd']:
            default_config_payload['servers'] = None
        call('nfs.update', default_config_payload)


@pytest.fixture(scope="module")
def nfs_dataset_and_share():
    """ Will delete the 'nfs' share and dataset at the module exit """
    with nfs_dataset('nfs') as ds:
        with nfs_share(NFS_PATH, {
                "comment": "My Test Share",
                "security": ["SYS"]
        }) as nfsid:
            yield {"nfsid": nfsid, "ds": ds}


@pytest.fixture(scope="class")
def start_nfs():
    """ The exit state is managed by init_nfs """
    try:
        yield set_nfs_service_state('start')
    finally:
        set_nfs_service_state('stop')


# =====================================================================
#                           Tests
# =====================================================================

def test_config(init_nfs):
    initial_config = init_nfs['config']
    initial_service_state = init_nfs['service_state']

    # We should be starting with the default config
    # Check the hard way so that we can identify the culprit
    for k, v in NFS_CONFIG.default_config.items():
        assert initial_config.get(k) == v, f'Expected {k}:"{v}", but found {k}:"{initial_config.get(k)}"'

    # Confirm NFS is not running
    assert initial_service_state['state'] == 'STOPPED', \
        f"Before update, expected STOPPED, but found {initial_service_state['state']}"


def test_service_enable_at_boot(init_nfs):
    initial_run_state = init_nfs['service_state']
    assert initial_run_state['enable'] is False

    svc_id = call('service.update', 'nfs', {"enable": True})
    nfs_state = call('service.query', [["id", "=", svc_id]])
    assert nfs_state[0]['service'] == "nfs"
    assert nfs_state[0]['enable'] is True


def test_dataset_permissions(nfs_dataset_and_share):
    ds = nfs_dataset_and_share["ds"]
    call('filesystem.setperm', {
        'path': os.path.join('/mnt', ds),
        'mode': '777',
        'uid': 0,
        'gid': 0,
    }, job=True)


class TestNFSops:
    """
    Test NFS operations: server running
    """
    def test_state_directory(self, start_nfs):
        """
        By default, the NFS state directory is at /var/lib/nfs.
        To support HA systems, we moved this to the system dataset
        at /var/db/system/nfs.  In support of this we updated the
        NFS conf file settings
        """
        assert start_nfs is True

        # Make sure the conf file has the expected settings
        sysds_path = call('systemdataset.sysdataset_path')
        assert sysds_path == '/var/db/system'
        nfs_state_dir = os.path.join(sysds_path, 'nfs')
        s = parse_server_config()
        assert s['exportd']['state-directory-path'] == nfs_state_dir, str(s)
        assert s['nfsdcld']['storagedir'] == os.path.join(nfs_state_dir, 'nfsdcld'), str(s)
        assert s['nfsdcltrack']['storagedir'] == os.path.join(nfs_state_dir, 'nfsdcltrack'), str(s)
        assert s['nfsdcld']['storagedir'] == os.path.join(nfs_state_dir, 'nfsdcld'), str(s)
        assert s['mountd']['state-directory-path'] == nfs_state_dir, str(s)
        assert s['statd']['state-directory-path'] == nfs_state_dir, str(s)

        # Confirm we have the mount point in the system dataset
        sysds = call('systemdataset.config')
        bootds = call('systemdataset.get_system_dataset_spec', sysds['pool'], sysds['uuid'])
        bootds_nfs = list([d for d in bootds if 'nfs' in d.get('name')])[0]
        assert bootds_nfs['name'] == sysds['pool'] + "/.system/nfs"

        # Confirm the required entries are present
        required_nfs_entries = {"nfsdcld", "nfsdcltrack", "sm", "sm.bak", "state", "v4recovery"}
        current_nfs_entries = set(list(ssh(f'ls {nfs_state_dir}').splitlines()))
        assert required_nfs_entries.issubset(current_nfs_entries)

        # Confirm proc entry reports expected value after nfs restart
        call('service.control', 'RESTART', 'nfs', job=True)
        sleep(1)
        recovery_dir = ssh('cat /proc/fs/nfsd/nfsv4recoverydir').strip()
        assert recovery_dir == os.path.join(nfs_state_dir, 'v4recovery'), \
            f"Expected {nfs_state_dir + '/v4recovery'} but found {recovery_dir}"
        # ----------------------------------------------------------------------
        # NOTE: Test fresh-install and upgrade.
        # ----------------------------------------------------------------------

    @pytest.mark.parametrize('vers', [3, 4])
    def test_basic_nfs_ops(self, start_nfs, nfs_dataset_and_share, vers):
        assert start_nfs is True
        assert nfs_dataset_and_share['nfsid'] is not None

        with SSH_NFS(truenas_server.ip, NFS_PATH, vers=vers, user=user,
                     password=password, ip=truenas_server.ip) as n:
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

    def test_nfs_scope_setting(self, start_nfs, nfs_dataset_and_share):
        """
        Test NFS share with scope configuration
        Confirm the scope setting is correctd.
        Capture the network transaction on a mount
        confirm the expected scope value is in the EXCHANGE_ID
        TODO: Add HA failover test
        """
        assert start_nfs is True
        assert nfs_dataset_and_share['nfsid'] is not None
        hostip = truenas_server.ip
        outs = ""
        errs = ""
        expected_scope_value = call('system.global.id')

        # Confirm /etc/nfs.conf
        conf = parse_server_config()
        assert conf['nfsd']['scope'] == expected_scope_value

        # Confirm NFS reports the expected scope value
        p = async_SSH_start("tcpdump -A -v -t -i lo -s 1514 port nfs -c12", user, password, hostip)
        # Give some time so that the tcpdump has started before we proceed
        sleep(2)
        with SSH_NFS(hostip, NFS_PATH, vers=4, user=user, password=password, ip=hostip):
            # Wait a couple seconds then collect
            outs, errs = async_SSH_done(p, 2)

        # Process the results
        output = outs.strip()
        assert len(output), f"No output from tcpdump:'{outs}', errs: {errs}"
        lines = output.split("\n")
        assert len(lines) > 12, f"Unexpected number of lines output by tcpdump: {outs}, errs: {errs}"
        assert expected_scope_value in output, {errs}

    def test_server_side_copy(self, start_nfs, nfs_dataset_and_share):
        assert start_nfs is True
        assert nfs_dataset_and_share['nfsid'] is not None
        with SSH_NFS(truenas_server.ip, NFS_PATH, vers=4, user=user,
                     password=password, ip=truenas_server.ip) as n:
            n.server_side_copy('ssc1', 'ssc2')

    @pytest.mark.parametrize('nfsd,cores,expected', [
        pp(50, 1, {'nfsd': 50, 'mountd': 12, 'managed': False}, id="User set 50: expect 12 mountd"),
        pp(None, 12, {'nfsd': 12, 'mountd': 3, 'managed': True}, id="12 cores: expect 12 nfsd, 3 mountd"),
        pp(None, 4, {'nfsd': 4, 'mountd': 1, 'managed': True}, id="4 cores: expect 4 nfsd, 1 mountd"),
        pp(None, 2, {'nfsd': 2, 'mountd': 1, 'managed': True}, id="2 cores: expect 2 nfsd, 1 mountd"),
        pp(None, 1, {'nfsd': 1, 'mountd': 1, 'managed': True}, id="1 core: expect 1 nfsd, 1 mountd"),
        pp(0, 4, {'nfsd': 4, 'mountd': 1, 'managed': True}, id="User set 0: invalid"),
        pp(257, 4, {'nfsd': 4, 'mountd': 1, 'managed': True}, id="User set 257: invalid"),
        pp(None, 48, {'nfsd': 32, 'mountd': 8, 'managed': True}, id="48 cores: expect 32 nfsd (max), 8 mountd"),
        pp(-1, 48, {'nfsd': 32, 'mountd': 8, 'managed': True}, id="Reset to 'managed_nfsd'"),
    ])
    def test_service_update(self, start_nfs, nfsd, cores, expected):
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
        assert start_nfs is True

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
                        assert call("nfs.config")['managed_nfsd'] == expected['managed']
                else:
                    with pytest.raises(ValidationErrors, match="Input should be"):
                        assert call("nfs.config")['managed_nfsd'] == expected['managed']
                        call("nfs.update", {"servers": nfsd})

    def test_share_update(self, start_nfs, nfs_dataset_and_share):
        """
        Test changing the security and enabled fields
        We want nfs running to allow confirmation of changes in exportfs
        """
        assert start_nfs is True
        assert nfs_dataset_and_share['nfsid'] is not None
        nfsid = nfs_dataset_and_share['nfsid']
        with nfs_share_config(nfsid) as share_data:
            assert share_data['security'] != []
            nfs_share = call('sharing.nfs.update', nfsid, {"security": [], "comment": "no comment"})

            # The default is 'SYS', so changing from ['SYS'] to [] does not change /etc/exports
            assert nfs_share['security'] == [], f"Expected [], but found {nfs_share[0]['security']}"
            assert nfs_share['comment'] == "no comment"

            # Confirm changes are reflected in /etc/exports
            parsed = parse_exports()
            assert len(parsed) == 1, str(parsed)
            export_opts = parsed[0]['opts'][0]['parameters']
            assert "sec=sys" in export_opts

            # Test share disable
            assert share_data['enabled'] is True
            nfs_share = call('sharing.nfs.update', nfsid, {"enabled": False})
            assert parse_exports() == []

    @pytest.mark.parametrize(
        "networklist,ExpectedToPass,FailureMsg", [
            # IPv4
            pp(["192.168.0.0/24", "192.168.1.0/24"], True, "", id="IPv4 - non-overlap"),
            pp(["192.168.0.0/16", "192.168.1.0/24"], False, "Overlapped", id="IPv4 - overlap wide"),
            pp(["192.168.0.0/24", "192.168.0.211/32"], False, "Overlapped", id="IPv4 - overlap narrow"),
            pp(["192.168.0.0/64"], False, "do not appear to be valid IPv4 or IPv6", id="IPv4 - invalid range"),
            pp(["bogus_network"], False, "do not appear to be valid IPv4 or IPv6", id="IPv4 - invalid format"),
            pp(["192.168.27.211"], True, "", id="IPv4 - auto-convert to CIDR"),
            pp(["0.0.0.0/0"], False, "No entry is required", id="IPv4 - all-hosts (0.0.0.0/0)"),
            pp(["0.0.0.0/24"], False, "No entry is required", id="IPv4 - all-hosts (0.0.0.0/24)"),
            pp(["192.168.0.0/24", "0.0.0.0/0"], False, "No entry is required", id="IPv4 - overlap with all-hosts"),
            # IPv6
            pp(["2001:0db8:85a3:0000:0000:8a2e::/96", "2001:0db8:85a3:0000:0000:8a2f::/96"],
               True, "", id="IPv6 - non-overlap"),
            pp(["2001:0db8:85a3:0000:0000:8a2e::/96", "2001:0db8:85a3:0000:0000:8a00::/88"],
               False, "Overlapped", id="IPv6 - overlap wide"),
            pp(["2001:0db8:85a3:0000:0000:8a2e::/96", "2001:0db8:85a3:0000:0000:8a2e:0370:7334/128"],
               False, "Overlapped", id="IPv6 - overlap narrow"),
            pp(["2001:0db8:85a3:0000:0000:8a2e:0370:7334/256"],
               False, "do not appear to be valid IPv4 or IPv6", id="IPv6 - invalid range"),
            pp(["2001:0db8:85a3:0000:0000:8a2e:0370:7334"],
               True, "", id="IPv6 - auto-convert to CIDR"),
            pp(["::/0"], False, "No entry is required", id="IPv6 - all-networks (::/0)"),
            pp(["::/48"], False, "No entry is required", id="IPv6 - all-networks (::/48)"),
            pp(["192.168.0.0/24", "::/0"], False, "No entry is required", id="IPv6 - overlap with all-networks"),
        ],
    )
    def test_share_networks(
            self, start_nfs, nfs_dataset_and_share, networklist, ExpectedToPass, FailureMsg):
        """
        Verify that adding a network generates an appropriate line in exports
        file for same path. Sample:

        "/mnt/dozer/nfs"\
            192.168.0.0/24(sec=sys,rw,subtree_check)\
            192.168.1.0/24(sec=sys,rw,subtree_check)
        """
        assert start_nfs is True
        assert nfs_dataset_and_share['nfsid'] is not None
        nfsid = nfs_dataset_and_share['nfsid']

        with nfs_share_config(nfsid):
            if ExpectedToPass:
                call('sharing.nfs.update', nfsid, {'networks': networklist})
            else:
                with pytest.raises((ValueError, ValidationErrors)) as ve:
                    call('sharing.nfs.update', nfsid, {'networks': networklist})
                if ve.typename == "ValueError":
                    assert FailureMsg in str(ve.value)
                else:
                    assert FailureMsg in str(ve.value.errors[0])

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
                # The entry should NOT be present
                assert len(exports_networks) == 1, str(parsed)

    @pytest.mark.parametrize(
        "hostlist,ExpectedToPass,FailureMsg", [
            pp(["192.168.0.69", "192.168.0.70", "@fakenetgroup"],
               True, "", id="Valid - IPv4 address, netgroup"),
            pp(["asdfnm-*", "?-asdfnm-*", "asdfnm[0-9]", "nmix?-*dev[0-9]"],
               True, "", id="Valid - wildcard names,ranges"),
            pp(["asdfdm-*.example.com", "?-asdfdm-*.ixsystems.com",
                "asdfdm[0-9].example.com", "dmix?-*dev[0-9].ixsystems.com"],
               True, "", id="Valid - wildcard domains,ranges"),
            pp(["-asdffail", "*.asdffail.com", "*.*.com", "bozofail.?.*"],
               False, "Unable to resolve", id="Invalid - names,domains (not resolvable)"),
            pp(["bogus/name"], False, "Unable to resolve", id="Invalid - name (path)"),
            pp(["192.168.1.0/24"], False, "Unable to resolve", id="Invalid - name (network format)"),
            pp(["0.0.0.0"], False, "No entry is required", id="Invalid - IPv4 everybody as 0.0.0.0"),
            pp(["asdfdm[0-9].example.com", "-asdffail", "devteam-*.ixsystems.com", "*.asdffail.com"],
               False, "Unable to resolve", id="Mix - valid and invalid names"),
            pp(["192.168.1.0", "192.168.1.0"], False, "Entries must be unique", id="Invalid - duplicate address"),
            pp(["ixsystems.com", "ixsystems.com"], False, "Entries must be unique", id="Invalid - duplicate address"),
            pp(["ixsystems.com", "*"], True, "", id="Valid - mix name and everybody"),
            pp(["*", "*.ixsystems.com"], True, "", id="Valid - mix everybody and wildcard name"),
            pp(["192.168.1.o"], False, "Unable to resolve", id="Invalid - character in address"),
            pp(["bad host"], False, "Cannot contain spaces", id="Invalid - name with spaces"),
            pp(["2001:0db8:85a3:0000:0000:8a2e:0370:7334"], True, "", id="Valid - IPv6 address"),
            pp(["::"], False, "No entry is required", id="Invalid - IPv6 everybody as ::"),
        ],
    )
    def test_share_hosts(
            self, start_nfs, nfs_dataset_and_share, hostlist, ExpectedToPass, FailureMsg):
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
        assert start_nfs is True
        assert nfs_dataset_and_share['nfsid'] is not None
        nfsid = nfs_dataset_and_share['nfsid']

        with nfs_share_config(nfsid):
            if ExpectedToPass:
                call('sharing.nfs.update', nfsid, {'hosts': hostlist})
            else:
                with pytest.raises((ValueError, ValidationErrors)) as ve:
                    call('sharing.nfs.update', nfsid, {'hosts': hostlist})
                if ve.typename == "ValueError":
                    assert FailureMsg in str(ve.value)
                else:
                    assert FailureMsg in str(ve.value.errors[0])

            parsed = parse_exports()
            assert len(parsed) == 1, str(parsed)

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

    def test_share_ro(self, start_nfs, nfs_dataset_and_share):
        """
        Verify that toggling `ro` will cause appropriate change in
        exports file. We also verify with write tests on a local mount.
        """
        assert start_nfs is True
        assert nfs_dataset_and_share['nfsid'] is not None
        nfsid = nfs_dataset_and_share['nfsid']

        with nfs_share_config(nfsid) as share_data:
            # Confirm 'rw' initial state and create a file and dir
            assert share_data['ro'] is False
            parsed = parse_exports()
            assert len(parsed) == 1, str(parsed)
            assert "rw" in parsed[0]['opts'][0]['parameters'], str(parsed)

            # Mount the share locally and create a file and dir
            with SSH_NFS(truenas_server.ip, NFS_PATH,
                         user=user, password=password, ip=truenas_server.ip) as n:
                n.create("testfile_should_pass")
                n.mkdir("testdir_should_pass")

            # Change to 'ro'
            call('sharing.nfs.update', nfsid, {'ro': True})

            # Confirm 'ro' state and behavior
            parsed = parse_exports()
            assert len(parsed) == 1, str(parsed)
            assert "rw" not in parsed[0]['opts'][0]['parameters'], str(parsed)

            # Attempt create and delete
            with SSH_NFS(truenas_server.ip, NFS_PATH,
                         user=user, password=password, ip=truenas_server.ip) as n:
                with pytest.raises(RuntimeError) as re:
                    n.create("testfile_should_fail")
                    assert False, "Should not have been able to create a new file"
                assert 'cannot touch' in str(re), re

                with pytest.raises(RuntimeError) as re:
                    n.mkdir("testdir_should_fail")
                    assert False, "Should not have been able to create a new directory"
                assert 'cannot create directory' in str(re), re

    def test_share_maproot(self, start_nfs, nfs_dataset_and_share):
        """
        root squash is always enabled, and so maproot accomplished through
        anonuid and anongid

        Sample:
        "/mnt/dozer/NFSV4"\
            *(sec=sys,rw,anonuid=65534,anongid=65534,subtree_check)
        """
        assert start_nfs is True
        assert nfs_dataset_and_share['nfsid'] is not None
        nfsid = nfs_dataset_and_share['nfsid']

        with nfs_share_config(nfsid) as share_data:
            # Confirm we won't compete against mapall
            assert share_data['mapall_user'] is None
            assert share_data['mapall_group'] is None

            # Map root to everybody
            call('sharing.nfs.update', nfsid, {
                'maproot_user': 'nobody',
                'maproot_group': 'nogroup'
            })

            parsed = parse_exports()
            assert len(parsed) == 1, str(parsed)

            params = parsed[0]['opts'][0]['parameters']
            assert 'anonuid=65534' in params, str(parsed)
            assert 'anongid=65534' in params, str(parsed)
            # TODO: Run test as nobody, expect success

            # Setting maproot_user and maproot_group to root should
            # cause us to append "no_root_squash" to options.
            call('sharing.nfs.update', nfsid, {
                'maproot_user': 'root',
                'maproot_group': 'root'
            })

            parsed = parse_exports()
            assert len(parsed) == 1, str(parsed)
            params = parsed[0]['opts'][0]['parameters']
            assert 'no_root_squash' in params, str(parsed)
            assert not any(filter(lambda x: x.startswith('anon'), params)), str(parsed)
            # TODO: Run test as nobody, expect failure

            # Second share should have normal (no maproot) params.
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

        # After share config restore, confirm expected settings
        parsed = parse_exports()
        assert len(parsed) == 1, str(parsed)
        params = parsed[0]['opts'][0]['parameters']

        assert not any(filter(lambda x: x.startswith('anon'), params)), str(parsed)

    def test_share_mapall(self, start_nfs, nfs_dataset_and_share):
        """
        mapall is accomplished through anonuid and anongid and
        setting 'all_squash'.

        Sample:
        "/mnt/dozer/NFSV4"\
            *(sec=sys,rw,all_squash,anonuid=65534,anongid=65534,subtree_check)
        """
        assert start_nfs is True
        assert nfs_dataset_and_share['nfsid'] is not None
        nfsid = nfs_dataset_and_share['nfsid']

        with nfs_share_config(nfsid) as share_data:
            # Confirm we won't compete against maproot
            assert share_data['maproot_user'] is None
            assert share_data['maproot_group'] is None

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

        # After share config restore, confirm settings
        parsed = parse_exports()
        assert len(parsed) == 1, str(parsed)
        params = parsed[0]['opts'][0]['parameters']

        assert not any(filter(lambda x: x.startswith('anon'), params)), str(parsed)
        assert 'all_squash' not in params, str(parsed)

    def test_subtree_behavior(self, start_nfs, nfs_dataset_and_share):
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
        assert start_nfs is True
        assert nfs_dataset_and_share['nfsid'] is not None

        with directory(f'{NFS_PATH}/sub1') as tmp_path:
            with nfs_share(tmp_path, {'hosts': ['127.0.0.1']}):
                parsed = parse_exports()
                assert len(parsed) == 2, str(parsed)

                assert parsed[0]['path'] == NFS_PATH, str(parsed)
                assert 'no_subtree_check' in parsed[0]['opts'][0]['parameters'], str(parsed)

                assert parsed[1]['path'] == tmp_path, str(parsed)
                assert 'subtree_check' in parsed[1]['opts'][0]['parameters'], str(parsed)

    def test_nonroot_behavior(self, start_nfs, nfs_dataset_and_share):
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
        assert start_nfs is True
        assert nfs_dataset_and_share['nfsid'] is not None

        # Verify that NFS server configuration is as expected
        with nfs_config() as nfs_conf_orig:

            # --- Test: allow_nonroot is False ---
            assert nfs_conf_orig['allow_nonroot'] is False, nfs_conf_orig

            # Confirm setting in /etc/exports
            parsed = parse_exports()
            assert len(parsed) == 1, str(parsed)
            assert 'insecure' not in parsed[0]['opts'][0]['parameters'], str(parsed)

            # Confirm we allow mounts from 'root' ports
            with SSH_NFS(truenas_server.ip, NFS_PATH, vers=4,
                         user=user, password=password, ip=truenas_server.ip):
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

            # --- Test: allow_nonroot is True ---
            new_nfs_conf = call('nfs.update', {"allow_nonroot": True})
            assert new_nfs_conf['allow_nonroot'] is True, new_nfs_conf

            parsed = parse_exports()
            assert len(parsed) == 1, str(parsed)
            assert 'insecure' in parsed[0]['opts'][0]['parameters'], str(parsed)

            # Confirm we allow mounts from 'root' ports
            with SSH_NFS(truenas_server.ip, NFS_PATH, vers=4,
                         user=user, password=password, ip=truenas_server.ip):
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

    def test_logging_filters(self, start_nfs, nfs_dataset_and_share):
        """
        This test checks the function of the mountd_log setting to filter
        rpc.mountd messages that have priority DEBUG to NOTICE.
        We perform loopback mounts on the TrueNAS server and
        then check the syslog and daemon.log for rpc.mountd messages.
        The mountd filter is applied to syslog and daemon.log.
        """
        assert start_nfs is True
        assert nfs_dataset_and_share['nfsid'] is not None

        with nfs_config():
            # Create several rpc.mountd daemons
            call("nfs.update", {"servers": 24})

            # Enable rpc.mountd logging
            call("nfs.update", {"mountd_log": True})

            # Run test:  rpc.mountd messages should not be present
            syslog_tail = async_SSH_start("tail -n 0 -F /var/log/syslog", user, password, truenas_server.ip)
            daemon_tail = async_SSH_start("tail -n 0 -F /var/log/daemon.log", user, password, truenas_server.ip)
            # This will log to both syslog and daemon.log
            ssh('logger -p daemon.notice "====== START_NFS_LOGGING_FILTER_TEST - expect dmount messages ======"')

            with SSH_NFS(truenas_server.ip, NFS_PATH, vers=4,
                         user=user, password=password, ip=truenas_server.ip) as n:
                n.ls('/')

            ssh('logger -p daemon.notice "====== END_NFS_SYSLOG_FILTER_TEST - expect mount messages ======"')
            syslog_data, errs = async_SSH_done(syslog_tail, 5)    # 5 second timeout
            daemon_data, errs = async_SSH_done(daemon_tail, 5)    # 5 second timeout

            assert 'rpc.mountd' in syslog_data, \
                f"Unexpectedly did not find rpc.mountd messages in syslog:\n{syslog_data}"
            assert 'rpc.mountd' in daemon_data, \
                f"Unexpectedly did not find rpc.mountd messages in daemon.log:\n{daemon_data}"

            # Disable rpc.mountd logging
            call("nfs.update", {"mountd_log": False})

            # Run test: rpc.mountd messages should be present
            syslog_tail = async_SSH_start("tail -n 0 -F /var/log/syslog", user, password, truenas_server.ip)
            daemon_tail = async_SSH_start("tail -n 0 -F /var/log/daemon.log", user, password, truenas_server.ip)
            ssh('logger -p daemon.notice "====== START_NFS_LOGGING_FILTER_TEST - no mountd messages ======"')

            with SSH_NFS(truenas_server.ip, NFS_PATH, vers=4,
                         user=user, password=password, ip=truenas_server.ip) as n:
                n.ls('/')

            ssh('logger -p daemon.notice "====== END_NFS_SYSLOG_FILTER_TEST - no mountd messages ======"')
            syslog_data, errs = async_SSH_done(syslog_tail, 5)    # 5 second timeout
            daemon_data, errs = async_SSH_done(daemon_tail, 5)    # 5 second timeout

            assert 'rpc.mountd' not in syslog_data, \
                f"Unexpectedly found rcp.mountd messages in syslog:\n{syslog_data}"
            assert 'rpc.mountd' not in daemon_data, \
                f"Unexpectedly found rcp.mountd messages in daemon.log:\n{daemon_data}"

    def test_client_status(self, start_nfs, nfs_dataset_and_share):
        """
        This test checks the function of API endpoints to list NFSv3 and
        NFSv4 clients by performing loopback mounts on the remote TrueNAS
        server and then checking client counts. Due to inherent imprecision
        of counts over NFSv3 protcol (specifically with regard to decrementing
        sessions) we only verify that count is non-zero for NFSv3.
        """
        assert start_nfs is True
        assert nfs_dataset_and_share['nfsid'] is not None

        with SSH_NFS(truenas_server.ip, NFS_PATH, vers=3,
                     user=user, password=password, ip=truenas_server.ip):
            res = call('nfs.get_nfs3_clients', [], {'count': True})
            assert int(res) != 0

        with SSH_NFS(truenas_server.ip, NFS_PATH, vers=4,
                     user=user, password=password, ip=truenas_server.ip):
            res = call('nfs.get_nfs4_clients')
            assert len(res) == 1, f"Expected to find 1, but found {len(res)}"

        # # Enable this when CI environment supports IPv6
        # # NAS-130437: Confirm IPv6 support
        # try:
        #     # Get the IPv6 equivalent of truenas_server.ip
        #     ip_info = call(
        #         'interface.query',
        #         [["aliases.*.address", "=", truenas_server.ip]], {"get": True}
        #     )
        #     devname = ip_info['name']
        #     aliases = ip_info['state']['aliases']

        #     ipv6_addr = list(filter(lambda x: x['type'] == 'INET6', aliases))[0]['address']

        #     ipv6_mp = '/mnt/nfs_ipv6'
        #     ssh(f"mkdir -p {ipv6_mp}")

        #     # zsh requires the 'server' part to be encapsulated in quotes due to square brackets
        #     ssh(f'mount "[{ipv6_addr}%{devname}]":{NFS_PATH} {ipv6_mp}')

        #     # Confirm we can process get_nfs4_clients that use IPv6 addresses
        #     nfs4_client_list = call("nfs.get_nfs4_clients")
        #     assert len(nfs4_client_list) == 1
        #     assert ipv6_addr in nfs4_client_list[0]['info']['callback address']

        # finally:
        #     ssh(f"umount -f {ipv6_mp}")
        #     ssh(f"rmdir {ipv6_mp}")

    @pytest.mark.parametrize('type,data', [
        pp('InvalidAssignment', [
            {'maproot_user': 'baduser'}, 'maproot_user', 'User not found: baduser'
        ], id="invalid maproot user"),
        pp('InvalidAssignment', [
            {'maproot_group': 'badgroup'}, 'maproot_user', 'This field is required when map group is specified'
        ], id="invalid maproot group"),
        pp('InvalidAssignment', [
            {'mapall_user': 'baduser'}, 'mapall_user', 'User not found: baduser'
        ], id="invalid mapall user"),
        pp('InvalidAssignment', [
            {'mapall_group': 'badgroup'}, 'mapall_user', 'This field is required when map group is specified'
        ], id="invalid mapall group"),
        pp('MissingUser', ['maproot_user', 'missinguser'], id="missing maproot user"),
        pp('MissingUser', ['mapall_user', 'missinguser'], id="missing mapall user"),
        pp('MissingGroup', ['maproot_group', 'missingroup'], id="missing maproot group"),
        pp('MissingGroup', ['mapall_group', 'missingroup'], id="missing mapall group"),
    ])
    def test_invalid_user_group_mapping(self, start_nfs, nfs_dataset_and_share, type, data):
        '''
        Verify we properly trap and handle invalid user and group mapping
        Two conditions:
            1) Catch invalid assignments
            2) Catch invalid settings at NFS start
        '''
        assert start_nfs is True
        assert nfs_dataset_and_share['nfsid'] is not None

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
                        run_missing_usrgrp_mapping_test(data, testval, tmp_path, share, usrInst)

            elif type == 'MissingGroup':
                # Use a built-in user for the group test
                grpname = data[1]
                testkey, testval = data[0].split('_')

                mapping = {f"{testkey}_user": 'ftp', data[0]: grpname}
                with create_group({'name': grpname}) as grpInst:
                    with nfs_share(tmp_path, mapping) as share:
                        run_missing_usrgrp_mapping_test(data, testval, tmp_path, share, grpInst)

    def test_service_protocols(self, start_nfs):
        """
        This test verifies that changing the `protocols` option generates expected
        changes in nfs kernel server config.  In most cases we will also confirm
        the settings have taken effect.

        For the time being this test will also exercise the deprecated `v4` option
        to the same effect, but this will later be removed.

        NFS must be enabled for this test to succeed as while the config (i.e.
        database) will be updated regardless, the server config file will not
        be updated.
        TODO: Add client side tests
        """
        assert start_nfs is True

        # Multiple restarts cause systemd failures.  Reset the systemd counters.
        reset_svcs("nfs-idmapd nfs-mountd nfs-server rpcbind rpc-statd")

        with nfs_config() as nfs_conf_orig:
            # Check existing config (both NFSv3 & NFSv4 configured)
            assert "NFSV3" in nfs_conf_orig['protocols'], nfs_conf_orig
            assert "NFSV4" in nfs_conf_orig['protocols'], nfs_conf_orig
            s = parse_server_config()
            assert s['nfsd']["vers3"] == 'y', str(s)
            assert s['nfsd']["vers4"] == 'y', str(s)
            confirm_nfs_version(['3', '4'])

            # Turn off NFSv4 (v3 on)
            new_config = call('nfs.update', {"protocols": ["NFSV3"]})
            assert "NFSV3" in new_config['protocols'], new_config
            assert "NFSV4" not in new_config['protocols'], new_config
            s = parse_server_config()
            assert s['nfsd']["vers3"] == 'y', str(s)
            assert s['nfsd']["vers4"] == 'n', str(s)

            # Confirm setting has taken effect: v4->off, v3->on
            confirm_nfs_version(['3'])

            # Confirm we trap invalid setting
            with pytest.raises(ValidationError) as ve:
                call("nfs.update", {"protocols": []})
            assert "nfs_update.protocols" == ve.value.attribute
            assert "at least one" in str(ve.value)

            # Turn off NFSv3 (v4 on)
            new_config = call('nfs.update', {"protocols": ["NFSV4"]})
            assert "NFSV3" not in new_config['protocols'], new_config
            assert "NFSV4" in new_config['protocols'], new_config
            s = parse_server_config()
            assert s['nfsd']["vers3"] == 'n', str(s)
            assert s['nfsd']["vers4"] == 'y', str(s)

            # Confirm setting has taken effect: v4->on, v3->off
            confirm_nfs_version(['4'])

        # Finally, confirm both are re-enabled
        nfs_conf = call('nfs.config')
        assert "NFSV3" in nfs_conf['protocols'], nfs_conf
        assert "NFSV4" in nfs_conf['protocols'], nfs_conf
        s = parse_server_config()
        assert s['nfsd']["vers3"] == 'y', str(s)
        assert s['nfsd']["vers4"] == 'y', str(s)

        # Confirm setting has taken effect: v4->on, v3->on
        confirm_nfs_version(['3', '4'])

    def test_service_udp(self, start_nfs):
        """
        This test verifies the udp config is NOT in the DB and
        that it is NOT in the etc file.
        """
        assert start_nfs is True

        # The 'udp' setting should have been removed
        nfs_conf = call('nfs.config')
        assert nfs_conf.get('udp') is None, nfs_conf

        s = parse_server_config()
        assert s.get('nfsd', {}).get('udp') is None, s

    @pytest.mark.parametrize('test_port', [
        pp(
            [
                ["mountd", 618, None],
                ["rpcstatd", 871, None],
                ["rpclockd", 32803, None]
            ], id="valid ports"
        ),
        pp(
            [
                ["rpcstatd", -21, "Input should be greater than"],
                ["rpclockd", 328031, "Input should be less than"]
            ], id="invalid ports"
        ),
        pp(
            [
                ["mountd", 20049, "reserved for internal use"]
            ], id="excluded ports"
        ),
    ])
    def test_service_ports(self, start_nfs, test_port):
        """
        This test verifies that we can set custom port and the
        settings are reflected in the relevant files and are active.
        This also tests the port range and exclude.
        """
        assert start_nfs is True
        # Multiple restarts cause systemd failures.  Reset the systemd counters.
        reset_svcs("nfs-idmapd nfs-mountd nfs-server rpcbind rpc-statd")

        # Friendly index names
        name = 0
        value = 1
        err = 2

        # Test ports
        for port in test_port:
            port_name = port[name] + "_port"
            if port[err] is None:
                nfs_conf = call("nfs.update", {port_name: port[value]})
                assert nfs_conf[port_name] == port[value]
            else:
                with pytest.raises(ValidationErrors, match=port[err]):
                    nfs_conf = call("nfs.update", {port_name: port[value]})

        # Compare DB with setting in /etc/nfs.conf
        with nfs_config() as config_db:
            s = parse_server_config()
            assert int(s['mountd']['port']) == config_db["mountd_port"], str(s)
            assert int(s['statd']['port']) == config_db["rpcstatd_port"], str(s)
            assert int(s['lockd']['port']) == config_db["rpclockd_port"], str(s)

            # Confirm port settings are active
            confirm_rpc_port('mountd', config_db["mountd_port"])
            confirm_rpc_port('status', config_db["rpcstatd_port"])
            confirm_rpc_port('nlockmgr', config_db["rpclockd_port"])

    def test_runtime_debug(self, start_nfs):
        """
        This validates that the private NFS debugging API works correctly.
        """
        assert start_nfs is True
        disabled = {"NFS": ["NONE"], "NFSD": ["NONE"], "NLM": ["NONE"], "RPC": ["NONE"]}
        enabled = {"NFS": ["PROC", "XDR", "CLIENT", "MOUNT", "XATTR_CACHE"],
                   "NFSD": ["ALL"],
                   "NLM": ["CLIENT", "CLNTLOCK", "SVC"],
                   "RPC": ["CALL", "NFS", "TRANS"]}
        failure = {"RPC": ["CALL", "NFS", "TRANS", "NONE"]}
        try:
            res = call('nfs.get_debug')
            assert res == disabled

            call('nfs.set_debug', enabled)
            res = call('nfs.get_debug')
            assert set(res['NFS']) == set(enabled['NFS']), f"Mismatch on NFS: {res}"
            assert set(res['NFSD']) == set(enabled['NFSD']), f"Mismatch on NFSD: {res}"
            assert set(res['NLM']) == set(enabled['NLM']), f"Mismatch on NLM: {res}"
            assert set(res['RPC']) == set(enabled['RPC']), f"Mismatch on RPC: {res}"

            # Test failure case.  This should generate an ValueError exception on the system
            with pytest.raises(ValueError) as ve:
                call('nfs.set_debug', failure)
            assert 'Cannot specify another value' in str(ve), ve

        finally:
            call('nfs.set_debug', disabled)
            res = call('nfs.get_debug')
            assert res == disabled

    @pytest.mark.parametrize("param,errmsg", [
        pp([""], None, id="basic settings"),
        pp(["1.2.3.4"], "Cannot use", id="Not in choices"),
        pp(["a.b.c.d"], "not appear to be", id="Not a valid IP"),
        pp(["", "8.8.8.8"], "Cannot use", id="2nd entry not in choices"),
        pp(["", "ixsystems.com"], "not appear to be", id="2nd entry not valid IP"),
        pp(["", None], "Input should be", id="2nd entry is None"),
        pp(["", "a.b.c.d", "ixsystems.com"], "not appear to be", id="Two invalid entries")
    ])
    def test_config_bindip(self, start_nfs, param, errmsg):
        '''
        Test the bindip setting in nfs config
        This test requires a static IP address
        * Success testing:
            - Test the actual bindip config setting
                o Confirm setting in conf files
                o Confirm service on IP address
        * Failure testing:
            - Valid IP, but does not match choices
            - Invalid IP
            - Two entries, one valid the other not
        '''
        assert start_nfs is True

        if errmsg is None:
            # Multiple restarts cause systemd failures.  Reset the systemd counters.
            reset_svcs("nfs-idmapd nfs-mountd nfs-server rpcbind rpc-statd")

            choices = call("nfs.bindip_choices")
            assert truenas_server.ip in choices

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
        else:
            # None of these should make it to the config
            if param[0] == "":
                param[0] = truenas_server.ip

            # Test the config and the standalone private
            with pytest.raises((ValueError, ValidationErrors)) as ve:
                call("nfs.update", {"bindip": param})
            if ve.typename == "ValueError":
                assert errmsg in str(ve.value)
            else:
                assert errmsg in str(ve.value.errors[0])

    @pytest.mark.parametrize("param,errmsg", [
        pp([""], None, id="basic settings"),
        pp(["a.b.c.d"], "not appear to be", id="Not a valid IP"),
        pp(["", "ixsystems.com"], "not appear to be", id="2nd entry not valid IP"),
        pp(["", None], "expected str instance", id="2nd entry is None"),
        pp(["", "a.b.c.d", "ixsystems.com"], "not appear to be", id="Two invalid entries")
    ])
    def test_nfs_bindip(self, start_nfs, param, errmsg):
        '''
        This test requires a static IP address
        - Test the private nfs.bindip call
        * Failure testing:
            - Valid IP, but does not match choices
            - Invalid IP
            - Two entries, one valid the other not
        '''
        assert start_nfs is True

        if errmsg is None:
            # Multiple restarts cause systemd failures.  Reset the systemd counters.
            reset_svcs("nfs-idmapd nfs-mountd nfs-server rpcbind rpc-statd")

            call("nfs.bindip", {"bindip": [truenas_server.ip]})
            call("nfs.bindip", {"bindip": []})

        else:
            # None of these should make it to the config
            if param[0] == "":
                param[0] = truenas_server.ip

            # Test the config and the standalone private
            with pytest.raises((ValueError, ValidationErrors, TypeError)) as ve:
                call("nfs.bindip", {"bindip": param})
            if ve.typename in ["ValueError", "TypeError"]:
                assert errmsg in str(ve.value)
            else:
                assert errmsg in str(ve.value.errors[0])

    def test_v4_domain(self, start_nfs):
        '''
        The v4_domain configuration item maps to the 'Domain' setting in
        the [General] section of /etc/idmapd.conf.
        It is described as:
            The local NFSv4 domain name. An NFSv4 domain is a namespace
            with a unique username<->UID and groupname<->GID mapping.
            (Default: Host's fully-qualified DNS domain name)
        '''
        assert start_nfs is True

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

    def test_xattr_support(self, start_nfs):
        """
        Perform basic validation of NFSv4.2 xattr support.
        Mount path via NFS 4.2, create a file and dir,
        and write + read xattr on each.
        """
        assert start_nfs is True

        xattr_nfs_path = f'/mnt/{pool_name}/test_nfs4_xattr'
        with nfs_dataset("test_nfs4_xattr"):
            with nfs_share(xattr_nfs_path):
                with SSH_NFS(truenas_server.ip, xattr_nfs_path, vers=4.2,
                             user=user, password=password, ip=truenas_server.ip) as n:
                    n.create("testfile")
                    n.setxattr("testfile", "user.testxattr", "the_contents")
                    xattr_val = n.getxattr("testfile", "user.testxattr")
                    assert xattr_val == "the_contents"

                    n.create("testdir", True)
                    n.setxattr("testdir", "user.testxattr2", "the_contents2")
                    xattr_val = n.getxattr("testdir", "user.testxattr2")
                    assert xattr_val == "the_contents2"

    class TestSubtreeShares:
        """
        Wrap a class around test_37 to allow calling the fixture only once
        in the parametrized test
        """

        # TODO: Work up a valid IPv6 test (when CI environment supports it)
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
                    contents = call('sharing.nfs.query')
                    startIdList = [item.get('id') for item in contents]

                    # Create the dirs
                    dirs = ["everybody_1", "everybody_2", "limited_1", "dir_1", "dir_2"]
                    subdirs = ["subdir1", "subdir2", "subdir3"]
                    try:
                        for dir in dirs:
                            ssh(f"mkdir -p {vol0}/{dir}")
                            for subdir in subdirs:
                                ssh(f"mkdir -p {vol0}/{dir}/{subdir}")
                                # And symlinks
                                ssh(f"ln -sf {vol0}/{dir}/{subdir} {vol0}/{dir}/symlink2{subdir}")

                        yield vol0, err_strs
                    finally:
                        # Remove the created dirs
                        for dir in dirs:
                            ssh(f"rm -rf {vol0}/{dir}")

                        # Remove the created shares
                        contents = call('sharing.nfs.query')
                        endIdList = [item.get('id') for item in contents]
                        [call('sharing.nfs.delete', id) for id in endIdList if id not in startIdList]

        @pytest.mark.parametrize(
            "dirname,isHost,HostOrNet,ExpectToPass, ErrFormat", [
                pp("everybody_1", True, ["*"], True, None, id="NAS-120957: host - everybody"),
                pp("everybody_2", True, ["*"], True, None, id="NAS-120957: host - non-related paths"),
                pp("everybody_2", False, ["192.168.1.0/22"], True, None, id="NAS-129577: network, everybody, same path"),
                pp("limited_1", True, ["127.0.0.1"], True, None, id="NAS-123042: host - export subdirs"),
                pp("limited_1", False, ["192.168.1.0/22"], True, None, id="NAS-123042: network - export subdirs"),
                pp("limited_1", True, ["127.0.0.1"], False, 0, id="NAS-127220: host - already exported"),
                pp("limited_1", False, ["192.168.1.0/22"], False, 2, id="NAS-127220: network - already exported"),
                pp("dir_1", True, ["*.example.com"], True, None, id="NAS-120616: host - wildcards"),
                pp("dir_1", True, ["*.example.com"], False, 0, id="NAS-127220: host - wildcard already exported"),
                pp("dir_1/subdir2", False, ["2001:0db8:85a3:0000:0000:8a2e::/96"],
                   True, None, id="NAS-123042: network - IPv6 network range"),
                pp("dir_1/subdir2", True, ["2001:0db8:85a3:0000:0000:8a2e:0370:7334"],
                   True, None, id="NAS-129577: host - IPv6 allow host overlap with network"),
                pp("dir_1/subdir2", False, ["2001:0db8:85a3:0000:0000:8a2e:0370:7334/112"],
                   False, 1, id="NAS-123042: network - IPv6 overlap with network"),
                pp("dir_1/subdir3", True, ["192.168.27.211"], True, None, id="NAS-123042: host - export sub-subdirs"),
                pp("dir_1/subdir3", False, ["192.168.24.0/22"],
                   True, None, id="NAS-129522: network - allow overlap with host"),
                pp("limited_1/subdir2", True, ["*"], True, None, id="NAS-123042: host - setup everybody on sub-subdir"),
                pp("limited_1/subdir2", True, ["*"], False, 2, id="NAS-127220: host - already exported sub-subdir"),
                pp("dir_2/subdir2", False, ["192.168.1.0/24"],
                   True, None, id="NAS-123042: network - export sub-subdirs"),
                pp("dir_2/subdir2", False, ["192.168.1.0/32"], False, 1, id="NAS-123042: network - overlap sub-subdir"),
                pp("limited_1/subdir3", True, ["192.168.1.0", "*.ixsystems.com"],
                   True, None, id="NAS-123042: host - two hosts, same sub-subdir"),
                pp("dir_1/symlink2subdir3", True, ["192.168.0.0"], False, 3, id="Block exporting symlinks"),
            ],
        )
        def test_subtree_share(self, start_nfs, dataset_and_dirs, dirname, isHost, HostOrNet, ExpectToPass, ErrFormat):
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
            assert start_nfs is True

            vol, err_strs = dataset_and_dirs
            dirpath = f'{vol}/{dirname}'
            if isHost:
                payload = {"path": dirpath, "hosts": HostOrNet}
            else:
                payload = {"path": dirpath, "networks": HostOrNet}

            if ExpectToPass:
                call("sharing.nfs.create", payload)
            else:
                with pytest.raises(ValidationErrors) as ve:
                    call("sharing.nfs.create", payload)
                errStr = str(ve.value.errors[0])
                # Confirm we have the expected error message format
                for this_substr in err_strs[ErrFormat]:
                    assert this_substr in errStr

    @pytest.mark.timeout(600)
    def test_nfsv4_acl_support(self, start_nfs):
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
        assert start_nfs is True

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
        # getacl setting
        simplified = True
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

                            result = call('filesystem.getacl', acl_nfs_path, not simplified)
                            for idx, ace in enumerate(result['acl']):
                                assert ace == {**nfsacl[idx], "who": None}, str(ace)

                        for flag in ("INHERIT_ONLY", "NO_PROPAGATE_INHERIT"):
                            theacl[4]['flags'][flag] = True
                            n.setacl(".", theacl)
                            nfsacl = n.getacl(".")
                            for idx, ace in enumerate(nfsacl):
                                assert ace == theacl[idx], str(ace)

                            result = call('filesystem.getacl', acl_nfs_path, not simplified)
                            for idx, ace in enumerate(result['acl']):
                                assert ace == {**nfsacl[idx], "who": None}, str(ace)

                        if test_acl_flag:
                            assert 'none' == n.getaclflag(".")
                            for acl_flag in ['auto-inherit', 'protected', 'defaulted']:
                                n.setaclflag(".", acl_flag)
                                assert acl_flag == n.getaclflag(".")

                                result = call('filesystem.getacl', acl_nfs_path, not simplified)

                                # Normalize the flag_is_set name for comparision to plugin equivalent
                                # (just remove the '-' from auto-inherit)
                                if acl_flag == 'auto-inherit':
                                    flag_is_set = 'autoinherit'
                                else:
                                    flag_is_set = acl_flag

                                # Now ensure that only the expected flag is set
                                nfs41_flags = result['aclflags']
                                for flag in ['autoinherit', 'protected', 'defaulted']:
                                    if flag == flag_is_set:
                                        assert nfs41_flags[flag], nfs41_flags
                                    else:
                                        assert not nfs41_flags[flag], nfs41_flags

    @pytest.mark.parametrize('state,expected', [
        pp(None, 'n', id="default state"),
        pp(True, 'y', id="enable"),
        pp(False, 'n', id="disable")
    ])
    def test_manage_gids(self, start_nfs, state, expected):
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

        TEST:   Confirm manage_gids is set in /etc/nfs.conf for
                both the enable and disable states

        TODO: Add client-side and server-side test from client when available
        '''
        assert start_nfs is True
        with nfs_config():

            if state is not None:
                sleep(3)  # In Cobia: Prevent restarting NFS too quickly.
                call("nfs.update", {"userd_manage_gids": state})

            s = parse_server_config()
            assert s['mountd']['manage-gids'] == expected, str(s)

    def test_rdma_config(self, start_nfs):
        '''
        Mock response from rdma.capable_protocols to confirm NFS over RDMA config setting
        '''
        assert start_nfs is True

        # Confirm the setting does not exist by default
        s = parse_server_config()
        assert s.get('rdma') is None, str(s)

        # RDMA setting should fail on a test vm.
        with pytest.raises(ValidationErrors) as ve:
            call("nfs.update", {"rdma": True})
        assert ve.value.errors == [
            ValidationError(
                'nfs_update.rdma',
                'This platform cannot support NFS over RDMA or is missing an RDMA capable NIC.',
                22
            )
        ]

        with mock("system.is_enterprise", return_value=True):
            with mock("rdma.capable_protocols", return_value=['NFS']):
                with nfs_config():
                    call("nfs.update", {"rdma": True})
                    s = parse_server_config()
                    assert s['nfsd']['rdma'] == 'y', str(s)
                    # 20049 is the default port for NFS over RDMA.
                    assert s['nfsd']['rdma-port'] == '20049', str(s)

    def test_prevent_shell_changes(self, start_nfs):
        '''
        Confirm nfs config is managed
        '''
        assert start_nfs is True

        def monkey_with_db():
            # Add NFS setting via direct DB
            ssh("sqlite3 /data/freenas-v1.db 'UPDATE services_nfs set nfs_srv_rdma=1'")

        def modnfsconf():
            # Add NFS setting via shell
            ssh(r"sed -i '/^\[nfsd\]/a rdma = y' /etc/nfs.conf")
            ssh("systemctl reload nfs-server")
            res = ssh("grep rdma /etc/nfs.conf")
            assert 'rdma' in res

        def rogueconf():
            # Add a rogue config file
            ssh("mkdir -p /etc/nfs.conf.d")
            ssh(r"echo '[nfsd]\nrdma = y\nrdma-port = 20049' > /etc/nfs.conf.d/rogue.conf")
            res = ssh("grep rdma /etc/nfs.conf.d/rogue.conf")
            assert 'rdma' in res

        def confirm_clean():
            res = ssh("grep rdma /etc/nfs.conf", check=False)
            assert 'rdma' not in res
            res = ssh("ls /etc/nfs.conf.d/rogue.conf", check=False, complete_response=True)
            assert "No such file or directory" in res['stderr']

        with mock("system.is_enterprise", return_value=False):
            with nfs_config():
                with nfs_dataset("deleteme") as ds:
                    for monkey_business in [modnfsconf, rogueconf]:
                        # Confirm restore with NFS -server- config changes
                        monkey_business()
                        call("nfs.update", {"mountd_log": True})
                        confirm_clean()

                        # Confirm restore with NFS -share- config changes
                        monkey_business()
                        with nfs_share(f"/mnt/{ds}"):
                            confirm_clean()
                            monkey_business()

                        confirm_clean()

            # Confirm restore with DB manipulations
            with nfs_db():
                monkey_with_db()
                ssh("rm -f /etc/nfs.conf")
                call('service.control', 'RESTART', 'nfs', job=True)
                confirm_clean()

    @pytest.mark.parametrize('entry_type,num,expect_alert', [
        pp('both', 0, False, id="confirm no alerts"),
        pp('hosts', 100, True, id="excessive hosts alert: 100"),
        pp('networks', 100, True, id="excessive networks alert: 100"),
        pp('hosts', 99, False, id="excessive hosts alert clear: 99"),
        pp('networks', 99, False, id="excessive networks alert clear: 0"),
    ])
    def test_share_host_and_network_alerts(self, start_nfs, nfs_dataset_and_share, entry_type, num, expect_alert):
        """Test alert generation wtih excessive number of host or network entries. Current threshold: 100"""
        assert start_nfs is True
        share_id = nfs_dataset_and_share['nfsid']
        ds = nfs_dataset_and_share['ds']
        nfs_share_alerts = {'hosts': "NFSHostListExcessive", 'networks': "NFSNetworkListExcessive"}

        match entry_type:
            case 'both':  # Both hosts and networks are empty should result in no alerts
                alerts = call('alert.list')
                current_alerts = [entry for entry in alerts if entry['key'] in list(nfs_share_alerts.values())]
                assert len(current_alerts) == 0, f"Unexpectedly found NFS share alert.\n{current_alerts}"
            case 'hosts':
                allowed_client_list = [] if num == 0 else [f"192.168.50.{i}" for i in range(1, num + 1)]
            case 'networks':
                allowed_client_list = [] if num == 0 else [f"192.168.40.{i}/32" for i in range(1, num + 1)]

        if entry_type in ['hosts', 'networks']:
            alert_name = nfs_share_alerts[entry_type]
            alerts = call('alert.list')

            # Confirm we're starting in an expected state
            this_alert = [entry for entry in alerts if entry['klass'] == alert_name]
            if expect_alert:
                # Should be starting clean
                assert len(this_alert) == 0, f"Unexpectedly found pre-existing alert '{alert_name}'.\n{alerts}"
            else:
                # Should have an alert to clear
                assert len(this_alert) > 0, f"Unexpectedly did not find an alert to clear '{alert_name}'.\n{alerts}"

            # Make the share change and get the current list of alerts
            call('sharing.nfs.update', share_id, {entry_type: allowed_client_list})
            alerts = call('alert.list')

            # Confirm we get the expected result
            if expect_alert:
                this_alert = [entry for entry in alerts if entry['klass'] == alert_name]
                assert len(this_alert) == 1, f"Did not find alert for '{alert_name}'.\n{alerts}"
            else:
                # The alert should be cleared
                this_alert = [entry for entry in alerts if entry['key'] == f"/mnt/{ds}"]
                assert len(this_alert) == 0, f"Unexpectedly found alert for key '/mnt/{ds}'.\n{alerts}"

    def test_share_alert_on_share_delete(self, start_nfs):
        """Share alerts should be deleted when the share is deleted. Current threshold: 100"""
        assert start_nfs is True
        alerts = call('alert.list')
        current_alerts = [entry for entry in alerts if entry['klass'] == "NFSHostListExcessive"]
        assert len(current_alerts) == 0, f"Unexpectedly found NFS share alert.\n{current_alerts}"

        with nfs_dataset('nfs') as ds:
            with nfs_share(NFS_PATH, {
            }) as nfsid:
                alerts = call('alert.list')
                current_alerts = [entry for entry in alerts if entry['key'] == f"/mnt/{ds}"]
                assert len(current_alerts) == 0, f"Unexpectedly found NFS share alert for key '/mnt/{ds}'\n{alerts}"

                allowed_client_list = [f"192.168.50.{i}" for i in range(1, 101)]
                call('sharing.nfs.update', nfsid, {'hosts': allowed_client_list})
                alerts = call('alert.list')

                this_alert = [entry for entry in alerts if entry['klass'] == "NFSHostListExcessive"]
                assert len(this_alert) == 1, f"Did not find alert for 'NFSHostListExcessive'.\n{alerts}"

        # Share should be gone.  Check alerts
        alerts = call('alert.list')
        this_alert = [entry for entry in alerts if entry['klass'] == "NFSHostListExcessive"]
        assert len(this_alert) == 0, f"Unexpectedly found alert for 'NFSHostListExcessive'.\n{alerts}"


def test_pool_delete_with_attached_share():
    '''
    Confirm we can delete a pool with the system dataset and a dataset with active NFS shares
    '''
    with another_pool() as new_pool:
        # Move the system dataset to this pool
        with system_dataset(new_pool['name']):
            # Add some additional NFS stuff to make it interesting
            with nfs_dataset("deleteme", pool=new_pool['name']) as ds:
                with nfs_share(f"/mnt/{ds}"):
                    with manage_start_nfs():
                        # Delete the pool and confirm it's gone
                        call("pool.export", new_pool["id"], {"destroy": True}, job=True)
                        assert call("pool.query", [["name", "=", f"{new_pool['name']}"]]) == []


def test_threadpool_mode():
    '''
    Verify that NFS thread pool configuration can be adjusted through private API endpoints.

    NOTE: This request will fail if NFS server (or NFS client) is still running.
    '''
    assert get_nfs_service_state() == "STOPPED", "NFS cannot be running during this test."
    default_mode = call('nfs.get_threadpool_mode')

    supported_modes = ["AUTO", "PERCPU", "PERNODE", "GLOBAL"]
    try:
        for m in supported_modes:
            call('nfs.set_threadpool_mode', m)
            res = call('nfs.get_threadpool_mode')
            assert res == m, res
    finally:
        # Restore to default
        call('nfs.set_threadpool_mode', default_mode)


@pytest.mark.parametrize('exports', ['missing', 'empty'])
def test_missing_or_empty_exports(exports):
    '''
    NAS-123498: Eliminate conditions on exports for service start
    The goal is to make the NFS server behavior similar to the other protocols
    '''
    # Setup /etc/exports
    if exports == 'empty':
        ssh("echo '' > /etc/exports")
    else:  # 'missing'
        ssh("rm -f /etc/exports")

    with nfs_config() as nfs_conf:
        try:
            # Start NFS
            call('service.control', 'START', 'nfs', job=True)
            sleep(1)
            confirm_nfsd_processes(nfs_conf['servers'])
        finally:
            # Return NFS to stopped condition
            call('service.control', 'STOP', 'nfs', job=True)
            sleep(1)

    # Confirm stopped
    assert get_nfs_service_state() == "STOPPED"


@pytest.mark.parametrize('expect_NFS_start', [False, True])
def test_files_in_exportsd(expect_NFS_start):
    '''
    Any files in /etc/exports.d are potentially dangerous, especially zfs.exports.
    We implemented protections against rogue exports files.
    - We block starting NFS if there are any files in /etc/exports.d
    - We generate an alert when we detect this condition
    - We clear the alert when /etc/exports.d is empty
    '''
    fail_check = {False: 'ConditionDirectoryNotEmpty=!/etc/exports.d', True: None}

    try:
        # Setup the test
        set_immutable_state('/etc/exports.d', want_immutable=False)  # Disable immutable

        # Do the 'failing' case first to end with a clean condition
        if not expect_NFS_start:
            ssh("echo 'bogus data' > /etc/exports.d/persistent.file")
            ssh("chattr +i /etc/exports.d/persistent.file")
        else:
            # Restore /etc/exports.d directory to a clean state
            ssh("chattr -i /etc/exports.d/persistent.file")
            ssh("rm -rf /etc/exports.d/*")

        set_immutable_state('/etc/exports.d', want_immutable=True)  # Enable immutable

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
