import contextlib
import itertools
import json
import random
import string
import time
from collections import defaultdict
from functools import cache

import pytest
from assets.websocket.pool import zvol
from assets.websocket.service import ensure_service_enabled, ensure_service_started
from auto_config import ha, pool_name

from middlewared.service_exception import MatchNotFound, ValidationErrors
from middlewared.test.integration.assets.iscsi import iscsi_extent
from middlewared.test.integration.assets.nvmet import (NVME_DEFAULT_TCP_PORT, nvmet_ana, nvmet_host, nvmet_host_subsys,
                                                       nvmet_namespace, nvmet_port, nvmet_port_subsys, nvmet_subsys,
                                                       nvmet_xport_referral)
from middlewared.test.integration.assets.pool import another_pool, dataset
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server, host as init_truenas_server

digits = ''.join(random.choices(string.digits, k=3))

# [i.api for i in DHCHAP_DHGROUP]
DHCHAP_DHGROUP_API_RANGE = [None, '2048-BIT', '3072-BIT', '4096-BIT', '6144-BIT', '8192-BIT']
# [i.api for i in DHCHAP_HASH]
DHCHAP_HASH_API_RANGE = ['SHA-256', 'SHA-384', 'SHA-512']

MB = 1024 * 1024
SERVICE_NAME = 'nvmet'
SUBSYS_NAME1 = 'testsubsys1'
SUBSYS_NAME2 = 'testsubsys2'
SUBSYS_NAME3 = 'testsubsys3'
SUBSYS_NAME4 = 'testsubsys4'
DISCOVERY_NQN = 'nqn.2014-08.org.nvmexpress.discovery'
ZVOL1_NAME = f'NVMET_ZVOL1_{digits}'
ZVOL1_MB = 100
ZVOL2_NAME = f'NVMET_ZVOL2_{digits}'
ZVOL2_MB = 200
ZVOL3_NAME = f'NVMET_ZVOL3_{digits}'
ZVOL3_MB = 300
ZVOL4_NAME = f'NVMET_ZVOL4_{digits}'
ZVOL4_MB = 400
NVMET_SPACE_ZVOL = f'NVMET SPACE ZVOL{digits}'
NVMET_SPACE_MB = 150
NVMET_ENCRYPTED_ZVOL = f'NVMET_ENCRYPTED_ZVOL{digits}'
NVMET_ENCRYPTED_MB = 250
NVMET_ENCRYPTED_PASSPHRASE = 'testing12345test'
ZVOL_RESIZE_NAME = f'NVMET_ZVOLRESIZE_{digits}'
ZVOL_RESIZE_START_MB = 50
ZVOL_RESIZE_END_MB = 150

FAKE_HOSTNQN = 'nqn.2014-08.org.nvmexpress:uuid:48747223-7535-4f8e-a789-b8af8bfdea54'
HOST1_NQN = 'nqn.2011-06.com.truenas:uuid-68bf9433-63ef-49f5-a921-4c0f8190fd94:host1'
HOST2_NQN = 'nqn.2011-06.com.truenas:hostname2'
DEVICE_TYPE_FILE = 'FILE'
MB_10 = 100 * MB
MB_100 = 100 * MB
MB_150 = 150 * MB
MB_200 = 200 * MB
NVME_ALT1_TCP_PORT = 4444
NVME_ALT2_TCP_PORT = 4555


@cache
def basenqn():
    return call('nvmet.global.config')['basenqn']


@pytest.fixture(scope='module')
def zvol1():
    with zvol(ZVOL1_NAME, ZVOL1_MB, pool_name) as config:
        yield config


@pytest.fixture(scope='module')
def zvol2():
    with zvol(ZVOL2_NAME, ZVOL2_MB, pool_name) as config:
        yield config


@pytest.fixture(scope='module')
def zvol3():
    with zvol(ZVOL3_NAME, ZVOL3_MB, pool_name) as config:
        yield config


@pytest.fixture(scope='module')
def zvol4():
    with zvol(ZVOL4_NAME, ZVOL4_MB, pool_name) as config:
        yield config


@pytest.fixture(scope='module')
def space_zvol():
    with zvol(NVMET_SPACE_ZVOL, NVMET_SPACE_MB, pool_name) as config:
        yield config


@pytest.fixture(scope='module')
def encrypted_zvol():
    with dataset(NVMET_ENCRYPTED_ZVOL, {
        'type': 'VOLUME',
        'volsize': NVMET_ENCRYPTED_MB * MB,
        'volblocksize': '16K',
        'encryption': True,
        'inherit_encryption': False,
        'encryption_options': {
            'algorithm': 'AES-128-CCM',
            'passphrase': NVMET_ENCRYPTED_PASSPHRASE,
        }
    }) as ds:
        config = call('pool.dataset.query', [['name', '=', ds]], {'get': True})
        yield config


def _ddict2dict(d):
    for k, v in d.items():
        if isinstance(v, dict):
            d[k] = _ddict2dict(v)
    return dict(d)


@contextlib.contextmanager
def assert_validation_errors(attribute: str, errmsg: str):
    with pytest.raises(ValidationErrors) as ve:
        yield
    assert ve.value.errors[0].attribute == attribute
    assert ve.value.errors[0].errmsg.startswith(errmsg)


def wait_for_session_count(count: int, retries: int = 5, delay: int = 1, raise_error: bool = False):
    sessions = []
    for i in range(retries):
        sessions = call('nvmet.global.sessions')
        if len(sessions) == count:
            return
        time.sleep(delay)
    if raise_error:
        raise ValueError(f'Expected {count} sessions, but have {len(sessions)}')


class NVMeCLIClient:
    DEBUG = False

    def __init__(self):
        self.run_command('modprobe nvme')
        self.run_command('modprobe nvme_tcp')

    def discover(self, addr=None, port=NVME_DEFAULT_TCP_PORT, transport='tcp'):
        if addr is None:
            addr = truenas_server.ip
        command = f'nvme discover -t {transport} -a {addr} -s {port} --output-format=json'
        return json.loads(self.run_command(command))

    def hostnqn(self):
        return self.run_command('cat /etc/nvme/hostnqn').strip()

    def connect(self, nqn, addr=None, port=NVME_DEFAULT_TCP_PORT, transport='tcp', **kwargs):
        if addr is None:
            addr = truenas_server.ip
        command = f'nvme connect -t {transport} -a {addr} -s {port} -n {nqn}'

        if dhchap_secret := kwargs.pop('dhchap_secret', None):
            command += f' --dhchap-secret={dhchap_secret}'

        if dhchap_ctrl_secret := kwargs.pop('dhchap_ctrl_secret', None):
            command += f' --dhchap-ctrl-secret={dhchap_ctrl_secret}'

        if self.DEBUG:
            print("COMMAND:", command)
        return self.run_command(command)

    def disconnect(self, nqn):
        command = f'nvme disconnect -n {nqn}'
        return self.run_command(command)

    def connect_all(self, addr=None, port=NVME_DEFAULT_TCP_PORT, transport='tcp'):
        if addr is None:
            addr = truenas_server.ip
        command = f'nvme connect-all -t {transport} -a {addr} -s {port}'
        return self.run_command(command)

    def disconnect_all(self):
        command = 'nvme disconnect-all'
        return self.run_command(command)

    def nvme_list(self):
        command = 'nvme list --output-format=json'
        return json.loads(self.run_command(command))

    def nvme_devices(self):
        serial_to_name = {s['serial']: s['name'] for s in call('nvmet.subsys.query',
                                                               [], {'select': ['name', 'serial']})}
        name_to_nqn = {name: f'{basenqn()}:{name}' for name in serial_to_name.values()}
        result = defaultdict(lambda: defaultdict(dict))
        for device in self.nvme_list().get('Devices'):
            try:
                name = serial_to_name[device.get('SerialNumber')]
                nqn = name_to_nqn[name]
            except KeyError:
                continue
            result[nqn]['namespace'][device.get('NameSpace')] = device
            result[nqn]['name'] = name
        return _ddict2dict(result)

    def nvme_list_subsys(self):
        command = 'nvme list-subsys --output-format=json'
        return json.loads(self.run_command(command))

    @contextlib.contextmanager
    def connect_ctx(self, nqn, addr=None, port=NVME_DEFAULT_TCP_PORT, transport='tcp', **kwargs):
        if self.DEBUG:
            print('Connecting:', nqn)
        self.connect(nqn, addr, port, transport, **kwargs)
        try:
            if self.DEBUG:
                print('Connected:', nqn)
            yield
        finally:
            if self.DEBUG:
                print('Disconnecting:', nqn)
            self.disconnect(nqn)
            if self.DEBUG:
                print('Disconnected:', nqn)

    @contextlib.contextmanager
    def connect_all_ctx(self, addr=None, port=NVME_DEFAULT_TCP_PORT, transport='tcp'):
        if self.DEBUG:
            print('Doing connect-all')
        self.connect_all(addr, port, transport)
        try:
            if self.DEBUG:
                print('Connected')
            yield
        finally:
            if self.DEBUG:
                print('Doing disconnect-all')
            self.disconnect_all()
            if self.DEBUG:
                print('Disconnected')

    def run_command(self, command):
        pass


class LoopbackClient(NVMeCLIClient):
    def run_command(self, command):
        if self.DEBUG:
            print("COMMAND:", command)
        return ssh(command)


@pytest.fixture(scope='module')
def loopback_client():
    return LoopbackClient()


