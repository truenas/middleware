import contextlib
import copy
import errno

import pytest
from assets.websocket.iscsi import target, target_extent_associate, zvol_extent
from assets.websocket.pool import zvol
from auto_config import ha, pool_name

from middlewared.service_exception import InstanceNotFound, ValidationError, ValidationErrors
from middlewared.test.integration.assets.alert import AlertMixin
from middlewared.test.integration.utils import call, mock, ssh

REL_TGT_ID_FC_OFFSET = 5000

SLOT_0 = 'CPU SLOT4 PCI-E 3.0 X16 / PCI Function 0'
SLOT_1 = 'CPU SLOT4 PCI-E 3.0 X16 / PCI Function 1'
SLOT_2 = 'CPU SLOT5 PCI-E 3.0 X16 / PCI Function 0'
SLOT_3 = 'CPU SLOT5 PCI-E 3.0 X16 / PCI Function 1'


NODE_A_0_WWPN = '0x210000aaaaaaaa01'
NODE_A_0_WWPN_NPIV_1 = '0x220000aaaaaaaa01'
NODE_A_0 = {
    'name': 'host14',
    'path': '/sys/class/fc_host/host14',
    'node_name': '0x200000aaaaaaaa01',
    'port_name': NODE_A_0_WWPN,
    'port_type': 'NPort (fabric via point-to-point)',
    'port_state': 'Online',
    'model': 'QLE2692',
    'speed': '8 Gbit',
    'addr': 'pci0000:b2/0000:b2:00.0/0000:b3:00.0',
    'max_npiv_vports': 254,
    'npiv_vports_inuse': 0,
    'physical': True,
    'slot': SLOT_0
}

NODE_A_1_WWPN = '0x210000aaaaaaaa02'
NODE_A_1 = {
    'name': 'host16',
    'path': '/sys/class/fc_host/host16',
    'node_name': '0x200000aaaaaaaa02',
    'port_name': NODE_A_1_WWPN,
    'port_type': 'NPort (fabric via point-to-point)',
    'port_state': 'Online',
    'model': 'QLE2692',
    'speed': '8 Gbit',
    'addr': 'pci0000:b2/0000:b2:00.0/0000:b3:00.1',
    'max_npiv_vports': 254,
    'npiv_vports_inuse': 0,
    'physical': True,
    'slot': SLOT_1
}

NODE_A_2_WWPN = '0x210000aaaaaaaa03'
NODE_A_2 = {
    'name': 'host17',
    'path': '/sys/class/fc_host/host17',
    'node_name': '0x200000aaaaaaaa03',
    'port_name': NODE_A_2_WWPN,
    'port_type': 'NPort (fabric via point-to-point)',
    'port_state': 'Online',
    'model': 'QLE2692',
    'speed': '8 Gbit',
    'addr': 'pci0000:b2/0000:b2:00.0/0000:b4:00.1',
    'max_npiv_vports': 254,
    'npiv_vports_inuse': 0,
    'physical': True,
    'slot': SLOT_2
}

NODE_A_3_WWPN = '0x210000aaaaaaaa04'
NODE_A_3 = {
    'name': 'host17',
    'path': '/sys/class/fc_host/host18',
    'node_name': '0x200000aaaaaaaa04',
    'port_name': NODE_A_3_WWPN,
    'port_type': 'NPort (fabric via point-to-point)',
    'port_state': 'Online',
    'model': 'QLE2692',
    'speed': '8 Gbit',
    'addr': 'pci0000:b2/0000:b2:00.0/0000:b4:00.2',
    'max_npiv_vports': 254,
    'npiv_vports_inuse': 0,
    'physical': True,
    'slot': SLOT_3
}


NODE_A_FC_PHYSICAL_PORTS = [NODE_A_0, NODE_A_1]

NODE_B_0_WWPN = '0x210000bbbbbbbb01'
NODE_B_0_WWPN_NPIV_1 = '0x220000bbbbbbbb01'
NODE_B_0 = {
    'name': 'host14',
    'path': '/sys/class/fc_host/host14',
    'node_name': '0x200000bbbbbbbb01',
    'port_name': NODE_B_0_WWPN,
    'port_type': 'NPort (fabric via point-to-point)',
    'port_state': 'Online',
    'model': 'QLE2692',
    'speed': '8 Gbit',
    'addr': 'pci0000:b2/0000:b2:00.0/0000:b3:00.0',
    'max_npiv_vports': 254,
    'npiv_vports_inuse': 0,
    'physical': True,
    'slot': SLOT_0
}

NODE_B_1_WWPN = '0x210000bbbbbbbb02'
NODE_B_1 = {
    'name': 'host16',
    'path': '/sys/class/fc_host/host16',
    'node_name': '0x200000bbbbbbbb02',
    'port_name': NODE_B_1_WWPN,
    'port_type': 'NPort (fabric via point-to-point)',
    'port_state': 'Online',
    'model': 'QLE2692',
    'speed': '8 Gbit',
    'addr': 'pci0000:b2/0000:b2:00.0/0000:b3:00.1',
    'max_npiv_vports': 254,
    'npiv_vports_inuse': 0,
    'physical': True,
    'slot': SLOT_1
}

NODE_B_2_WWPN = '0x210000bbbbbbbb03'
NODE_B_2 = {
    'name': 'host17',
    'path': '/sys/class/fc_host/host17',
    'node_name': '0x200000bbbbbbbb03',
    'port_name': NODE_B_2_WWPN,
    'port_type': 'NPort (fabric via point-to-point)',
    'port_state': 'Online',
    'model': 'QLE2692',
    'speed': '8 Gbit',
    'addr': 'pci0000:b2/0000:b2:00.0/0000:b4:00.1',
    'max_npiv_vports': 254,
    'npiv_vports_inuse': 0,
    'physical': True,
    'slot': SLOT_2
}

