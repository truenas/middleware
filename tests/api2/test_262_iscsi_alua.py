#!/usr/bin/env python3
#
# test_261_iscsi_cmd contains some general ALUA tests, but this file will contain some
# more detailed ALUA tests
import contextlib
import random
import string
from time import sleep

import pytest
from assets.websocket.iscsi import (alua_enabled, initiator_portal, target,
                                    target_extent_associate, verify_capacity,
                                    verify_luns)
from assets.websocket.service import ensure_service_enabled
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.client import truenas_server

from auto_config import ha, pool_name
from protocols import iscsi_scsi_connection

if not ha:
    pytest.skip("skipping ALUA tests", allow_module_level=True)


SERVICE_NAME = 'iscsitarget'
MB = 1024 * 1024


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
def zvol_extent(zvol, extent_name):
    payload = {
        'type': 'DISK',
        'disk': f'zvol/{zvol}',
        'name': extent_name,
    }
    config = call('iscsi.extent.create', payload)
    try:
        yield config
    finally:
        call('iscsi.extent.delete', config['id'], True, True)


class TestFixtureConfiguredALUA:
    """Fixture for with iSCSI enabled and ALUA configured"""

    def wait_for_settle(self, verbose=False):
        if verbose:
            print("Checking ALUA status...")
        retries = 12
        while retries:
            if call('iscsi.alua.settled'):
                if verbose:
                    print("ALUA is settled")
                break
            retries -= 1
            if verbose:
                print("Waiting for ALUA to settle")
            sleep(5)

    @pytest.fixture(scope='class')
    def alua_configured(self):
        with ensure_service_enabled(SERVICE_NAME):
            call('service.start', SERVICE_NAME)
            with alua_enabled():
                self.wait_for_settle()
                with initiator_portal() as config:
                    yield config

    @contextlib.contextmanager
    def target_lun(self, target_id, zvol_name, mb, lun):
        with zvol(zvol_name, mb) as zvol_config:
            with zvol_extent(zvol_config['id'], zvol_name) as extent_config:
                with target_extent_associate(target_id, extent_config['id'], lun):
                    yield

    def verify_luns(self, iqn, lun_size_list):
        lun_list = [lun for lun, _ in lun_size_list]
        for lun, mb in lun_size_list:
            # Node A
            with iscsi_scsi_connection(truenas_server.nodea_ip, iqn, lun) as s:
                verify_luns(s, lun_list)
                verify_capacity(s, mb * MB)
            # Node B
            with iscsi_scsi_connection(truenas_server.nodeb_ip, iqn) as s:
                verify_luns(s, lun_list)
                verify_capacity(s, 100 * MB)

    def test_alua_luns(self, alua_configured):
        """Test whether an ALUA target reacts correctly to having a LUN added
        and removed again (in terms of REPORT LUNS response)"""
        config = alua_configured
        portal_id = config['portal']['id']
        digits = ''.join(random.choices(string.digits, k=4))
        target_name = f"target{digits}"
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
