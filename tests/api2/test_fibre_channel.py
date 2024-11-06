import contextlib
import copy
import errno

import pytest
from assets.websocket.iscsi import target, target_extent_associate, zvol_extent
from auto_config import ha, pool_name

from middlewared.service_exception import ValidationError, ValidationErrors
from middlewared.test.integration.utils import call, mock, ssh

MB = 1024 * 1024

NODE_A_0_WWPN = '0x210000aaaaaaaa01'
NODE_A_0_WWPN_NPIV_1 = '0x220000aaaaaaaa01'
NODE_A_0 = {
    'name': 'host14',
    'path': '/sys/class/fc_host/host14',
    'node_name': '0x200000aaaaaaaa01',
    'port_name': NODE_A_0_WWPN,
    'port_type': 'NPort (fabric via point-to-point)',
    'port_state': 'Online',
    'speed': '8 Gbit',
    'addr': 'pci0000:b2/0000:b2:00.0/0000:b3:00.0',
    'max_npiv_vports': 254,
    'npiv_vports_inuse': 0,
    'physical': True,
    'slot': 'CPU SLOT4 PCI-E 3.0 X16 / PCI Function 0'
}

NODE_A_1_WWPN = '0x210000aaaaaaaa02'
NODE_A_1 = {
    'name': 'host16',
    'path': '/sys/class/fc_host/host16',
    'node_name': '0x200000aaaaaaaa02',
    'port_name': NODE_A_1_WWPN,
    'port_type': 'NPort (fabric via point-to-point)',
    'port_state': 'Online',
    'speed': '8 Gbit',
    'addr': 'pci0000:b2/0000:b2:00.0/0000:b3:00.1',
    'max_npiv_vports': 254,
    'npiv_vports_inuse': 0,
    'physical': True,
    'slot': 'CPU SLOT4 PCI-E 3.0 X16 / PCI Function 1'
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
    'speed': '8 Gbit',
    'addr': 'pci0000:b2/0000:b2:00.0/0000:b3:00.0',
    'max_npiv_vports': 254,
    'npiv_vports_inuse': 0,
    'physical': True,
    'slot': 'CPU SLOT4 PCI-E 3.0 X16 / PCI Function 0'
}

NODE_B_1_WWPN = '0x210000bbbbbbbb02'
NODE_B_1 = {
    'name': 'host16',
    'path': '/sys/class/fc_host/host16',
    'node_name': '0x200000bbbbbbbb02',
    'port_name': NODE_B_1_WWPN,
    'port_type': 'NPort (fabric via point-to-point)',
    'port_state': 'Online',
    'speed': '8 Gbit',
    'addr': 'pci0000:b2/0000:b2:00.0/0000:b3:00.1',
    'max_npiv_vports': 254,
    'npiv_vports_inuse': 0,
    'physical': True,
    'slot': 'CPU SLOT4 PCI-E 3.0 X16 / PCI Function 1'
}

NODE_B_FC_PHYSICAL_PORTS = [NODE_B_0, NODE_B_1]


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
def zvol(name, volsizeMB):
    payload = {
        'name': f'{pool_name}/{name}',
        'type': 'VOLUME',
        'volsize': volsizeMB * MB,
        'volblocksize': '16K'
    }
    config = call('pool.dataset.create', payload)
    try:
        yield config
    finally:
        call('pool.dataset.delete', config['id'])


@contextlib.contextmanager
def target_lun(target_config, zvol_name, mb, lun):
    with zvol(zvol_name, mb) as zvol_config:
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
def node_a_hardware(remote=False):
    with mock('fc.fc_hosts', return_value=NODE_A_FC_PHYSICAL_PORTS, remote=remote):
        physical_port_filter = [['physical', '=', True]]
        with mock('fc.fc_hosts', args=physical_port_filter, return_value=NODE_A_FC_PHYSICAL_PORTS, remote=remote):
            yield


@contextlib.contextmanager
def node_b_hardware(remote=False):
    with mock('fc.fc_hosts', return_value=NODE_B_FC_PHYSICAL_PORTS, remote=remote):
        physical_port_filter = [['physical', '=', True]]
        with mock('fc.fc_hosts', args=physical_port_filter, return_value=NODE_B_FC_PHYSICAL_PORTS, remote=remote):
            yield


@contextlib.contextmanager
def fcport_create(alias, target_id):
    config = call('fcport.create', {'port': alias, 'target_id': target_id})
    try:
        yield config
    finally:
        call('fcport.delete', config['id'])


