import pytest
from time import sleep

from middlewared.test.integration.assets.directory_service import directoryservice
from middlewared.test.integration.utils import call, ssh, truenas_server
from middlewared.test.integration.utils.failover import do_failover, ha_enabled


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
    with directoryservice(service_type):
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


@pytest.mark.skipif(not ha_enabled, reason='HA only test')
def test_secrets_propagate_to_standby_on_rotation():
    """
    The machine-account secret DB backup (services.cifs.secrets) is the only HA-durable
    copy and is replicated to the standby. After an on-disk password rotation,
    kerberos.check_updated_keytab must refresh that backup AND the refreshed row must
    reach the standby's config DB.
    """
    with directoryservice('ACTIVEDIRECTORY'):
        netbios = call('smb.config')['netbiosname'].upper()
        workgroup = call('smb.config')['workgroup']
        machine_key = f'SECRETS/MACHINE_PASSWORD/{workgroup}'

        before = call('directoryservices.secrets.get_db_secrets')[f'{netbios}$'][machine_key]

        # Rotate on the active node, then run the freshness check to back it up.
        ssh('net ads changetrustpw')
        call('kerberos.check_updated_keytab')

        active = call('directoryservices.secrets.get_db_secrets')[f'{netbios}$'][machine_key]
        assert active != before, 'active DB backup did not pick up the rotated secret'

        # The DB write replicates to the standby; allow a moment for SQL replay.
        standby = None
        for _ in range(10):
            standby = call(
                'failover.call_remote', 'directoryservices.secrets.get_db_secrets', []
            )[f'{netbios}$'][machine_key]
            if standby == active:
                break
            sleep(1)

        assert standby == active, 'standby DB backup did not receive the rotated secret'