class NVMeRunning:

    @pytest.fixture(scope='class')
    def fixture_nvmet_running(self):
        with ensure_service_enabled(SERVICE_NAME):
            with ensure_service_started(SERVICE_NAME, 3):
                yield

    @contextlib.contextmanager
    def subsys(self, name, port, **kwargs):
        zvol_name = kwargs.pop('zvol_name', None)
        nqn = f'{basenqn()}:{name}'
        with nvmet_subsys(name, **kwargs) as subsys:
            with nvmet_port_subsys(subsys['id'], port['id']):
                if zvol_name:
                    with nvmet_namespace(subsys['id'], f'zvol/{zvol_name}') as ns:
                        yield {
                            'id': subsys['id'],
                            'nqn': nqn,
                            'subsys': subsys,
                            'namespace': ns}
                else:
                    yield {
                        'id': subsys['id'],
                        'nqn': nqn,
                        'subsys': subsys}

    def assert_subsys_namespaces(self, data: dict, subnqn: str, sizes: list):
        assert len(data[subnqn]['namespace']) == len(sizes)
        for nsid, sizeMB in sizes:
            assert data[subnqn]['namespace'][nsid]['PhysicalSize'] == sizeMB * MB

    def subsys_paths(self, data: dict, subnqn: str):
        # Example data
        # [{'HostID': '91867c06-1d92-4b39-8316-3ca4b98aa5eb',
        #   'HostNQN': 'nqn.2014-08.org.nvmexpress:uuid:e8039519-21ec-49db-a7e2-422ab997abc0',
        #   'Subsystems': [{'NQN': 'nqn.2011-06.com.truenas:uuid:cef24057-8050-4fc7-ab87-773e19b32b0e:testsubsys1',
        #                   'Name': 'nvme-subsys1',
        #                   'Paths': [{'Address': 'traddr=192.168.56.115,trsvcid=4420,src_addr=192.168.56.115',
        #                              'Name': 'nvme1',
        #                              'State': 'live',
        #                              'Transport': 'tcp'}]}]}]
        for entry in data:
            if 'Subsystems' not in entry:
                continue
            for subsys in entry['Subsystems']:
                if subsys.get('NQN') == subnqn:
                    return subsys.get('Paths', [])
        return []

    def subsys_path_count(self, data: dict, subnqn: str):
        return len(self.subsys_paths(data, subnqn))

    def subsys_path_present(self, data: dict,
                            subnqn: str,
                            traddr: str,
                            trsvcid: str | int,
                            state: str | None = 'live',
                            transport: str = 'tcp'):
        # Example data
        # [{'HostID': '91867c06-1d92-4b39-8316-3ca4b98aa5eb',
        #   'HostNQN': 'nqn.2014-08.org.nvmexpress:uuid:e8039519-21ec-49db-a7e2-422ab997abc0',
        #   'Subsystems': [{'NQN': 'nqn.2011-06.com.truenas:uuid:cef24057-8050-4fc7-ab87-773e19b32b0e:testsubsys1',
        #                   'Name': 'nvme-subsys1',
        #                   'Paths': [{'Address': 'traddr=192.168.56.115,trsvcid=4420,src_addr=192.168.56.115',
        #                              'Name': 'nvme1',
        #                              'State': 'live',
        #                              'Transport': 'tcp'}]}]}]
        for path in self.subsys_paths(data, subnqn):
            if not path.get('Address').startswith(f'traddr={traddr},trsvcid={trsvcid},src_addr='):
                continue
            if state is not None:
                if path.get('State') != state:
                    continue
            if path.get('Transport') != transport:
                continue
            # If we reached here, then everything matches
            return True
        return False

    def assert_single_namespace(self, nc, subnqn, ns1MB, ip=None, port=None, **kwargs):
        if ip is None:
            ip = truenas_server.ip
        if port is None:
            port = NVME_DEFAULT_TCP_PORT
        with nc.connect_ctx(subnqn, ip, port, **kwargs):
            devices = nc.nvme_devices()
            assert len(devices) == 1, devices
            self.assert_subsys_namespaces(devices, subnqn, [(1, ns1MB)])
            data = nc.nvme_list_subsys()
            assert self.subsys_path_count(data, subnqn) == 1
            assert self.subsys_path_present(data, subnqn, ip, port)