NODE_B_3_WWPN = '0x210000bbbbbbbb04'
NODE_B_3 = {
    'name': 'host18',
    'path': '/sys/class/fc_host/host18',
    'node_name': '0x200000bbbbbbbb04',
    'port_name': NODE_B_3_WWPN,
    'port_type': 'NPort (fabric via point-to-point)',
    'port_state': 'Online',
    'model': 'QLE2692',
    'speed': '8 Gbit',
    'addr': 'pci0000:b2/0000:b2:00.0/0000:b4:00.2',
    'max_npiv_vports': 254,
    'npiv_vports_inuse': 0,
    'physical': True,
    'slot': SLOT_3
}

NODE_B_FC_PHYSICAL_PORTS = [NODE_B_0, NODE_B_1]

NO_SLOT_NODE_A_0_WWPN = '0x210011aa22bb1864'
NO_SLOT_NODE_A_1_WWPN = '0x210011aa22bb1865'
NO_SLOT_NODE_A_2_WWPN = '0x210012345678bde4'
NO_SLOT_NODE_A_3_WWPN = '0x210012345678bde5'
NO_SLOT_NODE_A_4_WWPN = '0x210012345678bde6'
NO_SLOT_NODE_A_5_WWPN = '0x210012345678bde7'

NO_SLOT_NODE_A_FC_PHYSICAL_PORTS = [
    {
        'name': 'host5',
        'path': '/sys/class/fc_host/host5',
        'node_name': '0x200012345678bde7',
        'port_name': NO_SLOT_NODE_A_5_WWPN,
        'port_type': 'Unknown',
        'port_state': 'Linkdown',
        'model': 'QLE2694L',
        'speed': 'unknown',
        'addr': 'pci0000:00/0000:00:03.1/0000:09:00.3',
        'max_npiv_vports': 254,
        'npiv_vports_inuse': 0,
        'physical': True
    },
    {
        'name': 'host3',
        'path': '/sys/class/fc_host/host3',
        'node_name': '0x200012345678bde5',
        'port_name': NO_SLOT_NODE_A_3_WWPN,
        'port_type': 'Unknown',
        'port_state': 'Linkdown',
        'model': 'QLE2694L',
        'speed': 'unknown',
        'addr': 'pci0000:00/0000:00:03.1/0000:09:00.1',
        'max_npiv_vports': 254,
        'npiv_vports_inuse': 0,
        'physical': True
    },
    {
        'name': 'host1',
        'path': '/sys/class/fc_host/host1',
        'node_name': '0x200011aa22bb1865',
        'port_name': NO_SLOT_NODE_A_1_WWPN,
        'port_type': 'Unknown',
        'port_state': 'Linkdown',
        'model': 'QLE2742',
        'speed': 'unknown',
        'addr': 'pci0000:80/0000:80:03.1/0000:87:00.1',
        'max_npiv_vports': 254,
        'npiv_vports_inuse': 0,
        'physical': True
    },
    {
        'name': 'host4',
        'path': '/sys/class/fc_host/host4',
        'node_name': '0x200012345678bde6',
        'port_name': NO_SLOT_NODE_A_4_WWPN,
        'port_type': 'Unknown',
        'port_state': 'Linkdown',
        'model': 'QLE2694L',
        'speed': 'unknown',
        'addr': 'pci0000:00/0000:00:03.1/0000:09:00.2',
        'max_npiv_vports': 254,
        'npiv_vports_inuse': 0,
        'physical': True
    },
    {
        'name': 'host2',
        'path': '/sys/class/fc_host/host2',
        'node_name': '0x200012345678bde4',
        'port_name': NO_SLOT_NODE_A_2_WWPN,
        'port_type': 'Unknown',
        'port_state': 'Linkdown',
        'model': 'QLE2694L',
        'speed': 'unknown',
        'addr': 'pci0000:00/0000:00:03.1/0000:09:00.0',
        'max_npiv_vports': 254,
        'npiv_vports_inuse': 0,
        'physical': True
    },
    {
        'name': 'host0',
        'path': '/sys/class/fc_host/host0',
        'node_name': '0x200011aa22bb1864',
        'port_name': NO_SLOT_NODE_A_0_WWPN,
        'port_type': 'Unknown',
        'port_state': 'Linkdown',
        'model': 'QLE2742',
        'speed': 'unknown',
        'addr': 'pci0000:80/0000:80:03.1/0000:87:00.0',
        'max_npiv_vports': 254,
        'npiv_vports_inuse': 0,
        'physical': True
    }
]

NO_SLOT_NODE_B_0_WWPN = '0x210011aa22bb18f8'
NO_SLOT_NODE_B_1_WWPN = '0x210011aa22bb18f9'
NO_SLOT_NODE_B_2_WWPN = '0x210012345678bd54'
NO_SLOT_NODE_B_3_WWPN = '0x210012345678bd55'
NO_SLOT_NODE_B_4_WWPN = '0x210012345678bd56'
NO_SLOT_NODE_B_5_WWPN = '0x210012345678bd57'

