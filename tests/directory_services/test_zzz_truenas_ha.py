import pytest

from middlewared.test.integration.assets.directory_service import directoryservice
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.failover import do_failover, ha


def check_ds_status(status_dict, expected):
    msg = status_dict['status_msg']
    status = status_dict['status']
    assert status == expected, f'{expected}: unexpected status [{status}]: {msg}'


@pytest.mark.skipif(not ha, reason='HA only test')
@pytest.mark.parametrize('service_type', ['ACTIVEDIRECTORY', 'IPA', 'LDAP'])
def test_failover(service_type):
    with directoryservice(service_type) as ds:
        # This node is healthy, but let's check on remote node
        check_ds_status(call('failover.call_remote', 'directoryservices.status'), 'HEALTHY')

        do_failover()

        # Check this node is HEALTHY
        check_ds_status(call('directoryservices.status'), 'HEALTHY')

        # Check remote node is HEALTHY
        check_ds_status(call('failover.call_remote', 'directoryservices.status'), 'HEALTHY')

        # Force a healthy check as well
        call('directoryservices.health.check')

        # And on remote node
        call('failover.call_remote', 'directoryservices.health.check')

    check_ds_status(call('directoryservices.status'), 'DISABLED')
    check_ds_status(call('failover.call_remote', 'directoryservices.status'), 'DISABLED')