class TestNVMe(NVMeRunning):
    """Fixture with NVMe"""

    @pytest.fixture(scope='class')
    def fixture_port(self, fixture_nvmet_running):
        assert truenas_server.ip in call('nvmet.port.transport_address_choices', 'TCP')
        with nvmet_port(truenas_server.ip) as port:
            yield port

    @pytest.fixture(scope='class')
    def hostnqn(self, loopback_client: NVMeCLIClient) -> str:
        return loopback_client.hostnqn()

    def test__service_stopped(self):
        assert call('service.query', [['service', '=', SERVICE_NAME]], {'get': True})['state'] == 'STOPPED'

    def test__no_sessions_when_service_stopped(self):
        assert call('service.query', [['service', '=', SERVICE_NAME]], {'get': True})['state'] == 'STOPPED'
        assert call('nvmet.global.sessions') == []

    def test__discover_fail_not_running(self, loopback_client: NVMeCLIClient):
        nc = loopback_client
        with pytest.raises(AssertionError, match='Connection refused'):
            nc.discover()

    def test__service_started(self, fixture_nvmet_running):
        assert call('service.query', [['service', '=', SERVICE_NAME]], {'get': True})['state'] == 'RUNNING'

    def test__discover_fail_no_port(self, loopback_client: NVMeCLIClient):
        nc = loopback_client
        with pytest.raises(AssertionError, match='Connection refused'):
            nc.discover()

    def assert_discovery(self, data: dict, subnqns: list | None = None):
        """
        Check that the discovery data has the expected results.

        The first entry should always be the current discovery subsystem.
        """
        expected_subnqns = set(subnqns if subnqns else [])
        expected_subnqns.add(DISCOVERY_NQN)
        assert 'records' in data
        for record in data['records']:
            subnqn = record.get('subnqn', '')
            assert subnqn in expected_subnqns, f'Unexpected subnqn: {subnqn}'
            if subnqn == DISCOVERY_NQN:
                assert record['subtype'] == 'current discovery subsystem', record
            else:
                assert record['subtype'] == 'nvme subsystem', record
            expected_subnqns.remove(subnqn)
        assert len(expected_subnqns) == 0, f'Did not find all expected subnqns: {",".join(expected_subnqns)}'

    def discovery_present(self, data: dict, needle: dict):
        """
        Check whether the specified `needle` is present in the discovery output.
        """
        assert 'records' in data
        for record in data['records']:
            matched = True
            for key, value in needle.items():
                if record[key] != value:
                    matched = False
                    break
            if matched:
                return True
        return False

    def test__discover_subsys(self, fixture_port, loopback_client: NVMeCLIClient, hostnqn: str):
        """
        Test that we can discover a subsystem.

        Check behavior of allow_any_host, and also when a `host` is permitted to
        access a subsystem.
        """
        port = fixture_port
        nc = loopback_client
        subsys1_nqn = f'{basenqn()}:{SUBSYS_NAME1}'
        with nvmet_subsys(SUBSYS_NAME1) as subsys:
            subsys_id = subsys['id']
            with nvmet_port_subsys(subsys_id, port['id']):
                self.assert_discovery(nc.discover())
                # Now allow ANYONE to discover the subsystem
                call('nvmet.subsys.update',
                     subsys_id,
                     {'allow_any_host': True})
                self.assert_discovery(nc.discover(), [subsys1_nqn])

                # Turn off allow_any_host, and replace by a host
                call('nvmet.subsys.update',
                     subsys_id,
                     {'allow_any_host': False})
                self.assert_discovery(nc.discover())

                with nvmet_host(hostnqn) as host:
                    with nvmet_host_subsys(host['id'], subsys_id):
                        self.assert_discovery(nc.discover(), [subsys1_nqn])
                    self.assert_discovery(nc.discover())
                self.assert_discovery(nc.discover())

    def test__discover_two_subsys(self, fixture_port, loopback_client: NVMeCLIClient, hostnqn: str):
        """
        Test that we can discover two subsystems.
        """
        nc = loopback_client
        with self.subsys(SUBSYS_NAME1, fixture_port, allow_any_host=True) as subsys1:
            self.assert_discovery(nc.discover(), [subsys1['nqn']])
            with self.subsys(SUBSYS_NAME2, fixture_port, allow_any_host=True) as subsys2:
                self.assert_discovery(nc.discover(), [subsys1['nqn'], subsys2['nqn']])
            self.assert_discovery(nc.discover(), [subsys1['nqn']])
            with self.subsys(SUBSYS_NAME2, fixture_port) as subsys2:
                self.assert_discovery(nc.discover(), [subsys1['nqn']])
                with nvmet_host(hostnqn) as host:
                    with nvmet_host_subsys(host['id'], subsys2['id']):
                        self.assert_discovery(nc.discover(), [subsys1['nqn'], subsys2['nqn']])

    def test__zvol_namespace(self, fixture_port, loopback_client, zvol1, zvol2, space_zvol):
        """
        Test that we can connect to a subsystem and see associated namespace.

        Also check that a ZVOL used for iSCSI cannot simultaneously be configured
        for NVMe-oF, and vice-versa.
        """
        nc = loopback_client

        zvol1_path = f'zvol/{zvol1["name"]}'
        zvol2_path = f'zvol/{zvol2["name"]}'

        with self.subsys(SUBSYS_NAME1, fixture_port, allow_any_host=True) as subsys1:
            subsys1_id = subsys1['id']
            subsys1_nqn = subsys1['nqn']
            with nvmet_namespace(subsys1_id, zvol1_path):
                with nc.connect_ctx(subsys1_nqn):
                    devices = nc.nvme_devices()
                    # Ensure 1 subsystem
                    assert len(devices) == 1, devices
                    # Ensure it has the namespaces we expect
                    self.assert_subsys_namespaces(devices, subsys1_nqn, [(1, ZVOL1_MB)])
                # Try to add the volume a second time, ensure that fails
                with assert_validation_errors('nvmet_namespace_create.device_path',
                                              f'This device_path already used by subsystem: {SUBSYS_NAME1}'):
                    with nvmet_namespace(subsys1_id, zvol1_path):
                        pass

                # Add another subsystem
                with self.subsys(SUBSYS_NAME2, fixture_port, allow_any_host=True) as subsys2:
                    subsys2_id = subsys2['id']
                    subsys2_nqn = subsys2['nqn']
                    # Try to add the volume to it, ensure it fails
                    with assert_validation_errors('nvmet_namespace_create.device_path',
                                                  f'This device_path already used by subsystem: {SUBSYS_NAME1}'):
                        with nvmet_namespace(subsys2_id, zvol1_path):
                            pass

                    # Instead add a volume that has a space in its name, ensure that works
                    with nvmet_namespace(subsys2_id, f'zvol/{space_zvol["name"]}') as ns:
                        with nc.connect_ctx(subsys2_nqn):
                            devices = nc.nvme_devices()
                            assert len(devices) == 1, devices
                            self.assert_subsys_namespaces(devices, subsys2_nqn, [(1, NVMET_SPACE_MB)])

                            # Now connect BOTH subsystems
                            with nc.connect_ctx(subsys1_nqn):
                                devices = nc.nvme_devices()
                                assert len(devices) == 2, devices
                                self.assert_subsys_namespaces(devices, subsys1_nqn, [(1, ZVOL1_MB)])
                                self.assert_subsys_namespaces(devices, subsys2_nqn, [(1, NVMET_SPACE_MB)])

                            # Ensure we can't update a namespace with an already used ZVOL
                            with assert_validation_errors('nvmet_namespace_update.device_path',
                                                          'This device_path already used by '
                                                          f'subsystem: {SUBSYS_NAME1}'):
                                call('nvmet.namespace.update', ns['id'], {'device_path': zvol1_path})

                            iscsi_extent_payload = {
                                'type': 'DISK',
                                'disk': zvol2_path,
                                'name': 'nvmet_test_extent'
                            }

                            with nvmet_namespace(subsys2_id, zvol2_path):
                                # Ensure we can't create iSCSI using a ZVOL used by us
                                with assert_validation_errors('iscsi_extent_create.disk',
                                                              'Disk currently in use by NVMe-oF '
                                                              f'subsystem {SUBSYS_NAME2} NSID 2'):
                                    with iscsi_extent(iscsi_extent_payload):
                                        pass

                            with iscsi_extent(iscsi_extent_payload):
                                # Ensure we can't create using a ZVOL used by iSCSI
                                in_use_msg = 'This device_path already used by iSCSI extent: nvmet_test_extent'
                                with assert_validation_errors('nvmet_namespace_create.device_path', in_use_msg):
                                    with nvmet_namespace(subsys2_id, zvol2_path):
                                        pass
                                # Ensure we can't update using a ZVOL used by iSCSI
                                with assert_validation_errors('nvmet_namespace_update.device_path', in_use_msg):
                                    call('nvmet.namespace.update', ns['id'], {'device_path': zvol2_path})

    def test__multiple_namespaces(self,
                                  fixture_port,
                                  loopback_client: NVMeCLIClient,
                                  zvol1,
                                  zvol2):
        """
        Test that we can connect to a subsystem and see multiple
        associated namespaces.
        """
        nc = loopback_client

        with self.subsys(SUBSYS_NAME1, fixture_port, allow_any_host=True) as subsys:
            subsys_id = subsys['id']
            subsys_nqn = subsys['nqn']
            with nvmet_namespace(subsys_id, f'zvol/{zvol1["name"]}'):
                # First ensure that we can discover the subsys with one namespace
                self.assert_discovery(nc.discover(), [subsys_nqn])
                # Ensure we're not currently connected
                devices = nc.nvme_list().get('Devices')
                assert len(devices) == 0
                assert len(nc.nvme_list_subsys()) == 0
                with nc.connect_ctx(subsys_nqn):
                    devices = nc.nvme_devices()
                    assert len(devices) == 1, devices
                    self.assert_subsys_namespaces(devices, subsys_nqn, [(1, ZVOL1_MB)])

                # Add another namespace to the subsystem
                with nvmet_namespace(subsys_id, f'zvol/{zvol2["name"]}'):
                    self.assert_discovery(nc.discover(), [subsys_nqn])
                    with nc.connect_ctx(subsys_nqn):
                        devices = nc.nvme_devices()
                        assert len(devices) == 1, devices
                        self.assert_subsys_namespaces(devices, subsys_nqn, [(1, ZVOL1_MB), (2, ZVOL2_MB)])

    def test__zvol_locked_namespace(self,
                                    fixture_port,
                                    loopback_client: NVMeCLIClient,
                                    zvol1,
                                    encrypted_zvol):
        """
        Test that we can lock and unlock a ZVOL used for a subsystem namespace,
        and that an attached client sees the namespace disappear and reappear.
        """
        nc = loopback_client

        with self.subsys(SUBSYS_NAME1, fixture_port, allow_any_host=True) as subsys:
            subsys_id = subsys['id']
            subsys_nqn = subsys['nqn']
            with nvmet_namespace(subsys_id, f'zvol/{zvol1["name"]}'):
                # First ensure that we can discover the subsys with one namespace
                self.assert_discovery(nc.discover(), [subsys_nqn])
                # Ensure we're not currently connected
                devices = nc.nvme_list().get('Devices')
                assert len(devices) == 0
                assert len(nc.nvme_list_subsys()) == 0
                with nc.connect_ctx(subsys_nqn):
                    devices = nc.nvme_devices()
                    assert len(devices) == 1, devices
                    self.assert_subsys_namespaces(devices, subsys_nqn, [(1, ZVOL1_MB)])

                # Add another (lockable) namespace to the subsystem
                with nvmet_namespace(subsys_id, f'zvol/{encrypted_zvol["name"]}'):
                    self.assert_discovery(nc.discover(), [subsys_nqn])
                    with nc.connect_ctx(subsys_nqn):
                        devices = nc.nvme_devices()
                        assert len(devices) == 1, devices
                        self.assert_subsys_namespaces(devices, subsys_nqn, [(1, ZVOL1_MB), (2, NVMET_ENCRYPTED_MB)])

                    # Lock the ZVOL
                    call('pool.dataset.lock', encrypted_zvol['id'], job=True)
                    with nc.connect_ctx(subsys_nqn):
                        devices = nc.nvme_devices()
                        assert len(devices) == 1, devices
                        self.assert_subsys_namespaces(devices, subsys_nqn, [(1, ZVOL1_MB)])

                    # Unlock the ZVOL again
                    call('pool.dataset.unlock',
                         encrypted_zvol['id'], {
                             'datasets': [{
                                 'passphrase': NVMET_ENCRYPTED_PASSPHRASE,
                                 'name': encrypted_zvol['name']}]
                         },
                         job=True)
                    with nc.connect_ctx(subsys_nqn):
                        devices = nc.nvme_devices()
                        assert len(devices) == 1, devices
                        self.assert_subsys_namespaces(devices, subsys_nqn, [(1, ZVOL1_MB), (2, NVMET_ENCRYPTED_MB)])

    def test__zvol_resize_namespace(self,
                                    fixture_port,
                                    loopback_client: NVMeCLIClient):
        """
        Test that we can resize a ZVOL used for a subsystem namespace,
        and that an attached client sees the namespace change size.
        """
        nc = loopback_client

        with self.subsys(SUBSYS_NAME1, fixture_port, allow_any_host=True) as subsys:
            subsys_id = subsys['id']
            subsys_nqn = subsys['nqn']
            with zvol(ZVOL_RESIZE_NAME, ZVOL_RESIZE_START_MB, pool_name) as zvol_config:
                with nvmet_namespace(subsys_id, f'zvol/{zvol_config["name"]}'):
                    # First ensure that we can discover the subsys with one namespace
                    self.assert_discovery(nc.discover(), [subsys_nqn])
                    # Ensure we're not currently connected
                    devices = nc.nvme_list().get('Devices')
                    assert len(devices) == 0
                    assert len(nc.nvme_list_subsys()) == 0
                    with nc.connect_ctx(subsys_nqn):
                        devices = nc.nvme_devices()
                        assert len(devices) == 1, devices
                        self.assert_subsys_namespaces(devices, subsys_nqn, [(1, ZVOL_RESIZE_START_MB)])

                        # Update the size of the ZVOL
                        call('pool.dataset.update', zvol_config['id'], {'volsize': ZVOL_RESIZE_END_MB * MB})

                        devices = nc.nvme_devices()
                        assert len(devices) == 1, devices
                        self.assert_subsys_namespaces(devices, subsys_nqn, [(1, ZVOL_RESIZE_END_MB)])

                        # Try to shrink the volume aagain, ensure that fails
                        with assert_validation_errors('pool_dataset_update.volsize',
                                                      'You cannot shrink a zvol from GUI, this may lead to data loss.'):
                            call('pool.dataset.update', zvol_config['id'], {'volsize': ZVOL_RESIZE_START_MB * MB})

                        # Check the size from the client perspective again
                        devices = nc.nvme_devices()
                        assert len(devices) == 1, devices
                        self.assert_subsys_namespaces(devices, subsys_nqn, [(1, ZVOL_RESIZE_END_MB)])

    def test__file_namespaces(self,
                              fixture_port,
                              loopback_client: NVMeCLIClient):
        """
        Test FILE based namespaces.

        Includes file resize test, and locked dataset test.
        """
        nc = loopback_client
        file1 = f'/mnt/{pool_name}/file1_{digits}'
        with self.subsys(SUBSYS_NAME1, fixture_port, allow_any_host=True) as subsys:
            subsys_id = subsys['id']
            subsys_nqn = subsys['nqn']
            with nvmet_namespace(subsys_id,
                                 file1,
                                 DEVICE_TYPE_FILE,
                                 filesize=MB_100,
                                 delete_options={'remove': True}) as ns:
                # First ensure that we can discover the subsys with one namespace
                self.assert_discovery(nc.discover(), [subsys_nqn])
                # Ensure we're not currently connected
                devices = nc.nvme_list().get('Devices')
                assert len(devices) == 0
                assert len(nc.nvme_list_subsys()) == 0
                with nc.connect_ctx(subsys_nqn):
                    devices = nc.nvme_devices()
                    assert len(devices) == 1, devices
                    self.assert_subsys_namespaces(devices, subsys_nqn, [(1, 100)])
                    # Resize the namespace (increase)
                    call('nvmet.namespace.update', ns['id'], {'filesize': MB_200})
                    devices = nc.nvme_devices()
                    assert len(devices) == 1, devices
                    self.assert_subsys_namespaces(devices, subsys_nqn, [(1, 200)])
                    # Ensure we can't shrink it
                    with assert_validation_errors('nvmet_namespace_update.filesize',
                                                  'Shrinking an namespace file is not allowed. '
                                                  'This can lead to data loss.'):
                        call('nvmet.namespace.update', ns['id'], {'filesize': MB_100})

                    # Now let's add a namespace base on a file on an encrypted volume
                    with dataset(f'ds_nvme{digits}', data={
                        'encryption': True,
                        'inherit_encryption': False,
                        'encryption_options': {'passphrase': NVMET_ENCRYPTED_PASSPHRASE}
                    }) as ds:
                        file2 = f'/mnt/{ds}/file2_{digits}'
                        with nvmet_namespace(subsys_id,
                                             file2,
                                             DEVICE_TYPE_FILE,
                                             filesize=MB_100,
                                             delete_options={'remove': True}):
                            devices = nc.nvme_devices()
                            assert len(devices) == 1, devices
                            self.assert_subsys_namespaces(devices, subsys_nqn, [(1, 200), (2, 100)])
                            # Lock the dataset
                            call('pool.dataset.lock', ds, job=True)
                            devices = nc.nvme_devices()
                            assert len(devices) == 1, devices
                            self.assert_subsys_namespaces(devices, subsys_nqn, [(1, 200)])

                            # Unlock the dataset again
                            call('pool.dataset.unlock',
                                 ds, {
                                     'datasets': [{
                                         'passphrase': NVMET_ENCRYPTED_PASSPHRASE,
                                         'name': ds}]
                                 },
                                 job=True)
                            devices = nc.nvme_devices()
                            assert len(devices) == 1, devices
                            self.assert_subsys_namespaces(devices, subsys_nqn, [(1, 200), (2, 100)])
                    # Dataset destroyed
                    devices = nc.nvme_devices()
                    assert len(devices) == 1, devices
                    self.assert_subsys_namespaces(devices, subsys_nqn, [(1, 200)])

                iscsi_extent_payload = {
                    'type': 'FILE',
                    'path': file1,
                    'name': 'nvmet_test_extent'
                }

                # Ensure we can't create iSCSI using a FILE used by us
                with assert_validation_errors('iscsi_extent_create.path',
                                              'File currently in use by NVMe-oF '
                                              f'subsystem {SUBSYS_NAME1} NSID 1'):
                    with iscsi_extent(iscsi_extent_payload):
                        pass

                iscsi_extent_payload = {
                    'type': 'FILE',
                    'path': file2,
                    'name': 'nvmet_test_extent',
                    'filesize': MB_100
                }

                with iscsi_extent(iscsi_extent_payload, True):
                    # Ensure we can't create using a FILE used by iSCSI
                    in_use_msg = 'This device_path already used by iSCSI extent: nvmet_test_extent'
                    with assert_validation_errors('nvmet_namespace_create.device_path', in_use_msg):
                        with nvmet_namespace(subsys_id,
                                             file2,
                                             DEVICE_TYPE_FILE,
                                             filesize=MB_100,
                                             delete_options={'remove': True}):
                            pass
                    # Ensure we can't update using a FILE used by iSCSI
                    with assert_validation_errors('nvmet_namespace_update.device_path', in_use_msg):
                        call('nvmet.namespace.update', ns['id'], {'device_path': file2})

    def test__pool_export_import(self, fixture_port, loopback_client: NVMeCLIClient, zvol1):
        """
        Test that we can export and import a pool underlying subsystem namespaces.
        """
        nc = loopback_client

        zvol1_path = f'zvol/{zvol1["name"]}'
        with self.subsys(SUBSYS_NAME1, fixture_port, allow_any_host=True) as subsys:
            subsys_id = subsys['id']
            subsys_nqn = subsys['nqn']
            with nvmet_namespace(subsys_id, zvol1_path):
                # First ensure that we access the subsys with one namespace
                with nc.connect_ctx(subsys_nqn):
                    devices = nc.nvme_devices()
                    assert len(devices) == 1, devices
                    self.assert_subsys_namespaces(devices, subsys_nqn, [(1, ZVOL1_MB)])

                # Now create another pool
                with another_pool() as pool2:
                    # Test with a ZVOL based namespace
                    with zvol("pool2zvol1", 50, pool2['name']) as zvol_config:
                        with nvmet_namespace(subsys_id, f'zvol/{zvol_config["name"]}'):
                            with nc.connect_ctx(subsys_nqn):
                                devices = nc.nvme_devices()
                                assert len(devices) == 1, devices
                                self.assert_subsys_namespaces(devices, subsys_nqn, [(1, ZVOL1_MB), (2, 50)])
                            call("pool.export", pool2["id"], job=True)
                            with nc.connect_ctx(subsys_nqn):
                                devices = nc.nvme_devices()
                                assert len(devices) == 1, devices
                                self.assert_subsys_namespaces(devices, subsys_nqn, [(1, ZVOL1_MB)])
                            call('pool.import_pool', {'guid': pool2['guid']}, job=True)
                            with nc.connect_ctx(subsys_nqn):
                                devices = nc.nvme_devices()
                                assert len(devices) == 1, devices
                                self.assert_subsys_namespaces(devices, subsys_nqn, [(1, ZVOL1_MB), (2, 50)])
                    # Lookup the pool again, the id may have changed
                    try:
                        pool2 = call('pool.query', [['guid', '=', pool2['guid']]], {'get': True})
                    except MatchNotFound:
                        pass
                    # Test with a FILE based namespace
                    file2 = f'/mnt/{pool2["name"]}/file_{digits}'
                    with nvmet_namespace(subsys_id,
                                         file2,
                                         DEVICE_TYPE_FILE,
                                         filesize=MB_150,
                                         delete_options={'remove': True}):
                        with nc.connect_ctx(subsys_nqn):
                            devices = nc.nvme_devices()
                            assert len(devices) == 1, devices
                            self.assert_subsys_namespaces(devices, subsys_nqn, [(1, ZVOL1_MB), (2, 150)])
                        call("pool.export", pool2["id"], job=True)
                        with nc.connect_ctx(subsys_nqn):
                            devices = nc.nvme_devices()
                            assert len(devices) == 1, devices
                            self.assert_subsys_namespaces(devices, subsys_nqn, [(1, ZVOL1_MB)])
                        call('pool.import_pool', {'guid': pool2['guid']}, job=True)
                        with nc.connect_ctx(subsys_nqn):
                            devices = nc.nvme_devices()
                            assert len(devices) == 1, devices
                            self.assert_subsys_namespaces(devices, subsys_nqn, [(1, ZVOL1_MB), (2, 150)])

    def test__discovery_referrals(self, fixture_port, loopback_client: NVMeCLIClient):
        """
        Test that a client can see expected referrals.

        For HA this includes the implicit referral for a port when ANA is enabled.
        """
        assert call('nvmet.global.config')['xport_referral']
        port = fixture_port
        nc = loopback_client
        subsys1_nqn = f'{basenqn()}:{SUBSYS_NAME1}'
        DISCOVERY_DEFAULT_PORT = {
            'trtype': 'tcp',
            'adrfam': 'ipv4',
            'traddr': truenas_server.ip,
            'trsvcid': f'{NVME_DEFAULT_TCP_PORT}',
            'subnqn': DISCOVERY_NQN
        }
        SUBSYS1_DEFAULT_PORT = DISCOVERY_DEFAULT_PORT | {'subnqn': subsys1_nqn}
        DISCOVERY_ALT1_PORT = DISCOVERY_DEFAULT_PORT | {'trsvcid': f'{NVME_ALT1_TCP_PORT}'}
        SUBSYS1_ALT1_PORT = DISCOVERY_ALT1_PORT | {'subnqn': subsys1_nqn}
        with nvmet_subsys(SUBSYS_NAME1, allow_any_host=True) as subsys:
            subsys_id = subsys['id']
            with nvmet_port_subsys(subsys_id, port['id']):
                with nvmet_xport_referral(True):
                    data = nc.discover()
                    assert len(data['records']) == 2
                    assert self.discovery_present(data, DISCOVERY_DEFAULT_PORT)
                    assert self.discovery_present(data, SUBSYS1_DEFAULT_PORT)

                    # Add another port
                    with nvmet_port(truenas_server.ip, addr_trsvcid=NVME_ALT1_TCP_PORT) as port2:
                        with nvmet_port_subsys(subsys_id, port2['id']):
                            # Check that we can see each port point at the other
                            data = nc.discover()
                            assert len(data['records']) == 3
                            assert self.discovery_present(data, DISCOVERY_DEFAULT_PORT)
                            assert self.discovery_present(data, SUBSYS1_DEFAULT_PORT)
                            assert self.discovery_present(data, DISCOVERY_ALT1_PORT)
                            data = nc.discover(port=NVME_ALT1_TCP_PORT)
                            assert len(data['records']) == 3
                            assert self.discovery_present(data, DISCOVERY_DEFAULT_PORT)
                            assert self.discovery_present(data, SUBSYS1_ALT1_PORT)
                            assert self.discovery_present(data, DISCOVERY_ALT1_PORT)

                            # Turn off xport_referral
                            with nvmet_xport_referral(False):
                                # Check that we can see each port point at the other
                                data = nc.discover()
                                assert len(data['records']) == 2
                                assert self.discovery_present(data, DISCOVERY_DEFAULT_PORT)
                                assert self.discovery_present(data, SUBSYS1_DEFAULT_PORT)
                                data = nc.discover(port=NVME_ALT1_TCP_PORT)
                                assert len(data['records']) == 2
                                assert self.discovery_present(data, SUBSYS1_ALT1_PORT)
                                assert self.discovery_present(data, DISCOVERY_ALT1_PORT)

                            if ha:
                                data = nc.discover()
                                assert len(data['records']) == 3
                                assert self.discovery_present(data, DISCOVERY_DEFAULT_PORT)
                                assert self.discovery_present(data, SUBSYS1_DEFAULT_PORT)
                                assert self.discovery_present(data, DISCOVERY_ALT1_PORT)
                                data = nc.discover(port=NVME_ALT1_TCP_PORT)
                                assert len(data['records']) == 3
                                assert self.discovery_present(data, DISCOVERY_DEFAULT_PORT)
                                assert self.discovery_present(data, SUBSYS1_ALT1_PORT)
                                assert self.discovery_present(data, DISCOVERY_ALT1_PORT)
                                with nvmet_ana(True):
                                    # With ANA enabled we won't use the VIP
                                    for node_ip, other_node_ip in [(truenas_server.nodea_ip, truenas_server.nodeb_ip),
                                                                   (truenas_server.nodeb_ip, truenas_server.nodea_ip)]:
                                        this_node = {'traddr': node_ip}
                                        other_node = {'traddr': other_node_ip}
                                        data = nc.discover(addr=node_ip)
                                        assert len(data['records']) == 4
                                        assert self.discovery_present(data, DISCOVERY_DEFAULT_PORT | this_node)
                                        assert self.discovery_present(data, SUBSYS1_DEFAULT_PORT | this_node)
                                        assert self.discovery_present(data, DISCOVERY_ALT1_PORT | this_node)
                                        assert self.discovery_present(data, DISCOVERY_DEFAULT_PORT | other_node)
                                        data = nc.discover(addr=node_ip, port=NVME_ALT1_TCP_PORT)
                                        assert len(data['records']) == 4
                                        assert self.discovery_present(data, DISCOVERY_DEFAULT_PORT | this_node)
                                        assert self.discovery_present(data, SUBSYS1_ALT1_PORT | this_node)
                                        assert self.discovery_present(data, DISCOVERY_ALT1_PORT | this_node)
                                        assert self.discovery_present(data, DISCOVERY_ALT1_PORT | other_node)

    def test__connect_all_referrals(self, fixture_port, loopback_client: NVMeCLIClient, zvol1):
        """
        Test that when a client does a nvme connect-all, it adds the paths defined
        by the referrals.

        For HA this includes the implicit referral for a port when ANA is enabled.
        """
        assert call('nvmet.global.config')['xport_referral']
        nc = loopback_client
        zvol1_path = f'zvol/{zvol1["name"]}'
        with self.subsys(SUBSYS_NAME1, fixture_port, allow_any_host=True) as subsys1:
            subsys_id = subsys1['id']
            subsys_nqn = subsys1['nqn']
            with nvmet_namespace(subsys_id, zvol1_path):
                assert len(nc.nvme_list_subsys()) == 0
                with nc.connect_all_ctx():
                    data = nc.nvme_list_subsys()
                    assert self.subsys_path_count(data, subsys_nqn) == 1
                    assert self.subsys_path_present(data, subsys_nqn, truenas_server.ip, NVME_DEFAULT_TCP_PORT)
                assert len(nc.nvme_list_subsys()) == 0

                # Add another port
                with nvmet_port(truenas_server.ip, addr_trsvcid=NVME_ALT1_TCP_PORT) as port2:
                    with nvmet_port_subsys(subsys_id, port2['id']):
                        with nc.connect_all_ctx():
                            data = nc.nvme_list_subsys()
                            assert self.subsys_path_count(data, subsys_nqn) == 2
                            assert self.subsys_path_present(data, subsys_nqn, truenas_server.ip, NVME_DEFAULT_TCP_PORT)
                            assert self.subsys_path_present(data, subsys_nqn, truenas_server.ip, NVME_ALT1_TCP_PORT)

                        with nc.connect_all_ctx(port=NVME_ALT1_TCP_PORT):
                            data = nc.nvme_list_subsys()
                            assert self.subsys_path_count(data, subsys_nqn) == 2
                            assert self.subsys_path_present(data, subsys_nqn, truenas_server.ip, NVME_DEFAULT_TCP_PORT)
                            assert self.subsys_path_present(data, subsys_nqn, truenas_server.ip, NVME_ALT1_TCP_PORT)

                        # Check HA when xport_referral and ANA are both True
                        if ha:
                            with nvmet_ana(True):
                                # Need to determine which IP is active
                                match call('failover.node'):
                                    case 'A':
                                        active_ip = truenas_server.nodea_ip
                                        standby_ip = truenas_server.nodeb_ip
                                    case 'B':
                                        active_ip = truenas_server.nodeb_ip
                                        standby_ip = truenas_server.nodea_ip
                                    case _:
                                        assert False, 'Unexpected failover.node'
                                with nc.connect_all_ctx(active_ip):
                                    data = nc.nvme_list_subsys()
                                    assert self.subsys_path_count(data, subsys_nqn) == 4
                                    assert self.subsys_path_present(data, subsys_nqn, active_ip, NVME_DEFAULT_TCP_PORT)
                                    assert self.subsys_path_present(data, subsys_nqn, active_ip, NVME_ALT1_TCP_PORT)
                                    assert self.subsys_path_present(data, subsys_nqn, standby_ip, NVME_DEFAULT_TCP_PORT)
                                    assert self.subsys_path_present(data, subsys_nqn, standby_ip, NVME_ALT1_TCP_PORT)

                                with nc.connect_all_ctx(active_ip, NVME_ALT1_TCP_PORT):
                                    data = nc.nvme_list_subsys()
                                    assert self.subsys_path_count(data, subsys_nqn) == 4
                                    assert self.subsys_path_present(data, subsys_nqn, active_ip, NVME_DEFAULT_TCP_PORT)
                                    assert self.subsys_path_present(data, subsys_nqn, active_ip, NVME_ALT1_TCP_PORT)
                                    assert self.subsys_path_present(data, subsys_nqn, standby_ip, NVME_DEFAULT_TCP_PORT)
                                    assert self.subsys_path_present(data, subsys_nqn, standby_ip, NVME_ALT1_TCP_PORT)

                                with nc.connect_all_ctx(standby_ip):
                                    data = nc.nvme_list_subsys()
                                    assert self.subsys_path_count(data, subsys_nqn) == 4
                                    assert self.subsys_path_present(data, subsys_nqn, active_ip, NVME_DEFAULT_TCP_PORT)
                                    assert self.subsys_path_present(data, subsys_nqn, active_ip, NVME_ALT1_TCP_PORT)
                                    assert self.subsys_path_present(data, subsys_nqn, standby_ip, NVME_DEFAULT_TCP_PORT)
                                    assert self.subsys_path_present(data, subsys_nqn, standby_ip, NVME_ALT1_TCP_PORT)

                                with nc.connect_all_ctx(standby_ip, NVME_ALT1_TCP_PORT):
                                    data = nc.nvme_list_subsys()
                                    assert self.subsys_path_count(data, subsys_nqn) == 4
                                    assert self.subsys_path_present(data, subsys_nqn, active_ip, NVME_DEFAULT_TCP_PORT)
                                    assert self.subsys_path_present(data, subsys_nqn, active_ip, NVME_ALT1_TCP_PORT)
                                    assert self.subsys_path_present(data, subsys_nqn, standby_ip, NVME_DEFAULT_TCP_PORT)
                                    assert self.subsys_path_present(data, subsys_nqn, standby_ip, NVME_ALT1_TCP_PORT)

                            # ANA is off again
                            with nc.connect_all_ctx():
                                data = nc.nvme_list_subsys()
                                assert self.subsys_path_count(data, subsys_nqn) == 2
                                assert self.subsys_path_present(data, subsys_nqn,
                                                                truenas_server.ip, NVME_DEFAULT_TCP_PORT)
                                assert self.subsys_path_present(data, subsys_nqn,
                                                                truenas_server.ip, NVME_ALT1_TCP_PORT)

                        # Turn off xport_referral
                        with nvmet_xport_referral(False):
                            with nc.connect_all_ctx():
                                data = nc.nvme_list_subsys()
                                assert self.subsys_path_count(data, subsys_nqn) == 1
                                assert self.subsys_path_present(data, subsys_nqn,
                                                                truenas_server.ip, NVME_DEFAULT_TCP_PORT)

                            # Check HA when xport_referral is False and ANA is True
                            if ha:
                                with nvmet_ana(True):
                                    # Need to determine which IP is active
                                    match call('failover.node'):
                                        case 'A':
                                            active_ip = truenas_server.nodea_ip
                                            standby_ip = truenas_server.nodeb_ip
                                        case 'B':
                                            active_ip = truenas_server.nodeb_ip
                                            standby_ip = truenas_server.nodea_ip
                                        case _:
                                            assert False, 'Unexpected failover.node'
                                    with nc.connect_all_ctx(active_ip):
                                        data = nc.nvme_list_subsys()
                                        assert self.subsys_path_count(data, subsys_nqn) == 2
                                        assert self.subsys_path_present(data,
                                                                        subsys_nqn,
                                                                        active_ip,
                                                                        NVME_DEFAULT_TCP_PORT)
                                        assert self.subsys_path_present(data,
                                                                        subsys_nqn,
                                                                        standby_ip,
                                                                        NVME_DEFAULT_TCP_PORT)

                                    with nc.connect_all_ctx(active_ip, NVME_ALT1_TCP_PORT):
                                        data = nc.nvme_list_subsys()
                                        assert self.subsys_path_count(data, subsys_nqn) == 2
                                        assert self.subsys_path_present(data,
                                                                        subsys_nqn,
                                                                        active_ip,
                                                                        NVME_ALT1_TCP_PORT)
                                        assert self.subsys_path_present(data,
                                                                        subsys_nqn,
                                                                        standby_ip,
                                                                        NVME_ALT1_TCP_PORT)

                                    with nc.connect_all_ctx(standby_ip):
                                        data = nc.nvme_list_subsys()
                                        assert self.subsys_path_count(data, subsys_nqn) == 2
                                        assert self.subsys_path_present(data,
                                                                        subsys_nqn,
                                                                        active_ip,
                                                                        NVME_DEFAULT_TCP_PORT)
                                        assert self.subsys_path_present(data,
                                                                        subsys_nqn,
                                                                        standby_ip,
                                                                        NVME_DEFAULT_TCP_PORT)

                                    with nc.connect_all_ctx(standby_ip, NVME_ALT1_TCP_PORT):
                                        data = nc.nvme_list_subsys()
                                        assert self.subsys_path_count(data, subsys_nqn) == 2
                                        assert self.subsys_path_present(data,
                                                                        subsys_nqn,
                                                                        active_ip,
                                                                        NVME_ALT1_TCP_PORT)
                                        assert self.subsys_path_present(data,
                                                                        subsys_nqn,
                                                                        standby_ip,
                                                                        NVME_ALT1_TCP_PORT)

    def test__verbose_subsys_query(self, fixture_port, zvol1, zvol2):
        """
        Test that nvmet.subsys.query gives the correct additional information
        when options.extra.verbose is set.
        """
        KEYS = ['hosts', 'namespaces', 'ports']

        def subsys_query():
            return call('nvmet.subsys.query')

        def subsys_verbose_query():
            return call('nvmet.subsys.query', [], {'extra': {'verbose': True}})

        def check_regular_query(count):
            subsystems = subsys_query()
            assert len(subsystems) == count
            for subsys in subsystems:
                for key in KEYS:
                    assert key not in subsys
            return subsystems

        def check_verbose_query(count):
            subsystems = subsys_verbose_query()
            assert len(subsystems) == count
            for subsys in subsystems:
                for key in KEYS:
                    assert key in subsys
            return subsystems

        def pick_from_list_by_id(_list, _id):
            for item in _list:
                if item['id'] == _id:
                    return item

        zvol1_path = f'zvol/{zvol1["name"]}'
        zvol2_path = f'zvol/{zvol2["name"]}'

        assert len(subsys_query()) == 0
        assert len(subsys_verbose_query()) == 0

        # Add subsystem
        with nvmet_subsys(SUBSYS_NAME1) as subsys1:
            subsys1_id = subsys1['id']
            # with nvmet_port_subsys(subsys['id'], port['id']):
            # with self.subsys(SUBSYS_NAME1, fixture_port) as subsys1:

            check_regular_query(1)
            subsystems = check_verbose_query(1)
            for key in KEYS:
                assert len(subsystems[0][key]) == 0

            # Associate subsystem with port
            with nvmet_port_subsys(subsys1_id, fixture_port['id']):
                check_regular_query(1)
                subsystems = check_verbose_query(1)
                assert len(subsystems[0]['hosts']) == 0
                assert len(subsystems[0]['namespaces']) == 0
                assert len(subsystems[0]['ports']) == 1
                assert subsystems[0]['ports'][0] == fixture_port['id']

                # Add a host -> no change
                with nvmet_host(HOST1_NQN) as host1:
                    check_regular_query(1)
                    subsystems = check_verbose_query(1)
                    assert len(subsystems[0]['hosts']) == 0
                    assert len(subsystems[0]['namespaces']) == 0
                    assert len(subsystems[0]['ports']) == 1
                    assert subsystems[0]['ports'][0] == fixture_port['id']

                    # Associate the host -> change
                    with nvmet_host_subsys(host1['id'], subsys1_id):
                        check_regular_query(1)
                        subsystems = check_verbose_query(1)
                        assert len(subsystems[0]['hosts']) == 1
                        assert len(subsystems[0]['namespaces']) == 0
                        assert len(subsystems[0]['ports']) == 1
                        assert subsystems[0]['hosts'][0] == host1['id']
                        assert subsystems[0]['ports'][0] == fixture_port['id']

                        # Create/associate another host -> change
                        with nvmet_host(HOST2_NQN) as host2:
                            with nvmet_host_subsys(host2['id'], subsys1_id):
                                check_regular_query(1)
                                subsystems = check_verbose_query(1)
                                assert len(subsystems[0]['hosts']) == 2
                                assert len(subsystems[0]['namespaces']) == 0
                                assert len(subsystems[0]['ports']) == 1
                                assert host1['id'] in subsystems[0]['hosts']
                                assert host2['id'] in subsystems[0]['hosts']
                                assert subsystems[0]['ports'][0] == fixture_port['id']

                        # Back to only 1 host
                        check_regular_query(1)
                        subsystems = check_verbose_query(1)
                        assert len(subsystems[0]['hosts']) == 1
                        assert len(subsystems[0]['namespaces']) == 0
                        assert len(subsystems[0]['ports']) == 1
                        assert subsystems[0]['hosts'][0] == host1['id']
                        assert subsystems[0]['ports'][0] == fixture_port['id']

                        with nvmet_namespace(subsys1_id, zvol1_path) as ns1:
                            check_regular_query(1)
                            subsystems = check_verbose_query(1)
                            assert len(subsystems[0]['hosts']) == 1
                            assert len(subsystems[0]['namespaces']) == 1
                            assert len(subsystems[0]['ports']) == 1
                            assert subsystems[0]['hosts'][0] == host1['id']
                            assert subsystems[0]['namespaces'][0] == ns1['id']
                            assert subsystems[0]['ports'][0] == fixture_port['id']

                            # Add subsystem
                            with nvmet_subsys(SUBSYS_NAME2) as subsys2:
                                subsys2_id = subsys2['id']
                                check_regular_query(2)
                                subsystems = check_verbose_query(2)
                                ss1 = pick_from_list_by_id(subsystems, subsys1_id)
                                assert len(ss1['hosts']) == 1
                                assert len(ss1['namespaces']) == 1
                                assert len(ss1['ports']) == 1
                                assert ss1['hosts'][0] == host1['id']
                                assert ss1['namespaces'][0] == ns1['id']
                                assert ss1['ports'][0] == fixture_port['id']

                                ss2 = pick_from_list_by_id(subsystems, subsys2_id)
                                assert len(ss2['hosts']) == 0
                                assert len(ss2['namespaces']) == 0
                                assert len(ss2['ports']) == 0

                                with nvmet_namespace(subsys2_id, zvol2_path) as ns2:
                                    check_regular_query(2)
                                    subsystems = check_verbose_query(2)
                                    ss1 = pick_from_list_by_id(subsystems, subsys1_id)
                                    assert len(ss1['hosts']) == 1
                                    assert len(ss1['namespaces']) == 1
                                    assert len(ss1['ports']) == 1
                                    assert ss1['hosts'][0] == host1['id']
                                    assert ss1['namespaces'][0] == ns1['id']
                                    assert ss1['ports'][0] == fixture_port['id']

                                    ss2 = pick_from_list_by_id(subsystems, subsys2_id)
                                    assert len(ss2['hosts']) == 0
                                    assert len(ss2['namespaces']) == 1
                                    assert len(ss2['ports']) == 0
                                    assert ss2['namespaces'][0] == ns2['id']

                                # Now make a 2nd NS on the 1st subsys
                                with nvmet_namespace(subsys1_id, zvol2_path) as ns3:
                                    check_regular_query(2)
                                    subsystems = check_verbose_query(2)
                                    ss1 = pick_from_list_by_id(subsystems, subsys1_id)
                                    assert len(ss1['hosts']) == 1
                                    assert len(ss1['namespaces']) == 2
                                    assert len(ss1['ports']) == 1
                                    assert ss1['hosts'][0] == host1['id']
                                    assert ns1['id'] in ss1['namespaces']
                                    assert ns3['id'] in ss1['namespaces']
                                    assert ss1['ports'][0] == fixture_port['id']

                                    ss2 = pick_from_list_by_id(subsystems, subsys2_id)
                                    assert len(ss2['hosts']) == 0
                                    assert len(ss2['namespaces']) == 0
                                    assert len(ss2['ports']) == 0

    def test__port_validation(self, fixture_port):
        # Create -> duplicate
        with assert_validation_errors('nvmet_port_create.addr_traddr',
                                      'There already is a port using the same transport and address'):
            with nvmet_port(truenas_server.ip):
                pass

        # Update
        with nvmet_port(truenas_server.ip, 4444) as port2:
            with assert_validation_errors('nvmet_port_update.addr_traddr',
                                          'There already is a port using the same transport and address'):
                call('nvmet.port.update', port2['id'], {'addr_trsvcid': 4420})

            call('nvmet.port.update', port2['id'], {'addr_trsvcid': 4421})

            # Associate port with subsys
            with nvmet_subsys(SUBSYS_NAME1) as subsys:
                with nvmet_port_subsys(subsys['id'], port2['id']):
                    with assert_validation_errors('nvmet_port_update.addr_trsvcid',
                                                  'Cannot change addr_trsvcid on an active port.  '
                                                  'Disable first to allow change.'):
                        call('nvmet.port.update', port2['id'], {'addr_trsvcid': 4422})

                call('nvmet.port.update', port2['id'], {'addr_trsvcid': 4422})

            with assert_validation_errors('nvmet_port_update.addr_trtype',
                                          'This platform cannot support NVMe-oF(RDMA) or '
                                          'is missing an RDMA capable NIC.'):
                call('nvmet.port.update', port2['id'], {'addr_trtype': 'RDMA'})

    def test__ana_settings(self, fixture_port, loopback_client, zvol1, zvol2):
        """
        Test that the global ANA setting, and per-subsystem ANA settings
        perform as expected, wrt connectivity on HA systems.

        On non-HA these settings should not be functional.
        """
        nc = loopback_client

        if not ha:
            with assert_validation_errors('nvmet_global_update.ana',
                                          'This platform does not support Asymmetric Namespace Access(ANA).'):
                call('nvmet.global.update', {'ana': True})

        # Make two subsystems.  We will only modify the ANA setting of
        # subsystem 2
        with self.subsys(SUBSYS_NAME1,
                         fixture_port,
                         allow_any_host=True,
                         zvol_name=zvol1["name"]) as subsys1:
            with self.subsys(SUBSYS_NAME2,
                             fixture_port,
                             allow_any_host=True,
                             zvol_name=zvol2["name"]) as subsys2:
                subsys1_nqn = subsys1['nqn']
                subsys2_id = subsys2['id']
                subsys2_nqn = subsys2['nqn']

                if not ha:
                    with assert_validation_errors('nvmet_subsys_update.ana',
                                                  'This platform does not support Asymmetric Namespace Access(ANA).'):
                        call('nvmet.subsys.update', subsys2_id, {'ana': True})
                    # Now return from the test (for non-HA)
                    return

                # HA only - all ANA settings currently off
                #
                # Here are the setting combinations to be tested
                #     Global ANA | Subsystem ANA
                # 1.     False   |   None
                # 2.     False   |   False
                # 3.     False   |   True
                # 4.     True    |   None
                # 5.     True    |   False
                # 6.     True    |   True

                # Check which node is currently NASTER
                match call('failover.node'):
                    case 'A':
                        active_ip = truenas_server.nodea_ip
                        standby_ip = truenas_server.nodeb_ip
                    case 'B':
                        active_ip = truenas_server.nodeb_ip
                        standby_ip = truenas_server.nodea_ip
                    case _:
                        assert False, 'Unexpected failover.node'

                def assert_nqn_access(by_vip, nqn):
                    if by_vip:
                        with nc.connect_ctx(nqn):
                            pass
                        with pytest.raises(AssertionError):
                            with nc.connect_ctx(nqn, active_ip):
                                pass
                        with pytest.raises(AssertionError):
                            with nc.connect_ctx(nqn, standby_ip):
                                pass
                    else:
                        with pytest.raises(AssertionError):
                            with nc.connect_ctx(nqn):
                                pass
                        with nc.connect_ctx(nqn, active_ip):
                            pass
                        with nc.connect_ctx(nqn, standby_ip):
                            pass

                # 1.     False   |   None
                assert_nqn_access(True, subsys1_nqn)
                assert_nqn_access(True, subsys2_nqn)

                # 2.     False   |   False
                call('nvmet.subsys.update', subsys2_id, {'ana': False})
                assert_nqn_access(True, subsys1_nqn)
                assert_nqn_access(True, subsys2_nqn)

                # 3.     False   |   True
                call('nvmet.subsys.update', subsys2_id, {'ana': True})
                assert_nqn_access(True, subsys1_nqn)
                assert_nqn_access(False, subsys2_nqn)

                with nvmet_ana(True):
                    # 4.     True    |   None
                    call('nvmet.subsys.update', subsys2_id, {'ana': None})
                    assert_nqn_access(False, subsys1_nqn)
                    assert_nqn_access(False, subsys2_nqn)

                    # 5.     True    |   False
                    call('nvmet.subsys.update', subsys2_id, {'ana': False})
                    assert_nqn_access(False, subsys1_nqn)
                    assert_nqn_access(True, subsys2_nqn)

                    # 6.     True    |   True
                    call('nvmet.subsys.update', subsys2_id, {'ana': True})
                    assert_nqn_access(False, subsys1_nqn)
                    assert_nqn_access(False, subsys2_nqn)

    def test__global_sessions_loopback(self, fixture_port, loopback_client, zvol1, zvol2, hostnqn):
        """
        Test that session reporting seems reasonable when using a loopback client.
        """
        nc = loopback_client

        def assert_session(session, port_id, subsys_id, ip=truenas_server.ip):
            assert session['host_traddr'] == ip
            assert session['hostnqn'] == hostnqn
            assert session['port_id'] == port_id
            assert session['subsys_id'] == subsys_id

        # Make two subsystems.
        with self.subsys(SUBSYS_NAME1,
                         fixture_port,
                         allow_any_host=True,
                         zvol_name=zvol1["name"]) as subsys1:
            with self.subsys(SUBSYS_NAME2,
                             fixture_port,
                             allow_any_host=True,
                             zvol_name=zvol2["name"]) as subsys2:
                # Ensure no sessions are currently reported
                assert call('nvmet.global.sessions') == []
                assert call('nvmet.global.sessions', [['subsys_id', '=', subsys1['id']]]) == []
                assert call('nvmet.global.sessions', [['subsys_id', '=', subsys2['id']]]) == []

                # Now connect to one subsystem
                with nc.connect_ctx(subsys1['nqn']):
                    sessions = call('nvmet.global.sessions')
                    assert len(sessions) == 1
                    assert_session(sessions[0], fixture_port['id'], subsys1['id'])

                    sessions = call('nvmet.global.sessions', [['subsys_id', '=', subsys1['id']]])
                    assert len(sessions) == 1
                    assert_session(sessions[0], fixture_port['id'], subsys1['id'])

                    sessions = call('nvmet.global.sessions', [['subsys_id', '=', subsys2['id']]])
                    assert len(sessions) == 0

                    # Now connect to the other subsystem
                    with nc.connect_ctx(subsys2['nqn']):
                        sessions = call('nvmet.global.sessions')
                        assert len(sessions) == 2
                        if sessions[0]['subsys_id'] == subsys1['id']:
                            assert_session(sessions[0], fixture_port['id'], subsys1['id'])
                            assert_session(sessions[1], fixture_port['id'], subsys2['id'])
                        else:
                            assert_session(sessions[0], fixture_port['id'], subsys2['id'])
                            assert_session(sessions[1], fixture_port['id'], subsys1['id'])

                        sessions = call('nvmet.global.sessions', [['subsys_id', '=', subsys1['id']]])
                        assert len(sessions) == 1
                        assert_session(sessions[0], fixture_port['id'], subsys1['id'])

                        sessions = call('nvmet.global.sessions', [['subsys_id', '=', subsys2['id']]])
                        assert len(sessions) == 1
                        assert_session(sessions[0], fixture_port['id'], subsys2['id'])

                    # Back to only having one session
                    wait_for_session_count(1)
                    sessions = call('nvmet.global.sessions')
                    assert len(sessions) == 1
                    assert_session(sessions[0], fixture_port['id'], subsys1['id'])

                    sessions = call('nvmet.global.sessions', [['subsys_id', '=', subsys1['id']]])
                    assert len(sessions) == 1
                    assert_session(sessions[0], fixture_port['id'], subsys1['id'])

                    sessions = call('nvmet.global.sessions', [['subsys_id', '=', subsys2['id']]])
                    assert len(sessions) == 0

                # back to having no sessions
                wait_for_session_count(0)
                assert call('nvmet.global.sessions') == []
                assert call('nvmet.global.sessions', [['subsys_id', '=', subsys1['id']]]) == []
                assert call('nvmet.global.sessions', [['subsys_id', '=', subsys2['id']]]) == []