NO_SLOT_NODE_B_FC_PHYSICAL_PORTS = [
    {
        'name': 'host5',
        'path': '/sys/class/fc_host/host5',
        'node_name': '0x200012345678bd57',
        'port_name': NO_SLOT_NODE_B_5_WWPN,
        'port_type': 'Unknown',
        'port_state': 'Linkdown',
        'model': 'QLE2694L',
        'speed': 'unknown',
        'addr': 'pci0000:00/0000:00:03.1/0000:09:00.3',
        'max_npiv_vports': 254,
        'npiv_vports_inuse': 0,
        'physical': True
    },
    {
        'name': 'host3',
        'path': '/sys/class/fc_host/host3',
        'node_name': '0x200012345678bd55',
        'port_name': NO_SLOT_NODE_B_3_WWPN,
        'port_type': 'Unknown',
        'port_state': 'Linkdown',
        'model': 'QLE2694L',
        'speed': 'unknown',
        'addr': 'pci0000:00/0000:00:03.1/0000:09:00.1',
        'max_npiv_vports': 254,
        'npiv_vports_inuse': 0,
        'physical': True
    },
    {
        'name': 'host1',
        'path': '/sys/class/fc_host/host1',
        'node_name': '0x200011aa22bb18f9',
        'port_name': NO_SLOT_NODE_B_1_WWPN,
        'port_type': 'Unknown',
        'port_state': 'Linkdown',
        'model': 'QLE2742',
        'speed': 'unknown',
        'addr': 'pci0000:80/0000:80:03.1/0000:8d:00.1',
        'max_npiv_vports': 254,
        'npiv_vports_inuse': 0,
        'physical': True
    },
    {
        'name': 'host4',
        'path': '/sys/class/fc_host/host4',
        'node_name': '0x200012345678bd56',
        'port_name': NO_SLOT_NODE_B_4_WWPN,
        'port_type': 'Unknown',
        'port_state': 'Linkdown',
        'model': 'QLE2694L',
        'speed': 'unknown',
        'addr': 'pci0000:00/0000:00:03.1/0000:09:00.2',
        'max_npiv_vports': 254,
        'npiv_vports_inuse': 0,
        'physical': True
    },
    {
        'name': 'host2',
        'path': '/sys/class/fc_host/host2',
        'node_name': '0x200012345678bd54',
        'port_name': NO_SLOT_NODE_B_2_WWPN,
        'port_type': 'Unknown',
        'port_state': 'Linkdown',
        'model': 'QLE2694L',
        'speed': 'unknown',
        'addr': 'pci0000:00/0000:00:03.1/0000:09:00.0',
        'max_npiv_vports': 254,
        'npiv_vports_inuse': 0,
        'physical': True
    },
    {
        'name': 'host0',
        'path': '/sys/class/fc_host/host0',
        'node_name': '0x200011aa22bb18f8',
        'port_name': NO_SLOT_NODE_B_0_WWPN,
        'model': 'QLE2742',
        'port_type': 'Unknown',
        'port_state': 'Linkdown',
        'speed': 'unknown',
        'addr': 'pci0000:80/0000:80:03.1/0000:8d:00.0',
        'max_npiv_vports': 254,
        'npiv_vports_inuse': 0,
        'physical': True
    }
]


@pytest.fixture
def clear_ratelimit():
    call('rate.limit.cache_clear')
    if ha:
        call('failover.call_remote', 'rate.limit.cache_clear')


def _str_to_naa(string):
    if isinstance(string, str):
        if string.startswith('0x'):
            return 'naa.' + string[2:]


def str_to_wwpn_naa(string):
    return _str_to_naa(string)


def str_to_wwpn_b_naa(string):
    if ha:
        return _str_to_naa(string)


def str_to_colon_hex(string):
    if isinstance(string, str) and string.startswith('0x'):
        # range(2,) to skip the leading 0x
        return ':'.join(string[i:i + 2] for i in range(2, len(string), 2))


def parse_values(lines):
    values = {'LUN': {}}
    while lines:
        line = lines.pop(0).strip()
        if line == '}':
            return values
        elif line == '' or line.startswith('#'):
            continue
        sline = line.split()
        if sline[0] == 'LUN':
            values['LUN'][sline[1]] = sline[2]
        elif len(sline) == 2:
            values[sline[0]] = sline[1]


def parse_targets(lines):
    targets = {}
    while lines:
        line = lines.pop(0).strip()
        if line.startswith('TARGET '):
            ident = line.split()[1]
            targets[ident] = parse_values(lines)
        elif line == '}':
            return targets


def parse_target_driver(target_driver, lines):
    needle = f'TARGET_DRIVER {target_driver} ' + '{'
    while lines:
        line = lines.pop(0).strip()
        if line == needle:
            targets = parse_targets(lines)
            return targets


def parse_qla2x00t(lines):
    return parse_target_driver('qla2x00t', copy.copy(lines))


def parse_iscsi(lines):
    return parse_target_driver('iscsi', copy.copy(lines))


@contextlib.contextmanager
def target_lun(target_config, zvol_name, mb, lun):
    with zvol(zvol_name, mb, pool_name) as zvol_config:
        with zvol_extent(zvol_config['id'], zvol_name) as extent_config:
            with target_extent_associate(target_config['id'], extent_config['id'], lun) as associate_config:
                yield {
                    'target': target_config,
                    'zvol': zvol_config,
                    'extent': extent_config,
                    'associate': associate_config
                }


@contextlib.contextmanager
def target_lun_zero(target_name, zvol_name, mb):
    with target(target_name, []) as target_config:
        with target_lun(target_config, zvol_name, mb, 0) as config:
            yield config


@contextlib.contextmanager
def node_hardware(physical_ports, remote=False):
    with mock('fc.fc_hosts', return_value=physical_ports, remote=remote):
        physical_port_filter = [['physical', '=', True]]
        with mock('fc.fc_hosts', args=physical_port_filter, return_value=physical_ports, remote=remote):
            yield


@contextlib.contextmanager
def mock_ports(node_a_physical_ports, node_b_physical_ports):
    if ha:
        node = call('failover.node')
        if node == 'A':
            with node_hardware(node_a_physical_ports):
                with node_hardware(node_b_physical_ports, True):
                    yield
        else:
            with node_hardware(node_a_physical_ports, True):
                with node_hardware(node_b_physical_ports):
                    yield
    else:
        with node_hardware(node_a_physical_ports):
            yield