class TestFixtureFibreChannel:
    """Fixture with Fibre Channel"""

    @pytest.fixture(scope='class')
    def fibre_channel_hardware(self):
        # Make sure iSCSI service is not running.  Would go boom
        assert call('service.query', [['service', '=', 'iscsitarget']], {'get': True})['state'] == 'STOPPED'
        with mock('fc.capable', return_value=True):
            with mock('system.feature_enabled', args=['FIBRECHANNEL',], return_value=True):
                call('fc.fc_host.reset_wired', True)
                if ha:
                    node = call('failover.node')
                    if node == 'A':
                        with node_a_hardware():
                            with node_b_hardware(True):
                                yield
                    else:
                        with node_a_hardware(True):
                            with node_b_hardware():
                                yield
                else:
                    with node_a_hardware():
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

    @pytest.fixture(scope='class')
    def fc_hosts(self, fibre_channel_wired):
        yield sorted(call('fc.fc_host.query'), key=lambda d: d['alias'])

    def assert_fc_host(self, fc_host, alias, wwpn, wwpn_b, npiv):
        assert fc_host['alias'] == alias
        assert fc_host['wwpn'] == str_to_wwpn_naa(wwpn)
        if wwpn_b is None:
            assert fc_host['wwpn_b'] is None
        else:
            assert fc_host['wwpn_b'] == str_to_wwpn_b_naa(wwpn_b)
        assert fc_host['npiv'] == npiv

    def test_wired(self, fc_hosts):
        assert len(fc_hosts) == 2
        if ha:
            self.assert_fc_host(fc_hosts[0], 'fc0', NODE_A_0_WWPN, NODE_B_0_WWPN, 0)
            self.assert_fc_host(fc_hosts[1], 'fc1', NODE_A_1_WWPN, NODE_B_1_WWPN, 0)
        else:
            self.assert_fc_host(fc_hosts[0], 'fc0', NODE_A_0_WWPN, None, 0)
            self.assert_fc_host(fc_hosts[1], 'fc1', NODE_A_1_WWPN, None, 0)
        self.fc_hosts = fc_hosts

    def test_target(self, fc_hosts):
        with target_lun_zero('fctarget0', 'fcextent0', 100) as config:
            target_id = config['target']['id']

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
                maps = call('fcport.query')
                assert len(maps) == 1
                assert maps[0] == map0

                # Let's generate the /etc/scst.conf and make sure it looks OK
                call('etc.generate', 'scst')
                lines = ssh("cat /etc/scst.conf").splitlines()
                scst_qla_targets = parse_qla2x00t(lines)
                assert len(scst_qla_targets) == 1
                rel_tgt_id = 5001
                if ha:
                    node = call('failover.node')
                    if node == 'A':
                        key = str_to_colon_hex(NODE_A_0_WWPN)
                    else:
                        key = str_to_colon_hex(NODE_B_0_WWPN)
                        if call('iscsi.global.alua_enabled'):
                            rel_tgt_id += 32000
                else:
                    key = str_to_colon_hex(NODE_A_0_WWPN)
                assert key in scst_qla_targets
                assert scst_qla_targets[key] == {
                    'LUN': {'0': 'fcextent0'},
                    'enabled': '1',
                    'rel_tgt_id': str(rel_tgt_id)
                }

                # OK, now let's create another FC target
                with target_lun_zero('fctarget2', 'fcextent2', 200) as config2:
                    target2_id = config2['target']['id']
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

                    # Make sure we can't create a new fcport using the in-use target
                    with pytest.raises(ValidationErrors) as ve:
                        call('fcport.create', {'port': fc_hosts[1]['alias'], 'target_id': target_id})
                    assert ve.value.errors == [
                        ValidationError(
                            'fcport_create.target_id',
                            'Object with this target_id already exists',
                            errno.EINVAL,
                        )
                    ]

                    # OK, now map the 2nd target
                    with fcport_create(fc_hosts[1]['alias'], target2_id) as map1:
                        maps = call('fcport.query')
                        assert len(maps) == 2
                        assert (maps[0] == map0 and maps[1] == map1) or (maps[0] == map1 and maps[1] == map0)

                        # Let's regenerate the /etc/scst.conf and just make sure it has the expected targets
                        call('etc.generate', 'scst')
                        lines = ssh("cat /etc/scst.conf").splitlines()
                        scst_qla_targets = parse_qla2x00t(lines)
                        assert len(scst_qla_targets) == 2
                        iscsi_targets = parse_iscsi(lines)
                        assert len(iscsi_targets) == 1
                        assert 'iqn.2005-10.org.freenas.ctl:fctarget2' in iscsi_targets

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

                        # Make sure we can't update the old fcport using the in-use target
                        with pytest.raises(ValidationErrors) as ve:
                            call('fcport.update', map0['id'], {'target_id': target2_id})
                        assert ve.value.errors == [
                            ValidationError(
                                'fcport_update.target_id',
                                'Object with this target_id already exists',
                                errno.EINVAL,
                            )
                        ]

                        # OK, now let's create a third FC target
                        with target_lun_zero('fctarget3', 'fcextent3', 300) as config3:
                            target3_id = config3['target']['id']
                            call('iscsi.target.update', target3_id, {'mode': 'FC'})

                            # Make sure we CAN update the old fcport to this target
                            assert call('fcport.update', map0['id'], {'target_id': target3_id})['target']['id'] == target3_id
                            # Then put is back
                            assert call('fcport.update', map0['id'], {'target_id': target_id})['target']['id'] == target_id

                    # We've just left the context where the 2nd fcport was created
                    # So now ensure we CAN update the old fcport to this port
                    assert call('fcport.update', map0['id'], {'port': fc_hosts[1]['alias']})['port'] == fc_hosts[1]['alias']
                    # Then put is back
                    assert call('fcport.update', map0['id'], {'port': fc_hosts[0]['alias']})['port'] == fc_hosts[0]['alias']

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
                assert len(scst_qla_targets) == 1
                rel_tgt_id = 5001
                if ha:
                    node = call('failover.node')
                    if node == 'A':
                        key = str_to_colon_hex(NODE_A_0_WWPN_NPIV_1)
                    else:
                        key = str_to_colon_hex(NODE_B_0_WWPN_NPIV_1)
                        if call('iscsi.global.alua_enabled'):
                            rel_tgt_id += 32000
                else:
                    key = str_to_colon_hex(NODE_A_0_WWPN_NPIV_1)
                assert key in scst_qla_targets
                assert scst_qla_targets[key] == {
                    'LUN': {'0': 'fcextent1'},
                    'enabled': '1',
                    'rel_tgt_id': str(rel_tgt_id)
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
