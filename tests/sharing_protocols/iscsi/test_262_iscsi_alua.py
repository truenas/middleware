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
from auto_config import extended_tests, ha, pool_name
from protocols import iscsi_scsi_connection

from middlewared.test.integration.assets.hostkvm import get_kvm_domain, poweroff_vm, reset_vm, start_vm
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, settle_ha, ssh
from middlewared.test.integration.utils.client import truenas_server

pytestmark = pytest.mark.skipif(not ha, reason='Tests applicable to HA only')
skip_extended_tests = pytest.mark.skipif(not extended_tests, reason="Skip extended tests")

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
        sleep(5)
        while retries:
            if call('iscsi.alua.settled'):
                if self.VERBOSE:
                    _debug('ALUA is settled')
                break
            retries -= 1
            if self.VERBOSE:
                _debug('Waiting for ALUA to settle')
            sleep(5)
        settle_ha()

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

    @pytest.fixture(scope="class")
    def restore_active_node(self):
        """Capture the MASTER at class entry; on class teardown reboot the
        current MASTER if it has changed.

        This is a class-scoped precursor to alua_configured (i.e.
        alua_configured depends on it), so its setup runs first and its
        teardown runs last -- after alua_configured has torn down ALUA,
        the initiator/portal, and the iSCSI service. The reboot therefore
        happens with the test-file's ALUA setup already gone, leaving the
        cluster in a clean baseline state with the original active node
        once again MASTER.

        Tests do not need to take this fixture explicitly; depending on it
        via alua_configured is sufficient.
        """
        initial_node = call("failover.node")
        try:
            yield
        finally:
            try:
                current_node = call("failover.node")
            except Exception:
                current_node = None
            if current_node and current_node != initial_node:
                _debug(
                    f"restore_active_node: current MASTER is Node "
                    f"{current_node}; rebooting to restore Node {initial_node}"
                )
                try:
                    call("system.reboot", "iSCSI ALUA test: restoring active node")
                except Exception:
                    # system.reboot may not return cleanly as the websocket
                    # connection is torn down by the reboot itself.
                    pass
                self.wait_for_new_master(current_node)
                self.wait_for_backup()
                self.wait_for_settle()
                _debug(f"restore_active_node: Node {initial_node} is MASTER again")

    @pytest.fixture(scope='class')
    def alua_configured(self, restore_active_node):
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

    @skip_extended_tests
    @pytest.mark.timeout(1200)
    def test_alua_target_create(self, alua_configured):
        """
        Test that we can create a target, extent and access it from both paths.
        Repeat many times.
        """
        config = alua_configured
        portal_id = config['portal']['id']
        for i in range(50):
            target_name = f'aluatargetrep{i:03}'
            iqn = f'iqn.2005-10.org.freenas.ctl:{target_name}'
            with target(target_name, [{'portal': portal_id}]) as target_config:
                extentname = f'aluaextent{i:03}'
                with self.target_lun(target_config['id'], extentname, 100, 0) as tlconfig:
                    serial = tlconfig['extent']['serial']
                    naa = tlconfig['extent']['naa']
                    ip1 = truenas_server.nodea_ip if i % 2 == 0 else truenas_server.nodeb_ip
                    ip2 = truenas_server.nodeb_ip if i % 2 == 0 else truenas_server.nodea_ip
                    with iscsi_scsi_connection(ip1, iqn) as s1:
                        print(f'Connected to {iqn} via {ip1}')
                        verify_ha_inquiry(s1, serial, naa, 1)
                    with iscsi_scsi_connection(ip2, iqn) as s2:
                        print(f'Connected to {iqn} via {ip2}')
                        verify_ha_inquiry(s2, serial, naa, 1)

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
        self.validate_shape(new_ip, fix_write_patterns)
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
        self.validate_shape(other_ip, fix_write_patterns)

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

    # ------------------------------------------------------------------
    # Regression test for the LUN-replace stall during failover.
    #
    # Background. iscsi.alua.become_active swaps each LUN from a dev_disk
    # to a local zvol via a sysfs `replace` write. The kernel defers the
    # cleanup of the OLD tgt_devs to a workqueue. That cleanup calls
    # scst_clear_reservation -> scst_dlm_res_lock, which can stall for
    # tens of seconds when the dead peer is still a DLM lockspace member.
    # While stalled the worker holds scst_mutex, so subsequent replaces
    # queue behind it. With a typical client config (~25 LUNs and active
    # multipath sessions) the stall blows past the 15s budget enforced by
    # failover.events.restart_services, leaving iSCSI half-swapped.
    #
    # The kernel parks the deferred cleanup on a list while
    # async_lun_replace=1 and only releases it when the orchestrator
    # writes 0 to the sysfs knob. Middleware writes 0 from
    # iscsi.alua.reset_active, after dlm.reset_active has evicted the
    # peer from the lockspaces.
    #
    # This test reproduces the production shape (2 targets with 25 + 10
    # LUNs, multipath sessions on both controllers), triggers an
    # ungraceful failover, and asserts that the failover-restart timeout
    # message is absent from the new master's failover.log.
    # ------------------------------------------------------------------

    LUN_REPLACE_LAYOUT = (("big", 25), ("small", 10))
    LUN_REPLACE_LUN_MB = 100

    @contextlib.contextmanager
    def target_lun_dataset(self, target_id, dataset_name, mb, lun):
        """Like target_lun, but uses dataset() instead of zvol().

        dataset() avoids the per-zvol SSH probe in zvol(), which matters
        once we have ~35 LUNs to set up.
        """
        zvol_data = {
            "type": "VOLUME",
            "volsize": mb * MB,
            "volblocksize": "16K",
        }
        with dataset(dataset_name, zvol_data, pool_name) as ds_path:
            with zvol_extent(ds_path, dataset_name) as extent_config:
                with target_extent_associate(
                    target_id, extent_config["id"], lun
                ) as associate_config:
                    yield {
                        "extent": extent_config,
                        "associate": associate_config,
                    }

    @pytest.fixture
    def fix_lun_replace_config(self, alua_configured):
        """2 targets with 25 + 10 LUNs each. Function-scoped so it doesn't
        coexist with fix_complex_alua_config or other class-scoped state."""
        config = alua_configured
        portal_id = config["portal"]["id"]
        digits = "".join(random.choices(string.digits, k=4))
        targets = {}
        with contextlib.ExitStack() as es:
            for suffix, luncount in self.LUN_REPLACE_LAYOUT:
                namebase = f"{digits}lr{suffix}"
                if self.VERBOSE:
                    _debug(
                        f"lun-replace: creating target {namebase} with {luncount} LUNs"
                    )
                tcfg = es.enter_context(
                    target(f"target{namebase}", [{"portal": portal_id}])
                )
                tcfg["luns"] = {}
                for lun in range(luncount):
                    ext_name = f"extent{namebase}l{lun}"
                    tcfg["luns"][lun] = es.enter_context(
                        self.target_lun_dataset(
                            tcfg["id"], ext_name, self.LUN_REPLACE_LUN_MB, lun
                        )
                    )
                targets[suffix] = tcfg
            sleep(2)
            self.wait_for_settle()
            yield targets
            if self.VERBOSE:
                _debug("lun-replace: tearing down targets")

    @pytest.fixture
    def fix_lun_replace_recovery(self, fix_get_domain):
        """Yield the current-master domain info; on test completion, ensure
        the original master VM is back online and the cluster has settled.

        Runs regardless of whether the test body raised, so an assertion
        failure in the middle of the failover doesn't leave the cluster in
        a single-node state for whatever runs next.
        """
        yield fix_get_domain
        domain = fix_get_domain["domain"]
        _debug(f"lun-replace: (recovery) ensuring VM {domain} is running")
        try:
            start_vm(domain)
        except Exception as e:
            # Most likely the VM was already running (test body completed
            # the recovery, or never powered it off). Move on.
            _debug(f"lun-replace: (recovery) start_vm raised {e!r}; continuing")
        _debug("lun-replace: (recovery) waiting for backup")
        self.wait_for_backup()
        _debug("lun-replace: (recovery) waiting for ALUA to settle")
        self.wait_for_settle()
        _debug("lun-replace: (recovery) cluster recovered")

    @skip_extended_tests
    @pytest.mark.timeout(1200)
    def test_failover_lun_replace(
        self, fix_lun_replace_config, fix_lun_replace_recovery
    ):
        """become_active LUN-replace loop must not stall on DLM during failover."""
        targets = fix_lun_replace_config
        node = fix_lun_replace_recovery["node"]
        domain = fix_lun_replace_recovery["domain"]
        iqns = {
            suffix: f"{basename}:{tcfg['name']}" for suffix, tcfg in targets.items()
        }

        # The bug requires that the soon-to-be-new-master have at least one
        # client iSCSI session at the moment of failover, so that
        # __scst_acg_del_lun has tgt_devs to put on the async-cleanup list.
        # One session to the BACKUP node on the 25-LUN target gives the
        # standby's kernel 25 tgt_devs to free during become_active --
        # plenty to trigger the race against scst_mutex.
        standby_node = "B" if node == "A" else "A"
        standby_ip = (
            truenas_server.nodea_ip if standby_node == "A" else truenas_server.nodeb_ip
        )
        big_iqn = iqns["big"]

        _debug(
            f"lun-replace: master Node {node} ({domain}); opening session to STANDBY Node {standby_node} ({standby_ip}) {big_iqn}"
        )
        with iscsi_scsi_connection(standby_ip, big_iqn) as s:
            s.testunitready()
            _debug(
                "lun-replace: session up; waiting for ALUA to settle before failover"
            )
            sleep(2)
            self.wait_for_settle()

            _debug(f"lun-replace: powering off VM {domain} (Node {node})")
            poweroff_vm(domain)
            sleep(10)

            _debug("lun-replace: waiting for new master")
            new_node = self.wait_for_new_master(node)
            _debug(
                f"lun-replace: new master is Node {new_node}; waiting for failover_in_progress to clear"
            )
            self.wait_for_failover_in_progress()
            sleep(5)

        # The session was to the standby (which survived the failover), so
        # the close at this point is clean.
        new_ip = truenas_server.nodea_ip if new_node == "A" else truenas_server.nodeb_ip
        # Note: do NOT call wait_for_settle() here -- the original master is
        # powered off, so iscsi.alua.settled cannot return True (it queries
        # the peer via failover.call_remote). wait_for_settle() will run
        # after recovery below, once both nodes are up again.
        _debug(f"lun-replace: failover complete; new master IP is {new_ip}")

        # Primary regression check: the 15s timeout never fired during the
        # failover that just completed. The message comes from
        # failover.events.restart_services -- see middleware/plugins/
        # failover_/event.py -- and is logged to /var/log/failover.log.
        _debug(
            "lun-replace: checking /var/log/failover.log on new master for restart-timeout message"
        )
        result = ssh(
            "grep -c 'Failed to restart service \"iscsitarget\" after' "
            "/var/log/failover.log || true"
        ).strip()
        _debug(f"lun-replace: failover.log restart-timeout match count = {result!r}")
        assert result == "0", (
            f"failover.log on new master Node {new_node} reports "
            f"iscsitarget restart timeout (grep -c returned {result!r}); "
            f"LUN-replace regression?"
        )

        # Secondary sanity check: the middleware fix ran. After
        # iscsi.alua.reset_active, async_lun_replace must read 0. If only
        # the kernel side were applied without the middleware companion,
        # become_active would still complete (parking + drain at unload),
        # but this knob would be stuck at 1.
        flag = ssh("cat /sys/kernel/scst_tgt/async_lun_replace").strip()
        _debug(f"lun-replace: async_lun_replace = {flag!r}")
        assert flag == "0", (
            f"/sys/kernel/scst_tgt/async_lun_replace is {flag!r} on new "
            f"master Node {new_node}; iscsi.scst.disable_async_lun_replace "
            f"did not run from reset_active"
        )

        # Functional check: every LUN is reachable on the new master.
        _debug("lun-replace: validating LUN access on new master")
        for suffix, tcfg in targets.items():
            iqn = iqns[suffix]
            for lun in tcfg["luns"]:
                with iscsi_scsi_connection(new_ip, iqn, lun) as s:
                    s.testunitready()
        _debug("lun-replace: all LUNs reachable on new master")

        # Recovery (start_vm + wait_for_backup + wait_for_settle) is handled
        # by fix_lun_replace_recovery so it runs even if an assertion above
        # has already failed.