@contextlib.contextmanager
def set_fchost_npiv(id_: int, value: int):
    original_value = call('fc.fc_host.query', [['id', '=', id_]], {'get': True})['npiv']
    try:
        call('fc.fc_host.update', id_, {'npiv': value})
        yield
    finally:
        call('fc.fc_host.update', id_, {'npiv': original_value})


def fc_target_rel_tgt_id(rel_tgt_id, alias):
    try:
        per_hba = int(alias.split('/')[0][2:]) * 1000
    except Exception:
        per_hba = 0
    return rel_tgt_id + REL_TGT_ID_FC_OFFSET + per_hba


def unmock_ports():
    physical_port_filter = [['physical', '=', True]]
    call('test.remove_mock', 'fc.fc_hosts', None)
    call('test.remove_mock', 'fc.fc_hosts', physical_port_filter)
    if ha:
        call('failover.call_remote', 'test.remove_mock', ['fc.fc_hosts', None])
        call('failover.call_remote', 'test.remove_mock', ['fc.fc_hosts', physical_port_filter])


@contextlib.contextmanager
def remock_ports(node_a_physical_ports, node_b_physical_ports):
    unmock_ports()
    with mock_ports(node_a_physical_ports, node_b_physical_ports):
        # Normally changing the hardware would have required rebooting the controllers, which
        # would clear cache.  Do that now.
        call('cache.pop', 'fc.fc_host_nport_wwpn_choices')
        call('cache.pop', 'fc.fc_host.hbas_changed')
        if ha:
            call('failover.call_remote', 'cache.pop', ['fc.fc_host_nport_wwpn_choices'])
            call('failover.call_remote', 'cache.pop', ['fc.fc_host.hbas_changed'])
        yield


@contextlib.contextmanager
def nport_wwpn_choices(choices, remote=False):
    with mock('fc.fc_host_nport_wwpn_choices', args=[], return_value=choices, remote=remote):
        yield


@contextlib.contextmanager
def fcport_create(alias, target_id, allow_deleted=False):
    config = call('fcport.create', {'port': alias, 'target_id': target_id})
    try:
        yield config
    finally:
        if allow_deleted:
            try:
                call('fcport.delete', config['id'])
            except InstanceNotFound:
                pass
        else:
            call('fcport.delete', config['id'])


def assert_fc_host(fc_host, alias, wwpn, wwpn_b, npiv):
    assert fc_host['alias'] == alias
    assert fc_host['wwpn'] == str_to_wwpn_naa(wwpn)
    if wwpn_b is None:
        assert fc_host['wwpn_b'] is None
    else:
        assert fc_host['wwpn_b'] == str_to_wwpn_b_naa(wwpn_b)
    assert fc_host['npiv'] == npiv


class AbstractFibreChannel:

    NODE_A_PORTS = NODE_A_FC_PHYSICAL_PORTS
    NODE_B_PORTS = NODE_B_FC_PHYSICAL_PORTS

    @pytest.fixture(scope='class')
    def fibre_channel_hardware(self):
        # Make sure iSCSI service is not running.  Would go boom
        assert call('service.query', [['service', '=', 'iscsitarget']], {'get': True})['state'] == 'STOPPED'
        with mock('fc.capable', return_value=True):
            with mock('system.feature_enabled', args=['FIBRECHANNEL',], return_value=True):
                call('fc.fc_host.reset_wired', True)
                with mock_ports(self.NODE_A_PORTS, self.NODE_B_PORTS):
                    yield

    @pytest.fixture(scope='class')
    def fibre_channel_wired(self, fibre_channel_hardware):
        """
        Wire the mocked FC ports together.

        Note that this will only work once during a middleware run.
        (There are some exceptions, but these don't apply to CI.)
        """
        assert call('fcport.query') == []
        try:
            yield
        finally:
            for fc in call('fc.fc_host.query'):
                call('fc.fc_host.delete', fc['id'])
            call('fc.fc_host.reset_wired', True)

    @pytest.fixture(scope='class')
    def fc_hosts(self, fibre_channel_wired):
        yield sorted(call('fc.fc_host.query'), key=lambda d: d['alias'])


