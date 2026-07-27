import pytest

from middlewared.test.integration.assets.directory_service import (
    directoryservice,
    AD_DOM2_LIMITED_USER,
    AD_DOM2_LIMITED_USER_PASSWORD,
)
from middlewared.test.integration.assets.privilege import privilege
from middlewared.test.integration.utils import call, client, ssh, truenas_server
from middlewared.test.integration.utils.failover import do_failover, ha_enabled


SAF_PATH = '/root/.KDC_SERVER_AFFINITY'


@pytest.fixture(scope='function')
def enable_ds_auth():
    """ Directory services users may only authenticate to the API when the ds_auth
    system.general setting is on (with it off, the generated PAM stacks for API login
    exclude the directory services modules entirely). Every test in this file is
    HA-only and HA systems are always enterprise-licensed, so the setting can be
    toggled directly. Changing it regenerates PAM on both controllers, which also
    covers logins performed after a failover. """
    call('system.general.update', {'ds_auth': True})

    try:
        yield
    finally:
        call('system.general.update', {'ds_auth': False})


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
def test_ad_user_privilege_auth_survives_failover(enable_ds_auth):
    """
    An AD user granted API access through a group privilege must still authenticate to the
    API after a failover.

    ``test_failover`` above only asserts ``directoryservices.status`` is HEALTHY, which does
    not exercise group-membership resolution on the newly-active controller. Asserting a real
    login -- and that the group-derived privilege is retained -- is what covers that.
    """
    with directoryservice('ACTIVEDIRECTORY') as ds:
        domain_name = ds['config']['configuration']['domain']
        short_name = ds['domain_info']['domain_controller']['pre-win2k_domain']

        # RID 513 is the constant RID for the "Domain Users" group. The limited AD user is a
        # member of it and has no other path to API access, so the granted READONLY_ADMIN
        # role depends entirely on that group membership resolving on the active controller.
        domain_sid = call('idmap.domain_info', short_name)['sid']
        limited_user = f'{AD_DOM2_LIMITED_USER}@{domain_name}'

        with privilege({
            'name': 'AD failover privilege',
            'local_groups': [],
            'ds_groups': [f'{domain_sid}-513'],
            'roles': ['READONLY_ADMIN'],
            'web_shell': False,
        }):
            # Baseline: the user authenticates and receives the group-derived role before
            # failover, so a post-failover failure is unambiguously a failover regression.
            with client(auth=(limited_user, AD_DOM2_LIMITED_USER_PASSWORD)) as c:
                methods = c.call('core.get_methods')
                assert 'system.info' in methods
                assert 'pool.create' not in methods

            do_failover()

            # DS health alone does not prove group resolution works; the login below does.
            check_ds_status(call('directoryservices.status'), 'HEALTHY')

            # The same AD user must still authenticate on the new active controller and retain
            # the group-derived privilege. A stale local SAM SID would truncate the group list,
            # dropping the privileged group -- denying the login (this context manager would
            # raise) or stripping the role.
            with client(auth=(limited_user, AD_DOM2_LIMITED_USER_PASSWORD)) as c:
                me = c.call('auth.me')
                assert 'DIRECTORY_SERVICE' in me['account_attributes']
                methods = c.call('core.get_methods')
                assert 'system.info' in methods, (
                    'AD user lost its group-derived privilege after failover; local SAM SID '
                    'or group membership resolution did not survive promotion'
                )
                assert 'pool.create' not in methods