class TestNVMeHostAuth(NVMeRunning):

    @pytest.fixture(scope='class')
    def fixture_port(self, fixture_nvmet_running):
        assert truenas_server.ip in call('nvmet.port.transport_address_choices', 'TCP')
        with nvmet_port(truenas_server.ip) as port:
            yield port

    @pytest.fixture(scope='class')
    def hostnqn(self, loopback_client: NVMeCLIClient) -> str:
        return loopback_client.hostnqn()

    @pytest.fixture(scope='class')
    def host_auth_fixture(self, zvol1, hostnqn, fixture_port):
        zvol1_path = f'zvol/{zvol1["name"]}'
        with self.subsys(SUBSYS_NAME1, fixture_port) as subsys1:
            subsys_id = subsys1['id']
            with nvmet_namespace(subsys_id, zvol1_path):
                with nvmet_host(hostnqn) as host:
                    with nvmet_host_subsys(host['id'], subsys_id):
                        yield subsys1 | {'host_id': host['id'], 'host': host}

    @pytest.mark.parametrize('group,hash,bidirectional', itertools.product(DHCHAP_DHGROUP_API_RANGE,
                                                                           DHCHAP_HASH_API_RANGE,
                                                                           [False, True]))
    def test__host_auth(self, group, hash, bidirectional, loopback_client, host_auth_fixture, hostnqn):
        nc = loopback_client
        subnqn = host_auth_fixture['nqn']

        dhchap_secret = call('nvmet.host.generate_key', hash, hostnqn)
        dhchap_ctrl_secret = call('nvmet.host.generate_key', hash, hostnqn) if bidirectional else None
        payload = {
            'dhchap_dhgroup': group,
            'dhchap_hash': hash,
            'dhchap_key': dhchap_secret,
            'dhchap_ctrl_key': dhchap_ctrl_secret
        }
        call('nvmet.host.update', host_auth_fixture['host_id'], payload)
        # First ensure that without supplying credentials we cannot connect.
        with pytest.raises(AssertionError):
            with nc.connect_ctx(subnqn):
                pass

        # Then verify that with the correct creds, we CAN connect
        self.assert_single_namespace(nc, subnqn, ZVOL1_MB, dhchap_secret=dhchap_secret,
                                     dhchap_ctrl_secret=dhchap_ctrl_secret)

    def test__host_dhchap_dhgroup_choices(self):
        assert set(call('nvmet.host.dhchap_dhgroup_choices')) == set(['2048-BIT',
                                                                      '3072-BIT',
                                                                      '4096-BIT',
                                                                      '6144-BIT',
                                                                      '8192-BIT'])

    def test__host_dhchap_hash_choices(self):
        assert set(call('nvmet.host.dhchap_hash_choices')) == set(['SHA-256',
                                                                   'SHA-384',
                                                                   'SHA-512'])