class TestFixtureFibreChannel(AbstractFibreChannel):
    """Fixture with Fibre Channel"""

    def test_wired(self, fc_hosts, clear_ratelimit):
        assert len(fc_hosts) == 2
        if ha:
            assert_fc_host(fc_hosts[0], 'fc0', NODE_A_0_WWPN, NODE_B_0_WWPN, 0)
            assert_fc_host(fc_hosts[1], 'fc1', NODE_A_1_WWPN, NODE_B_1_WWPN, 0)
        else:
            assert_fc_host(fc_hosts[0], 'fc0', NODE_A_0_WWPN, None, 0)
            assert_fc_host(fc_hosts[1], 'fc1', NODE_A_1_WWPN, None, 0)

    def test_target(self, fc_hosts):
        with target_lun_zero('fctarget0', 'fcextent0', 100) as config:
            target_id = config['target']['id']
            rel_tgt_id = config['target']['rel_tgt_id']

            # The target was created with mode ISCSI.  Ensure we can't use that.
            with pytest.raises(ValidationErrors) as ve:
                call('fcport.create', {'port': fc_hosts[0]['alias'], 'target_id': target_id})
            assert ve.value.errors == [
                ValidationError(
                    'fcport_create.target_id',
                    f'Specified target "fctarget0" ({target_id}) does not have a "mode" (ISCSI) that permits FC access',
                    errno.EINVAL,
                )
            ]

            # Change the mode of the target
            call('iscsi.target.update', target_id, {'mode': 'FC'})

            # Now we should be able to successfully map the target
            with fcport_create(fc_hosts[0]['alias'], target_id) as map0:
                mapped_rel_tgt_id = fc_target_rel_tgt_id(rel_tgt_id, fc_hosts[0]['alias'])
                maps = call('fcport.query')
                assert len(maps) == 1
                assert maps[0] == map0

                # Let's generate the /etc/scst.conf and make sure it looks OK
                call('etc.generate', 'scst')
                lines = ssh("cat /etc/scst.conf").splitlines()
                scst_qla_targets = parse_qla2x00t(lines)
                # The 2nd physical port will also be written, albeit disabled
                assert len(scst_qla_targets) == 2
                rel_tgt_id_node_offset = 0
                if ha:
                    node = call('failover.node')
                    if node == 'A':
                        key0 = str_to_colon_hex(NODE_A_0_WWPN)
                        key1 = str_to_colon_hex(NODE_A_1_WWPN)
                    else:
                        key0 = str_to_colon_hex(NODE_B_0_WWPN)
                        key1 = str_to_colon_hex(NODE_B_1_WWPN)
                        if call('iscsi.global.alua_enabled'):
                            rel_tgt_id_node_offset = 32000
                else:
                    key0 = str_to_colon_hex(NODE_A_0_WWPN)
                    key1 = str_to_colon_hex(NODE_A_1_WWPN)
                assert key0 in scst_qla_targets
                assert scst_qla_targets[key0] == {
                    'LUN': {'0': 'fcextent0'},
                    'enabled': '1',
                    'rel_tgt_id': str(mapped_rel_tgt_id + rel_tgt_id_node_offset)
                }
                assert key1 in scst_qla_targets
                assert scst_qla_targets[key1] == {
                    'LUN': {},
                    'enabled': '0',
                    'rel_tgt_id': '10000'
                }

                # OK, now let's create another FC target
                with target_lun_zero('fctarget2', 'fcextent2', 200) as config2:
                    target2_id = config2['target']['id']
                    rel_tgt_id2 = config2['target']['rel_tgt_id']

                    # Change the mode of the target
                    call('iscsi.target.update', target2_id, {'mode': 'BOTH'})

                    # Make sure we can't create a new fcport using the in-use port
                    with pytest.raises(ValidationErrors) as ve:
                        call('fcport.create', {'port': fc_hosts[0]['alias'], 'target_id': target2_id})
                    assert ve.value.errors == [
                        ValidationError(
                            'fcport_create.port',
                            'Object with this port already exists',
                            errno.EINVAL,
                        )
                    ]

                    # NAS-137249 / 26.04 / Support Fibre Channel MPIO changed what
                    # is permitted wrt mapping targets
                    # - Can map the same target out another port
                    # - Cannot map the same target twice to the same physical dev
                    with fcport_create(fc_hosts[1]['alias'], target_id) as map1:
                        pass
                    with set_fchost_npiv(fc_hosts[0]['id'], 1):
                        alias = fc_hosts[0]['alias']
                        npivalias = f'{alias}/1'
                        with pytest.raises(ValidationErrors) as ve:
                            call('fcport.create', {'port': npivalias, 'target_id': target_id})
                        assert ve.value.errors == [
                            ValidationError(
                                'fcport_create.port',
                                f'Invalid FC port ({npivalias}) supplied, target already mapped to {alias}',
                                errno.EINVAL,
                            )
                        ]

                    # OK, now map the 2nd target
                    with fcport_create(fc_hosts[1]['alias'], target2_id) as map1:
                        mapped_rel_tgt_id2 = fc_target_rel_tgt_id(rel_tgt_id2, fc_hosts[1]['alias'])
                        maps = call('fcport.query')
                        assert len(maps) == 2
                        assert (maps[0] == map0 and maps[1] == map1) or (maps[0] == map1 and maps[1] == map0)

                        # Let's regenerate the /etc/scst.conf and just make sure it has the expected targets
                        call('etc.generate', 'scst')
                        lines = ssh("cat /etc/scst.conf").splitlines()
                        # Check FC targets
                        scst_qla_targets = parse_qla2x00t(lines)
                        assert len(scst_qla_targets) == 2
                        assert key0 in scst_qla_targets
                        assert scst_qla_targets[key0] == {
                            'LUN': {'0': 'fcextent0'},
                            'enabled': '1',
                            'rel_tgt_id': str(mapped_rel_tgt_id + rel_tgt_id_node_offset)
                        }
                        assert key1 in scst_qla_targets
                        assert scst_qla_targets[key1] == {
                            'LUN': {'0': 'fcextent2'},
                            'enabled': '1',
                            'rel_tgt_id': str(mapped_rel_tgt_id2 + rel_tgt_id_node_offset)
                        }
                        # Check iSCSI target
                        iqn2 = 'iqn.2005-10.org.freenas.ctl:fctarget2'
                        iscsi_targets = parse_iscsi(lines)
                        assert len(iscsi_targets) == 1
                        assert iqn2 in iscsi_targets
                        assert iscsi_targets[iqn2] == {
                            'LUN': {'0': 'fcextent2'},
                            'rel_tgt_id': str(rel_tgt_id2 + rel_tgt_id_node_offset),
                            'enabled': '1',
                            'per_portal_acl': '1'
                        }

                        # Make sure we can't update the old fcport using the in-use port
                        with pytest.raises(ValidationErrors) as ve:
                            call('fcport.update', map0['id'], {'port': fc_hosts[1]['alias']})
                        assert ve.value.errors == [
                            ValidationError(
                                'fcport_update.port',
                                'Object with this port already exists',
                                errno.EINVAL,
                            )
                        ]

                        # After NAS-137249 make sure we CAN update the old fcport using the
                        # in-use target
                        call('fcport.update', map0['id'], {'target_id': target2_id})
                        # And restore things again afterwards.
                        call('fcport.update', map0['id'], {'target_id': target_id})

                        # OK, now let's create a third FC target
                        with target_lun_zero('fctarget3', 'fcextent3', 300) as config3:
                            target3_id = config3['target']['id']
                            call('iscsi.target.update', target3_id, {'mode': 'FC'})

                            # Make sure we CAN update the old fcport to this target
                            assert call('fcport.update',
                                        map0['id'],
                                        {'target_id': target3_id})['target']['id'] == target3_id
                            # Then put is back
                            assert call('fcport.update',
                                        map0['id'],
                                        {'target_id': target_id})['target']['id'] == target_id

                    # We've just left the context where the 2nd fcport was created
                    # So now ensure we CAN update the old fcport to this port
                    assert call('fcport.update',
                                map0['id'],
                                {'port': fc_hosts[1]['alias']})['port'] == fc_hosts[1]['alias']
                    # Then put is back
                    assert call('fcport.update',
                                map0['id'],
                                {'port': fc_hosts[0]['alias']})['port'] == fc_hosts[0]['alias']

    def test_target_delete(self, fc_hosts):
        """Ensure that we can delete a mapped FC target."""
        with target_lun_zero('fctarget0', 'fcextent0', 100) as config:
            target_id = config['target']['id']

            # Change the mode of the target
            call('iscsi.target.update', target_id, {'mode': 'FC'})

            # Now we should be able to successfully map the target
            with fcport_create(fc_hosts[0]['alias'], target_id, True):
                # Make sure we have a mapping
                assert len(call('fcport.query', [['target.id', '=', target_id]])) == 1

                # Delete the target
                call('iscsi.target.delete', target_id, True, True)

                # Make sure we DON'T have a mapping
                assert len(call('fcport.query', [['target.id', '=', target_id]])) == 0

    def test_target_mode_change(self, fc_hosts):
        """
        Ensure that when we change the mode of a mapped FC target, the
        mapping gets removed.
        """
        with target_lun_zero('fctarget0', 'fcextent0', 100) as config:
            target_id = config['target']['id']

            # Change the mode of the target
            call('iscsi.target.update', target_id, {'mode': 'FC'})

            # Now we should be able to successfully map the target
            with fcport_create(fc_hosts[0]['alias'], target_id, True):
                # Make sure we have a mapping
                assert len(call('fcport.query', [['target.id', '=', target_id]])) == 1

                # Change the mode of the target to BOTH
                call('iscsi.target.update', target_id, {'mode': 'BOTH'})

                # Make sure we STILL have a mapping
                assert len(call('fcport.query', [['target.id', '=', target_id]])) == 1

                # Change the mode of the target to ISCSI
                call('iscsi.target.update', target_id, {'mode': 'ISCSI'})

                # Make sure we DON'T have a mapping
                assert len(call('fcport.query', [['target.id', '=', target_id]])) == 0

            # Change the mode of the target to BOTH
            call('iscsi.target.update', target_id, {'mode': 'BOTH'})

            # Map the target again
            with fcport_create(fc_hosts[0]['alias'], target_id, True):
                # Make sure we have a mapping
                assert len(call('fcport.query', [['target.id', '=', target_id]])) == 1

                # Change the mode of the target to BOTH
                call('iscsi.target.update', target_id, {'mode': 'FC'})

                # Make sure we STILL have a mapping
                assert len(call('fcport.query', [['target.id', '=', target_id]])) == 1

                # Change the mode of the target to ISCSI
                call('iscsi.target.update', target_id, {'mode': 'ISCSI'})

                # Make sure we DON'T have a mapping
                assert len(call('fcport.query', [['target.id', '=', target_id]])) == 0

    def test_npiv_setting(self, fc_hosts):
        # Try to set NPIV to -1
        with pytest.raises(ValidationErrors) as ve:
            call('fc.fc_host.update', fc_hosts[0]['id'], {'npiv': -1})
        assert ve.value.errors == [
            ValidationError(
                'fc_host_update.npiv',
                'Invalid npiv (-1) supplied, must be 0 or greater',
                errno.EINVAL,
            )
        ]

        # Try to set NPIV to too large a value (3000)
        with pytest.raises(ValidationErrors) as ve:
            call('fc.fc_host.update', fc_hosts[0]['id'], {'npiv': 3000})
        assert ve.value.errors == [
            ValidationError(
                'fc_host_update.npiv',
                'Invalid npiv (3000) supplied, max value 254',
                errno.EINVAL,
            )
        ]

        # Make sure fcport.port_choices looks correct
        assert call('fcport.port_choices') == {
            'fc0': {
                'wwpn': str_to_wwpn_naa(NODE_A_0_WWPN),
                'wwpn_b': str_to_wwpn_b_naa(NODE_B_0_WWPN)
            },
            'fc1': {
                'wwpn': str_to_wwpn_naa(NODE_A_1_WWPN),
                'wwpn_b': str_to_wwpn_b_naa(NODE_B_1_WWPN)
            }
        }

        # Now set it to a valid value (4)
        call('fc.fc_host.update', fc_hosts[0]['id'], {'npiv': 4})

        # Read things back with a couple of queries to test those.
        fc0 = call('fc.fc_host.query', [['wwpn', '=', str_to_wwpn_naa(NODE_A_0_WWPN)]], {'get': True})
        assert fc0['npiv'] == 4
        if ha:
            fc1 = call('fc.fc_host.query', [['wwpn_b', '=', str_to_wwpn_b_naa(NODE_B_1_WWPN)]], {'get': True})
            assert fc1['npiv'] == 0
        else:
            fc1 = call('fc.fc_host.query', [['wwpn', '=', str_to_wwpn_naa(NODE_A_1_WWPN)]], {'get': True})
            assert fc1['npiv'] == 0

        # Increase to a valid value (5)
        call('fc.fc_host.update', fc_hosts[0]['id'], {'npiv': 5})
        fc0 = call('fc.fc_host.query', [['alias', '=', 'fc0']], {'get': True})
        assert fc0['npiv'] == 5

        # Reduce to a valid value (1)
        call('fc.fc_host.update', fc_hosts[0]['id'], {'npiv': 1})
        fc0 = call('fc.fc_host.query', [['wwpn', '=', str_to_wwpn_naa(NODE_A_0_WWPN)]], {'get': True})
        assert fc0['npiv'] == 1

        # Make sure fcport.port_choices looks correct
        assert call('fcport.port_choices') == {
            'fc0': {
                'wwpn': str_to_wwpn_naa(NODE_A_0_WWPN),
                'wwpn_b': str_to_wwpn_b_naa(NODE_B_0_WWPN)
            },
            'fc0/1': {
                'wwpn': str_to_wwpn_naa(NODE_A_0_WWPN_NPIV_1),
                'wwpn_b': str_to_wwpn_b_naa(NODE_B_0_WWPN_NPIV_1)
            },
            'fc1': {
                'wwpn': str_to_wwpn_naa(NODE_A_1_WWPN),
                'wwpn_b': str_to_wwpn_b_naa(NODE_B_1_WWPN)
            }
        }

        with target_lun_zero('fctarget1', 'fcextent1', 100) as config:
            # The target was created as an ISCSI target.  We should not be able
            # to map it to a FC port.
            target_id = config['target']['id']
            call('iscsi.target.update', target_id, {'mode': 'BOTH'})

            with fcport_create('fc0/1', target_id):
                # Check that we can NOT now reduce npiv to zero
                with pytest.raises(ValidationErrors) as ve:
                    call('fc.fc_host.update', fc_hosts[0]['id'], {'npiv': 0})
                assert ve.value.errors == [
                    ValidationError(
                        'fc_host_update.npiv',
                        'Invalid npiv (0) supplied, fc0/1 is currently mapped to a target',
                        errno.EINVAL,
                    )
                ]

                # Let's also make sure that the /etc/scst.conf looks right when an
                # NPIV mapped target is present
                call('etc.generate', 'scst')
                lines = ssh("cat /etc/scst.conf").splitlines()
                scst_qla_targets = parse_qla2x00t(lines)
                assert len(scst_qla_targets) == 3
                rel_tgt_id_node_offset = 0
                if ha:
                    node = call('failover.node')
                    if node == 'A':
                        key0 = str_to_colon_hex(NODE_A_0_WWPN)
                        key1 = str_to_colon_hex(NODE_A_1_WWPN)
                        key2 = str_to_colon_hex(NODE_A_0_WWPN_NPIV_1)
                    else:
                        key0 = str_to_colon_hex(NODE_B_0_WWPN)
                        key1 = str_to_colon_hex(NODE_B_1_WWPN)
                        key2 = str_to_colon_hex(NODE_B_0_WWPN_NPIV_1)
                        if call('iscsi.global.alua_enabled'):
                            rel_tgt_id_node_offset = 32000
                else:
                    key0 = str_to_colon_hex(NODE_A_0_WWPN)
                    key1 = str_to_colon_hex(NODE_A_1_WWPN)
                    key2 = str_to_colon_hex(NODE_A_0_WWPN_NPIV_1)
                assert key0 in scst_qla_targets
                assert scst_qla_targets[key0] == {
                    'LUN': {},
                    'enabled': '0',
                    'rel_tgt_id': '10000'
                }
                assert key1 in scst_qla_targets
                assert scst_qla_targets[key1] == {
                    'LUN': {},
                    'enabled': '0',
                    'rel_tgt_id': '10001'
                }
                assert key2 in scst_qla_targets
                assert scst_qla_targets[key2] == {
                    'LUN': {'0': 'fcextent1'},
                    'enabled': '1',
                    'node_name': key0,
                    'parent_host': key0,
                    'rel_tgt_id': str(5001 + rel_tgt_id_node_offset)
                }

            # NPIV target no longer mapped.  Now reduce npiv to zero
            call('fc.fc_host.update', fc_hosts[0]['id'], {'npiv': 0})

            # Make sure fcport.port_choices looks correct
            assert call('fcport.port_choices') == {
                'fc0': {
                    'wwpn': str_to_wwpn_naa(NODE_A_0_WWPN),
                    'wwpn_b': str_to_wwpn_b_naa(NODE_B_0_WWPN)
                },
                'fc1': {
                    'wwpn': str_to_wwpn_naa(NODE_A_1_WWPN),
                    'wwpn_b': str_to_wwpn_b_naa(NODE_B_1_WWPN)
                }
            }


