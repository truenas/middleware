import sys
import time
import os

import pytest
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import ha, ip, dev_test
from middlewared.test.integration.utils.client import client

# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')


def test_001_verify_system_dataset_functionality():
    ip_to_be_used = ip
    if ha and os.environ.get('virtual_ip', False):
        ip_to_be_used = os.environ['controller1_ip']

    with client(host_ip=ip_to_be_used) as c:
        bp_name = c.call('boot.pool_name')
        pool_info = {
            'bp_name': bp_name,
            'bp_sysds_basename': f'{bp_name}/.system',
            'zp_name1': 'cargo1',
            'zp_name2': 'cargo2',
        }
        """
        When a system is first installed or all zpools are deleted
        then we place the system dataset on the boot pool. Since our
        CI pipelines always start with a fresh VM, we can safely assume
        that there are no zpools (created or imported) by the time this
        test runs and so we can assert this accordingly.
        """
        results = c.call('systemdataset.config')
        assert isinstance(results, dict)
        assert results['pool'] == pool_info['bp_name']
        assert results['basename'] == pool_info['bp_sysds_basename']

        """
        Now that we've verified the system dataset is on the boot-pool we do the follwing:
        1. get unused disks
        2. create a 1 disk striped zpool
        3. verify system dataset automagically migrated to this pool
        4. if this is HA, wait for standby to reboot (since we reboot standby
            on system dataset migrate)
        5. start the smb service and migrate the system dataset to boot-pool
        6. create a 2nd zpool and ensure the system dataset doesn't migrate to it
        7. cleanup both zpools by exporting them
        """
        unused_disks = [i['name'] for i in c.call('disk.get_unused')]
        assert len(unused_disks) >= 2
        pool_name1, pool_name2 = pool_info['zp_name1'], pool_info['zp_name2']
        pool1, pool2 = None, None
        try:
            pool1 = c.call(
                'pool.create', {
                    'name': pool_name1,
                    'topology': {'data': [{'type': 'STRIPE', 'disks': [unused_disks[0]]}]}
                },
                job=True
            )
        except Exception as e:
            assert False, e
        else:
            results = c.call('systemdataset.config')
            assert isinstance(results, dict)
            assert results['pool'] == pool_name1
            assert results['basename'] == f'{pool_name1}/.system'
            if ha:
                # on HA systems, when first zpool is created we reboot
                # the standby so the system dataset related operations
                # can complete properly
                max_wait, wait_time, sleep_time = 120, 0, 1
                while wait_time < max_wait:
                    if c.call('failover.call_remote', 'core.ping') == 'pong':
                        break
                    else:
                        time.sleep(sleep_time)
                        wait_time += sleep_time

            try:
                pool2 = c.call(
                    'pool.create', {
                        'name': pool_name2,
                        'topology': {'data': [{'type': 'STRIPE', 'disks': [unused_disks[1]]}]}
                    },
                    job=True
                )
            except Exception as e:
                assert False, e
            else:
                # we've created a 2nd pool, so let's ensure the system dataset doesn't automatically
                # migrate to this one since it should already exist on `pool_name1`
                results = c.call('systemdataset.config')
                assert isinstance(results, dict)
                assert results['pool'] == pool_name1
                assert results['basename'] == f'{pool_name1}/.system'

            # finally, let's start the smb service and make sure that we can move system dataset
            # while the service is started (end-user is prompted in the webUI that this will cause
            # service disruption)
            smb_svc = c.call('service.query', [['service', '=', 'cifs']], {'get': True})
            if smb_svc['state'] != 'RUNNING':
                assert c.call('service.start', 'cifs')

            sysds = c.call('systemdataset.update', {'pool': pool_info['bp_name']}, job=True)
            assert sysds['pool'] == pool_info['bp_name']
            assert sysds['basename'] == pool_info['bp_sysds_basename']
            assert c.call('service.stop', 'cifs') is False  # the way we return service status is horrible
        finally:
            for pool in filter(lambda x: x is not None, (pool1, pool2)):
                c.call('pool.export', pool['id'], {'destroy': True}, job=True)
