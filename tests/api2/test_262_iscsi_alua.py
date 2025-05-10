import contextlib
import datetime
import random
import string
from time import sleep

import pytest
from assets.websocket.iscsi import (alua_enabled, initiator_portal, target, target_extent_associate, verify_capacity,
                                    verify_ha_inquiry, verify_luns, zvol_extent)
from assets.websocket.pool import zvol
from assets.websocket.service import ensure_service_enabled
from auto_config import ha, pool_name
from protocols import iscsi_scsi_connection

from middlewared.test.integration.assets.hostkvm import get_kvm_domain, poweroff_vm, reset_vm, start_vm
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.client import truenas_server

pytestmark = pytest.mark.skipif(not ha, reason='Tests applicable to HA only')

SERVICE_NAME = 'iscsitarget'
MB = 1024 * 1024
basename = 'iqn.2005-10.org.freenas.ctl'


def other_domain(hadomain):
    if hadomain.endswith('_c1'):
        return f'{hadomain[:-1]}2'
    elif hadomain.endswith('_c2'):
        return f'{hadomain[:-1]}1'
    raise ValueError(f'Invalid HA domain name: {hadomain}')


def _debug(message):
    print(datetime.datetime.now().strftime('[%Y-%m-%d %H:%M:%S]'), message)