class TestFixtureNoSlotFibreChannel(AbstractFibreChannel):
    """
    Fixture with Fibre Channel without slot information
    reported in fc.fc_hosts
    """
    NODE_A_PORTS = NO_SLOT_NODE_A_FC_PHYSICAL_PORTS
    NODE_B_PORTS = NO_SLOT_NODE_B_FC_PHYSICAL_PORTS

    def test_wired(self, fc_hosts):
        assert len(fc_hosts) == 6
        if ha:
            assert_fc_host(fc_hosts[0], 'fc0', NO_SLOT_NODE_A_0_WWPN, NO_SLOT_NODE_B_0_WWPN, 0)
            assert_fc_host(fc_hosts[1], 'fc1', NO_SLOT_NODE_A_1_WWPN, NO_SLOT_NODE_B_1_WWPN, 0)
            assert_fc_host(fc_hosts[2], 'fc2', NO_SLOT_NODE_A_2_WWPN, NO_SLOT_NODE_B_2_WWPN, 0)
            assert_fc_host(fc_hosts[3], 'fc3', NO_SLOT_NODE_A_3_WWPN, NO_SLOT_NODE_B_3_WWPN, 0)
            assert_fc_host(fc_hosts[4], 'fc4', NO_SLOT_NODE_A_4_WWPN, NO_SLOT_NODE_B_4_WWPN, 0)
            assert_fc_host(fc_hosts[5], 'fc5', NO_SLOT_NODE_A_5_WWPN, NO_SLOT_NODE_B_5_WWPN, 0)
        else:
            assert_fc_host(fc_hosts[0], 'fc0', NO_SLOT_NODE_A_0_WWPN, None, 0)
            assert_fc_host(fc_hosts[1], 'fc1', NO_SLOT_NODE_A_1_WWPN, None, 0)
            assert_fc_host(fc_hosts[2], 'fc2', NO_SLOT_NODE_A_2_WWPN, None, 0)
            assert_fc_host(fc_hosts[3], 'fc3', NO_SLOT_NODE_A_3_WWPN, None, 0)
            assert_fc_host(fc_hosts[4], 'fc4', NO_SLOT_NODE_A_4_WWPN, None, 0)
            assert_fc_host(fc_hosts[5], 'fc5', NO_SLOT_NODE_A_5_WWPN, None, 0)


