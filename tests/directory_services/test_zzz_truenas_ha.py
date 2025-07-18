import pytest

from middlewared.test.integration.assets.directory_service import directoryservice
from middlewared.test.integration.utils import call, ssh, truenas_server
from middlewared.test.integration.utils.failover import do_failover, ha_enabled
from time import sleep


SAF_PATH = '/root/.KDC_SERVER_AFFINITY'


def check_ds_status(status_dict, expected):
    msg = status_dict['status_msg']
    status = status_dict['status']
    assert status == expected, f'{expected}: unexpected status [{status}]: {msg}'


def get_server_affinity(server_ip):
    saf_data = ssh(f'cat {SAF_PATH}', ip=server_ip)
    return saf_data.split()[0]


def check_server_affinity():
    # Verfiy that both nodes have same KDC affinity set
    nodea_affinity = get_server_affinity(truenas_server.nodea_ip)
    nodeb_affinity = get_server_affinity(truenas_server.nodeb_ip)
    assert nodea_affinity == nodeb_affinity


def check_status_ad_impl():
    # Compare machine account passwords.
    workgroup = call('smb.config')['workgroup']
    active_secrets = call('directoryservices.secrets.get_machine_secret', workgroup)
    standby_secrets = call('failover.call_remote', 'directoryservices.secrets.get_machine_secret', [workgroup])
    assert active_secrets == standby_secrets


@pytest.mark.skipif(not ha_enabled, reason='HA only test')
@pytest.mark.parametrize('service_type', ['ACTIVEDIRECTORY', 'IPA', 'LDAP'])
def test_failover(service_type):
    with directoryservice(service_type) as ds:
        # This node is healthy, but let's check on remote node
        check_ds_status(call('failover.call_remote', 'directoryservices.status'), 'HEALTHY')

        do_failover()

        # Check this node is HEALTHY
        check_ds_status(call('directoryservices.status'), 'HEALTHY')

        # Check that state is correct on standby
        match service_type:
            case 'ACTIVEDIRECTORY':
                check_server_affinity()
                check_status_ad_impl()
            case 'IPA':
                check_server_affinity()
            case 'LDAP':
                pass
            case _:
                raise RuntimeError(f'{service_type}: unhandled directory service type')

        # Check remote node is HEALTHY
        check_ds_status(call('failover.call_remote', 'directoryservices.status'), 'HEALTHY')

        # Force test recover
        call('directoryservices.health.recover')
        call('failover.call_remote', 'directoryservices.health.recover')

    check_ds_status(call('directoryservices.status'), None)
    check_ds_status(call('failover.call_remote', 'directoryservices.status'), None)