class TestForceDelete(NVMeRunning):

    def test__host_force_delete(self, fixture_nvmet_running):
        """
        Verify that trying to delete a host linked to a subsys will
        raise an excception.  Also verify that force option works.
        """
        def _expected_msg(subsystems):
            count = len(subsystems)
            match count:
                case 1:
                    return f'Host {FAKE_HOSTNQN} used by 1 subsystem: {SUBSYS_NAME1}'
                case 2 | 3:
                    return f'Host {FAKE_HOSTNQN} used by {count} subsystems: {",".join(subsystems)}'
                case _:
                    return f'Host {FAKE_HOSTNQN} used by {count} subsystems: {",".join(subsystems)},...'

        with nvmet_subsys(SUBSYS_NAME1) as subsys1:
            with nvmet_host(FAKE_HOSTNQN, delete_exist_precheck=True) as host:
                assert len(call('nvmet.host.query')) == 1
                # Not linked then we can delete
                call('nvmet.host.delete', host['id'])
                assert len(call('nvmet.host.query')) == 0
            with nvmet_host(FAKE_HOSTNQN, delete_exist_precheck=True) as host:
                host_id = host['id']
                assert len(call('nvmet.host.query')) == 1
                with nvmet_host_subsys(host_id, subsys1['id'], delete_exist_precheck=True):
                    # Linked then we cannot delete
                    with assert_validation_errors('nvmet_host_delete.id',
                                                  _expected_msg([SUBSYS_NAME1])):
                        call('nvmet.host.delete', host_id)
                    assert len(call('nvmet.host.query')) == 1
                    with nvmet_subsys(SUBSYS_NAME2) as subsys2:
                        with nvmet_host_subsys(host_id, subsys2['id']):
                            with assert_validation_errors('nvmet_host_delete.id',
                                                          _expected_msg([SUBSYS_NAME1,
                                                                         SUBSYS_NAME2])):
                                call('nvmet.host.delete', host_id)
                                with nvmet_subsys(SUBSYS_NAME3) as subsys3:
                                    with nvmet_host_subsys(host_id, subsys3['id']):
                                        with assert_validation_errors('nvmet_host_delete.id',
                                                                      _expected_msg([SUBSYS_NAME1,
                                                                                     SUBSYS_NAME2,
                                                                                     SUBSYS_NAME3])):
                                            call('nvmet.host.delete', host_id)
                                            with nvmet_subsys(SUBSYS_NAME4) as subsys4:
                                                with nvmet_host_subsys(host_id, subsys4['id']):
                                                    with assert_validation_errors('nvmet_host_delete.id',
                                                                                  _expected_msg([SUBSYS_NAME1,
                                                                                                 SUBSYS_NAME2,
                                                                                                 SUBSYS_NAME3,
                                                                                                 SUBSYS_NAME4])):

                                                        call('nvmet.host.delete', host_id)
                    assert len(call('nvmet.host.query')) == 1
                    # Linked then we cannot delete
                    with assert_validation_errors('nvmet_host_delete.id',
                                                  f'Host {FAKE_HOSTNQN} used by 1 subsystem: {SUBSYS_NAME1}'):
                        call('nvmet.host.delete', host_id)
                    assert len(call('nvmet.host.query')) == 1
                    # Force the deletion
                    call('nvmet.host.delete', host_id, {'force': True})
                    assert len(call('nvmet.host.query')) == 0
                    assert len(call('nvmet.subsys.query')) == 1
            assert len(call('nvmet.subsys.query')) == 1
        assert len(call('nvmet.subsys.query')) == 0

    def test__port_force_delete(self, fixture_nvmet_running):
        """
        Verify that trying to delete a port that has a subsys mapped will
        raise an excception.  Also verify that force option works.
        """
        # Because we expect the port and port_subsys to be deleted on
        # a force, we add delete_exist_precheck option to the calls of the
        # relevant context managers (so that they don't throw exceptions
        # themselves).
        with nvmet_port(truenas_server.ip, delete_exist_precheck=True) as port:
            with nvmet_subsys(SUBSYS_NAME1) as subsys:
                with nvmet_port_subsys(subsys['id'], port['id'], delete_exist_precheck=True) as port_subsys:
                    assert 1 == call('nvmet.port_subsys.query', [['id', '=', port_subsys['id']]], {'count': True})
                    # Now try to delete the port -> fails
                    with assert_validation_errors('nvmet_port_delete.id',
                                                  f'Port #1 used by 1 subsystem: {SUBSYS_NAME1}'):
                        call('nvmet.port.delete', port['id'])
                    # Force delete the port
                    call('nvmet.port.delete', port['id'], {'force': True})

                    # Ensure that the associated port_subsys has also been deleted
                    assert 0 == call('nvmet.port_subsys.query', [['id', '=', port_subsys['id']]], {'count': True})

    def test__subsys_force_delete(self, fixture_nvmet_running, zvol1, zvol2, zvol3, zvol4):
        """
        Verify that trying to delete a subsys that has an attached namespace
        will raise an excception.  Also verify that force option works.
        """
        # Because we expect the port and port_subsys to be deleted on
        # a force, we add delete_exist_precheck option to the calls of the
        # relevant context managers (so that they don't throw exceptions
        # themselves).
        with nvmet_subsys(SUBSYS_NAME1, delete_exist_precheck=True) as subsys:
            subsys_id = subsys['id']
            with nvmet_namespace(subsys_id, f'zvol/{zvol1["name"]}', delete_exist_precheck=True):
                # Because of the way that foreign keys get expanded we query using
                # 'subsys.id' rather than 'subsys_id'
                assert 1 == call('nvmet.namespace.query', [['subsys.id', '=', subsys_id]], {'count': True})
                # Now try to delete the subsys -> fails
                with assert_validation_errors('nvmet_subsys_delete.id',
                                              f'Subsystem {SUBSYS_NAME1} contains 1 namespace: 1'):
                    call('nvmet.subsys.delete', subsys_id)

                with nvmet_namespace(subsys_id, f'zvol/{zvol2["name"]}'):
                    assert 2 == call('nvmet.namespace.query', [['subsys.id', '=', subsys_id]], {'count': True})
                    with assert_validation_errors('nvmet_subsys_delete.id',
                                                  f'Subsystem {SUBSYS_NAME1} contains 2 namespaces: 1,2'):
                        call('nvmet.subsys.delete', subsys_id)

                    with nvmet_namespace(subsys_id, f'zvol/{zvol3["name"]}', nsid=10):
                        assert 3 == call('nvmet.namespace.query', [['subsys.id', '=', subsys_id]], {'count': True})
                        with assert_validation_errors('nvmet_subsys_delete.id',
                                                      f'Subsystem {SUBSYS_NAME1} contains 3 namespaces: 1,2,10'):
                            call('nvmet.subsys.delete', subsys_id)

                        with nvmet_namespace(subsys_id, f'zvol/{zvol4["name"]}'):
                            assert 4 == call('nvmet.namespace.query', [['subsys.id', '=', subsys_id]], {'count': True})
                            with assert_validation_errors('nvmet_subsys_delete.id',
                                                          f'Subsystem {SUBSYS_NAME1} contains 4 namespaces: 1,2,3,...'):
                                call('nvmet.subsys.delete', subsys_id)

                assert 1 == call('nvmet.namespace.query', [['subsys.id', '=', subsys_id]], {'count': True})

                # Force delete the subsys
                call('nvmet.subsys.delete', subsys_id, {'force': True})

                # Ensure that the associated namespace has also been deleted
                assert 0 == call('nvmet.namespace.query', [['subsys.id', '=', subsys_id]], {'count': True})