class TestFibreChannelHardwareAdd(AbstractFibreChannel, AlertMixin):
    ALERT_CLASS_NAME = 'FCHardwareAdded'

    @pytest.mark.dependency(name="fc_add_baseline")
    def test_add_baseline(self, fc_hosts, clear_ratelimit):
        assert len(fc_hosts) == 2
        if ha:
            assert_fc_host(fc_hosts[0], 'fc0', NODE_A_0_WWPN, NODE_B_0_WWPN, 0)
            assert_fc_host(fc_hosts[1], 'fc1', NODE_A_1_WWPN, NODE_B_1_WWPN, 0)
        else:
            assert_fc_host(fc_hosts[0], 'fc0', NODE_A_0_WWPN, None, 0)
            assert_fc_host(fc_hosts[1], 'fc1', NODE_A_1_WWPN, None, 0)
        assert call('fc.fc_host.hbas_changed') == {'added': False, 'removed': False}

    @pytest.mark.dependency(depends=['fc_add_baseline'])
    def test_add(self, fc_hosts):
        self.clear_alert()
        # Add another dual-port HBA to each controller
        with remock_ports([NODE_A_0, NODE_A_1, NODE_A_2, NODE_A_3], [NODE_B_0, NODE_B_1, NODE_B_2, NODE_B_3]):
            # Normally changing the hardware would have required rebooting the controllers, which
            # would clear cache.  Do that now.
            call('fc.fc_host.reset_check_hardware')
            assert call('fcport.query') == []
            fc_hosts = sorted(call('fc.fc_host.query'), key=lambda d: d['alias'])
            assert len(fc_hosts) == 4
            if ha:
                assert_fc_host(fc_hosts[0], 'fc0', NODE_A_0_WWPN, NODE_B_0_WWPN, 0)
                assert_fc_host(fc_hosts[1], 'fc1', NODE_A_1_WWPN, NODE_B_1_WWPN, 0)
                assert_fc_host(fc_hosts[2], 'fc2', NODE_A_2_WWPN, NODE_B_2_WWPN, 0)
                assert_fc_host(fc_hosts[3], 'fc3', NODE_A_3_WWPN, NODE_B_3_WWPN, 0)
            else:
                assert_fc_host(fc_hosts[0], 'fc0', NODE_A_0_WWPN, None, 0)
                assert_fc_host(fc_hosts[1], 'fc1', NODE_A_1_WWPN, None, 0)
                assert_fc_host(fc_hosts[2], 'fc2', NODE_A_2_WWPN, None, 0)
                assert_fc_host(fc_hosts[3], 'fc3', NODE_A_3_WWPN, None, 0)
            self.assert_alert_count(1)
        self.clear_alert()