class TestFixtureConfiguredALUA:
    """Fixture for with iSCSI enabled and ALUA configured"""

    ZEROS = bytearray(512)
    BLOCKS = 5
    VERBOSE = False
    NUM_TARGETS = 10

    def wait_for_settle(self):
        if self.VERBOSE:
            _debug('Checking ALUA status...')
        retries = 12
        while retries:
            if call('iscsi.alua.settled'):
                if self.VERBOSE:
                    _debug('ALUA is settled')
                break
            retries -= 1
            if self.VERBOSE:
                _debug('Waiting for ALUA to settle')
            sleep(5)

    def wait_for_master(self, timeout=120):
        for _ in range(timeout):
            try:
                if call('failover.status') == 'MASTER':
                    if self.VERBOSE:
                        _debug('Can communicate with new MASTER')
                    break
                if self.VERBOSE:
                    _debug('Waiting for new MASTER')
                sleep(10)
            except Exception:
                if self.VERBOSE:
                    _debug('Exception while waiting for new MASTER')
                sleep(10)

    def wait_for_ready(self, timeout=120):
        for _ in range(timeout):
            try:
                if call('system.ready'):
                    if self.VERBOSE:
                        _debug('System is ready')
                    break
                if self.VERBOSE:
                    _debug('Waiting for ready')
                sleep(10)
            except Exception:
                if self.VERBOSE:
                    _debug('Exception while waiting for ready')
                sleep(10)

    def wait_for_backup(self, timeout=120):
        for _ in range(timeout):
            try:
                if not call('failover.disabled.reasons'):
                    if self.VERBOSE:
                        _debug('Both controllers available')
                    break
                if self.VERBOSE:
                    _debug('Waiting for BACKUP')
                sleep(10)
            except Exception:
                if self.VERBOSE:
                    _debug('Exception while waiting for BACKUP')
                sleep(10)

    def wait_for_new_master(self, oldnode, timeout=60):
        for _ in range(timeout):
            try:
                newnode = call('failover.node')
                if oldnode != newnode:
                    if call('failover.status') == 'MASTER':
                        if self.VERBOSE:
                            _debug(f'Can communicate with new MASTER {newnode}')
                        return newnode
                if self.VERBOSE:
                    _debug('Waiting for new MASTER')
                sleep(10)
            except Exception:
                if self.VERBOSE:
                    _debug('Exception while waiting for new MASTER')
                sleep(10)

    def wait_for_failover_in_progress(self, timeout=120):
        for _ in range(timeout):
            try:
                if not call('failover.in_progress'):
                    if self.VERBOSE:
                        _debug('Failover event complete')
                    return
                if self.VERBOSE:
                    _debug('Waiting for failover event to complete')
                sleep(10)
            except Exception:
                if self.VERBOSE:
                    _debug('Exception while waiting for failover event to complete')
                sleep(10)

    @pytest.fixture(scope='class')
    def alua_configured(self):
        assert call('failover.config')['disabled'] is False
        with ensure_service_enabled(SERVICE_NAME):
            call('service.control', 'START', SERVICE_NAME, job=True)
            with alua_enabled():
                self.wait_for_settle()
                with initiator_portal() as config:
                    yield config
            if self.VERBOSE:
                _debug('Tore down ALUA')
        if self.VERBOSE:
            _debug('Tore down iSCSI')

    @pytest.fixture(scope='class')
    def fix_complex_alua_config(self, alua_configured):
        """Fixture to create a non-trival ALUA iSCSI configuration"""
        # Will create 10 targets (0-9) with 0 to 9 LUNs
        config = alua_configured
        portal_id = config['portal']['id']
        digits = ''.join(random.choices(string.digits, k=4))
        # iqn = f'iqn.2005-10.org.freenas.ctl:{target_name}'
        targets = {}
        with contextlib.ExitStack() as es:
            for i in range(self.NUM_TARGETS):
                namebase = f'{digits}x{i}'
                if self.VERBOSE:
                    _debug(f'Creating target {i}...')
                target_config = es.enter_context(target(f'target{namebase}', [{'portal': portal_id}]))
                target_id = target_config['id']
                target_config['luns'] = {}
                luncount = self.lun_count(i)
                for j in range(luncount):
                    sizemb = 20 + (10 * (j + 1))
                    if i > 7:
                        lun = 100 + j
                    else:
                        lun = j
                    if self.VERBOSE:
                        _debug(f'Creating extent (LUN {lun} {sizemb}MB)...')
                    target_config['luns'][lun] = es.enter_context(
                        self.target_lun(target_id, f'extent{namebase}l{lun}', sizemb, lun)
                    )
                targets[i] = target_config
            sleep(2)
            self.wait_for_settle()
            yield targets
            if self.VERBOSE:
                _debug(f'Tearing down {self.NUM_TARGETS} targets ...')
        if self.VERBOSE:
            _debug(f'Tore down {self.NUM_TARGETS} targets')

    @contextlib.contextmanager
    def target_lun(self, target_id, zvol_name, mb, lun):
        with zvol(zvol_name, mb, pool_name) as zvol_config:
            with zvol_extent(zvol_config['id'], zvol_name) as extent_config:
                with target_extent_associate(target_id, extent_config['id'], lun) as associate_config:
                    yield {
                        'zvol': zvol_config,
                        'extent': extent_config,
                        'associate': associate_config
                    }

    def verify_luns(self, iqn, lun_size_list):
        """Ensure that the expected LUNs are visible from each controller."""
        lun_list = [lun for lun, _ in lun_size_list]
        for lun, mb in lun_size_list:
            # Node A
            with iscsi_scsi_connection(truenas_server.nodea_ip, iqn, lun) as s:
                verify_luns(s, lun_list)
                verify_capacity(s, mb * MB)
            # Node B
            with iscsi_scsi_connection(truenas_server.nodeb_ip, iqn, lun) as s:
                verify_luns(s, lun_list)
                verify_capacity(s, mb * MB)

    def lun_count(self, targetnum):
        match targetnum:
            case 0:
                return 0
            case 1 | 2 | 3 | 4 | 5:
                return 1
            case 6 | 7 | 8:
                return 2
            case _:
                return 5

    def test_alua_luns(self, alua_configured):
        """Test whether an ALUA target reacts correctly to having a LUN added
        and removed again (in terms of REPORT LUNS response)"""
        config = alua_configured
        portal_id = config['portal']['id']
        digits = ''.join(random.choices(string.digits, k=4))
        target_name = f'target{digits}'
        iqn = f'iqn.2005-10.org.freenas.ctl:{target_name}'
        with target(target_name, [{'portal': portal_id}]) as target_config:
            target_id = target_config['id']
            # First configure a single extent at LUN 0 and ensure that we
            # can see it from both interfaces.
            with self.target_lun(target_id, f'extent0_{digits}', 100, 0):
                sleep(2)
                self.wait_for_settle()
                self.verify_luns(iqn, [(0, 100)])

                # Next add a 2nd extent at LUN 1 and ensure that we can see both LUNs
                # from both interfaces.
                with self.target_lun(target_id, f'extent1_{digits}', 200, 1):
                    sleep(2)
                    self.wait_for_settle()
                    self.verify_luns(iqn, [(0, 100), (1, 200)])

                # After the LUN 1 extent has been removed again, ensure that we cannot see it
                # any longer.
                sleep(2)
                self.wait_for_settle()
                self.verify_luns(iqn, [(0, 100)])

                # Next add back a 2nd extent at LUN 1 (with a different size) and ensure
                # that we can still see both LUNs from both interfaces.
                with self.target_lun(target_id, f'extent1_{digits}', 250, 1):
                    sleep(2)
                    self.wait_for_settle()
                    self.verify_luns(iqn, [(0, 100), (1, 250)])
                    # Add a third LUN
                    with self.target_lun(target_id, f'extent2_{digits}', 300, 2):
                        sleep(2)
                        self.wait_for_settle()
                        self.verify_luns(iqn, [(0, 100), (1, 250), (2, 300)])
                    sleep(2)
                    self.wait_for_settle()
                    self.verify_luns(iqn, [(0, 100), (1, 250)])
                sleep(2)
                self.wait_for_settle()
                self.verify_luns(iqn, [(0, 100)])

    def test_alua_lun_100(self, alua_configured):
        """Test that an ALUA target - without a LUN 0 - works correctly with only LUN 100."""
        config = alua_configured
        portal_id = config['portal']['id']
        digits = ''.join(random.choices(string.digits, k=4))
        target_name = f'target{digits}'
        iqn = f'iqn.2005-10.org.freenas.ctl:{target_name}'
        with target(target_name, [{'portal': portal_id}]) as target_config:
            target_id = target_config['id']
            # First configure a single extent at LUN 0 and ensure that we
            # can see it from both interfaces.
            with self.target_lun(target_id, f'extent0_{digits}', 200, 100):
                sleep(2)
                self.wait_for_settle()
                self.verify_luns(iqn, [(100, 200)])
            sleep(2)
            self.wait_for_settle()

    def visit_luns(self, ip, config, callback):
        """Run the specified callback method for each LUN in the config"""
        for target_num, target_config in config.items():
            luns = target_config['luns']
            if not luns:
                # If no LUNs then we can't talk to the target.
                continue
            target_name = target_config['name']
            iqn = f'{basename}:{target_name}'
            for lun, lun_config in luns.items():
                with iscsi_scsi_connection(ip, iqn, lun) as s:
                    callback(s, target_num, lun, lun_config)

    def validate_shape(self, ip, config, tpgs=1):
        """Validate that each LUN in the config has the expected shape.

        For example, serial number, NAA, size.
        """
        def validate_lun(s, target_num, lun, lun_config):
            api_serial_number = lun_config['extent']['serial']
            api_naa = lun_config['extent']['naa']
            verify_ha_inquiry(s, api_serial_number, api_naa, tpgs)
            if 'zvol' in lun_config:
                verify_capacity(s, lun_config['zvol']['volsize']['parsed'])
            if self.VERBOSE:
                _debug(f'Target {target_num} LUN {lun} shape OK')
        self.visit_luns(ip, config, validate_lun)

    @pytest.fixture(scope='class')
    def fix_validate_shapes(self, fix_complex_alua_config):
        """Fixture that validates that the complex ALUA config has the right shape."""
        # Make sure that each controller is exporting the targets/LUNs we expect
        if self.VERBOSE:
            _debug('Validate shape seen by Node A...')
        self.validate_shape(truenas_server.nodea_ip, fix_complex_alua_config)

        if self.VERBOSE:
            _debug('Validate shape seen by Node B...')
        self.validate_shape(truenas_server.nodeb_ip, fix_complex_alua_config)

        if self.VERBOSE:
            _debug('Validated shape')
        yield fix_complex_alua_config

    def zero_luns(self, ip, config):
        def zero_lun(s, target_num, lun, lun_config):
            # Write zeros using WRITE SAME (16)
            s.writesame16(0, self.BLOCKS, self.ZEROS)
            s.synchronizecache10(0, self.BLOCKS)
        self.visit_luns(ip, config, zero_lun)

    def check_zero_luns(self, ip, config):
        def check_zero_lun(s, target_num, lun, lun_config):
            r = s.read16(0, self.BLOCKS)
            assert r.datain == self.ZEROS * self.BLOCKS, r.datain
        self.visit_luns(ip, config, check_zero_lun)

    @pytest.fixture(scope='class')
    def fix_zero_luns(self, fix_validate_shapes):
        """Fixture that validates that the complex ALUA config has zeros written to LUNs."""
        # Zero the LUNs
        self.zero_luns(truenas_server.nodea_ip, fix_validate_shapes)

        # Check that the LUNs are zeroed
        self.check_zero_luns(truenas_server.nodea_ip, fix_validate_shapes)
        self.check_zero_luns(truenas_server.nodeb_ip, fix_validate_shapes)

        if self.VERBOSE:
            _debug('LUNs zeroed')
        return fix_validate_shapes

    def page_pattern(self, target_num, lun):
        """
        Return a 512 byte long bytearray unique to the target/lun.
        """
        basis = f'TARGET {target_num} LUN {lun} ------'
        b = bytearray()
        b.extend(basis[:16].encode())
        pattern = b * 32
        assert len(pattern) == 512, pattern
        return pattern

    def write_patterns(self, ip, config):
        def write_pattern(s, target_num, lun, lun_config):
            s.writesame16(1, 2, self.page_pattern(target_num, lun))
            s.synchronizecache10(1, 2)
        self.visit_luns(ip, config, write_pattern)

    def check_patterns(self, ip, config):
        def check_pattern(s, target_num, lun, lun_config):
            pattern = self.page_pattern(target_num, lun)
            r = s.read16(0, 1)
            assert r.datain == self.ZEROS, r.datain
            r = s.read16(1, 2)
            assert r.datain == pattern * 2, r.datain
            r = s.read16(3, 1)
            assert r.datain == self.ZEROS, r.datain
            if self.VERBOSE:
                _debug(f'Target {target_num} LUN {lun} pattern OK: {pattern[:16]}')
        self.visit_luns(ip, config, check_pattern)

    @pytest.fixture(scope='class')
    def fix_write_patterns(self, fix_zero_luns):
        """Fixture that writes a data pattern to the complex ALUA config."""
        # Write the pattern
        self.write_patterns(truenas_server.nodea_ip, fix_zero_luns)
        if self.VERBOSE:
            _debug('Wrote LUN patterns')

        # Check that the LUNs have the correct patterns
        if self.VERBOSE:
            _debug('Validate data pattern seen by Node A...')
        self.check_patterns(truenas_server.nodea_ip, fix_zero_luns)
        if self.VERBOSE:
            _debug('Validate data pattern seen by Node B...')
        self.check_patterns(truenas_server.nodeb_ip, fix_zero_luns)

        if self.VERBOSE:
            _debug('LUNs have pattern written / checked')
        # Delay for a few seconds to give host a chance
        sleep(5)
        return fix_zero_luns

    @pytest.fixture(scope='class')
    def fix_orig_active_node(self):
        return call('failover.node')

    @pytest.mark.timeout(900)
    def test_complex_alua_setup(self, fix_validate_shapes, fix_orig_active_node):
        """
        Test that the complex ALUA configuration is setup, and has the correct shape.
        """
        orig_active_node = fix_orig_active_node
        assert orig_active_node in ['A', 'B']

    @pytest.mark.timeout(900)
    def test_complex_zero_luns(self, fix_zero_luns):
        """
        Test that the complex ALUA configuration is setup, and has zeros written
        to LUNs.
        """
        pass

    @pytest.mark.timeout(900)
    def test_complex_write_patterns(self, fix_write_patterns):
        """
        Test that the complex ALUA configuration is setup, and has a data pattern written
        to LUNs.
        """
        pass

    @pytest.fixture
    def fix_get_domain(self):
        """
        Fixture to get the KVM domain associated with the current
        MASTER node.

        Note: unlike most other fixtures in this class, the fixture does NOT
        have class scope.
        """
        # Do some sanity checks before we proceed.
        assert call('failover.status') == 'MASTER'

        node = call('failover.node')
        assert node in ['A', 'B']

        domain = get_kvm_domain()
        assert domain
        if node == 'A':
            assert domain.endswith('_c1')
        elif node == 'B':
            assert domain.endswith('_c2')

        return {'node': node, 'domain': domain}

    @pytest.mark.timeout(900)
    def test_failover_complex_alua_config(self, fix_write_patterns, fix_get_domain):
        """
        Power off the current MASTER and ensure that the previous BACKUP node serves
        the ALUA targets, as soon as failover is complete.
        """
        node = fix_get_domain['node']
        domain = fix_get_domain['domain']

        # Shutdown the current MASTER.
        if self.VERBOSE:
            _debug(f'Powering off VM {domain} (Node {node})')
        poweroff_vm(domain)
        sleep(10)

        # Wait for the new MASTER to come up
        newnode = self.wait_for_new_master(node)

        # Wait for the failover event to complete
        self.wait_for_failover_in_progress()
        sleep(5)

        if newnode == 'A':
            new_ip = truenas_server.nodea_ip
        else:
            new_ip = truenas_server.nodeb_ip

        if self.VERBOSE:
            _debug(f'Validate shape seen by Node {newnode}...')
        self.validate_shape(new_ip, fix_write_patterns, 0)
        if self.VERBOSE:
            _debug(f'Validate data pattern seen by Node {newnode}...')
        self.check_patterns(new_ip, fix_write_patterns)

    @pytest.mark.timeout(900)
    def test_boot_complex_alua_config(self, fix_write_patterns, fix_get_domain, fix_orig_active_node):
        """
        Reset the current MASTER, and repower the previous MASTER and ensure that
        ALUA targets are served by both nodes.
        """
        domain = fix_get_domain['domain']
        orig_domain = other_domain(domain)

        # Reset the MASTER
        reset_vm(domain)
        if self.VERBOSE:
            _debug(f'Reset VM {domain}')

        # Power the shutdown node back on.
        start_vm(orig_domain)
        if self.VERBOSE:
            _debug(f'Started VM {orig_domain}')

        sleep(5)

        # Wait for the new MASTER to come up
        self.wait_for_master()
        self.wait_for_failover_in_progress()
        self.wait_for_ready()
        assert call('system.info')['uptime_seconds'] < 600

        # Ensure that the BACKUP is also up
        self.wait_for_backup()
        self.wait_for_settle()
        assert call('failover.call_remote', 'system.info')['uptime_seconds'] < 600

        newnode = call('failover.node')
        assert newnode in ['A', 'B']

        if newnode == 'A':
            new_ip = truenas_server.nodea_ip
            other_ip = truenas_server.nodeb_ip
            othernode = 'B'
        else:
            new_ip = truenas_server.nodeb_ip
            other_ip = truenas_server.nodea_ip
            othernode = 'A'

        # Ensure that the targets look OK on MASTER
        if self.VERBOSE:
            _debug(f'Validate shape seen by Node {newnode}...')
        self.validate_shape(new_ip, fix_write_patterns, None)

        if self.VERBOSE:
            _debug(f'Validate data pattern seen by Node {newnode}...')
        self.check_patterns(new_ip, fix_write_patterns)

        # Ensure that the targets look OK on BACKUP
        if self.VERBOSE:
            _debug(f'Validate shape seen by Node {othernode}...')
        self.validate_shape(other_ip, fix_write_patterns, 1)

        if self.VERBOSE:
            _debug(f'Validate data pattern seen by Node {othernode}...')
        self.check_patterns(other_ip, fix_write_patterns)

        # Finally, we want to ensure that we have the same MASTER node as
        # when these tests started.
        if newnode != fix_orig_active_node:
            if self.VERBOSE:
                _debug(f'Restoring {fix_orig_active_node} as MASTER')
            try:
                call('system.reboot', 'iSCSI ALUA test')
            except Exception:
                pass
            newnode2 = self.wait_for_new_master(newnode)
            assert newnode2 == fix_orig_active_node
            self.wait_for_backup()
            self.wait_for_settle()