class TestManySubsystems:
    SUBSYS_COUNT = 100
    TIME_LIMIT_SECONDS = 15
    DELAY_SECONDS = 3

    @pytest.fixture(scope='class')
    def fixture_port(self):
        if truenas_server.ip is None:
            init_truenas_server()
        assert truenas_server.ip in call('nvmet.port.transport_address_choices', 'TCP')
        with nvmet_port(truenas_server.ip) as port:
            yield port

    @pytest.fixture(scope='class')
    def fixture_100_nvme_subsystems(self, fixture_port):
        with contextlib.ExitStack() as es:
            for i in range(self.SUBSYS_COUNT):
                filename = f'/mnt/{pool_name}/file{i}'
                subsys_config = es.enter_context(nvmet_subsys(f'bar{i}', allow_any_host=True))
                es.enter_context(nvmet_port_subsys(subsys_config['id'], fixture_port['id']))
                es.enter_context(nvmet_namespace(subsys_config['id'],
                                                 filename,
                                                 DEVICE_TYPE_FILE,
                                                 filesize=MB_10,
                                                 delete_options={'remove': True}))
            yield

    def test__start_many_nvme(self, loopback_client: NVMeCLIClient, fixture_100_nvme_subsystems):
        nc = loopback_client
        with pytest.raises(AssertionError, match='Connection refused'):
            nc.discover()
        # We want to be sure that the service starts in a reasonable amount of time.
        start_time = time.time()
        with ensure_service_started(SERVICE_NAME, self.DELAY_SECONDS):
            end_time = time.time()
            assert end_time - start_time < self.TIME_LIMIT_SECONDS + self.DELAY_SECONDS
            # Even if we started, let's make sure can see all the subsystems
            # One extra for the discovery target.
            res = nc.discover()
            assert len(res['records']) == self.SUBSYS_COUNT + 1