class TestFibreChannelHardwareReplace(AbstractFibreChannel, AlertMixin):
    ALERT_CLASS_NAME = 'FCHardwareReplaced'

    @pytest.mark.dependency(name="fc_replace_baseline")
    def test_replace_baseline(self, fc_hosts, clear_ratelimit):
        assert len(fc_hosts) == 2
        if ha:
            assert_fc_host(fc_hosts[0], 'fc0', NODE_A_0_WWPN, NODE_B_0_WWPN, 0)
            assert_fc_host(fc_hosts[1], 'fc1', NODE_A_1_WWPN, NODE_B_1_WWPN, 0)
        else:
            assert_fc_host(fc_hosts[0], 'fc0', NODE_A_0_WWPN, None, 0)
            assert_fc_host(fc_hosts[1], 'fc1', NODE_A_1_WWPN, None, 0)
        assert call('fc.fc_host.hbas_changed') == {'added': False, 'removed': False}

    @pytest.mark.dependency(depends=['fc_replace_baseline'])
    def test_replace(self, fc_hosts):
        self.clear_alert()
        # Add another dual-port HBA to each controller
        with remock_ports([NODE_A_2, NODE_A_3], [NODE_B_2, NODE_B_3]):
            # Normally changing the hardware would have required rebooting the controllers, which
            # would clear cache.  Do that now.
            call('fc.fc_host.reset_check_hardware')
            assert call('fcport.query') == []
            fc_hosts = sorted(call('fc.fc_host.query'), key=lambda d: d['alias'])
            assert len(fc_hosts) == 2
            if ha:
                assert_fc_host(fc_hosts[0], 'fc0', NODE_A_2_WWPN, NODE_B_2_WWPN, 0)
                assert_fc_host(fc_hosts[1], 'fc1', NODE_A_3_WWPN, NODE_B_3_WWPN, 0)
            else:
                assert_fc_host(fc_hosts[0], 'fc0', NODE_A_2_WWPN, None, 0)
                assert_fc_host(fc_hosts[1], 'fc1', NODE_A_3_WWPN, None, 0)
            self.assert_alert_count(1)
        self.clear_alert()
