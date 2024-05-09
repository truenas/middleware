import contextlib
import ipaddress
import socket

import pytest

from middlewared.test.integration.assets.iscsi import target_login_test
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server


@pytest.fixture(scope="module")
def my_ip4():
    """See which of my IP addresses will be used to connect."""
    # Things can be complicated e.g. my NAT between the test runner
    # and the target system  Therefore, first try using ssh into the
    # remote system and see what it thinks our IP address is.
    try:
        myip = ipaddress.ip_address(ssh('echo $SSH_CLIENT').split()[0])
        if myip.version != 4:
            raise ValueError("Not a valid IPv4 address")
        return str(myip)
    except Exception:
        # Fall back
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((truenas_server.ip, 80))
        assert result == 0
        myip = sock.getsockname()[0]
        sock.close()
        # Check that we have an IPv4 address
        socket.inet_pton(socket.AF_INET, myip)
        return myip


@contextlib.contextmanager
def portal():
    portal_config = call('iscsi.portal.create', {'listen': [{'ip': truenas_server.ip}], 'discovery_authmethod': 'NONE'})
    try:
        yield portal_config
    finally:
        call('iscsi.portal.delete', portal_config['id'])


@contextlib.contextmanager
def initiator():
    initiator_config = call('iscsi.initiator.create', {})
    try:
        yield initiator_config
    finally:
        call('iscsi.initiator.delete', initiator_config['id'])


@contextlib.contextmanager
def target(target_name, groups):
    target_config = call('iscsi.target.create', {'name': target_name, 'groups': groups})
    try:
        yield target_config
    finally:
        call('iscsi.target.delete', target_config['id'])


@contextlib.contextmanager
def extent(extent_name, zvol_name=None):
    zvol_name = zvol_name or extent_name
    with dataset(zvol_name, {'type': 'VOLUME', 'volsize': 51200, 'volblocksize': '512', 'sparse': True}) as zvol:
        extent_config = call('iscsi.extent.create', {'name': extent_name, 'disk': f'zvol/{zvol}'})
        try:
            yield extent_config
        finally:
            call('iscsi.extent.delete', extent_config['id'])


@contextlib.contextmanager
def target_extent(target_id, extent_id, lun_id):
    target_extent_config = call(
        'iscsi.targetextent.create', {'target': target_id, 'extent': extent_id, 'lunid': lun_id}
    )
    try:
        yield target_extent_config
    finally:
        call('iscsi.targetextent.delete', target_extent_config['id'])


@contextlib.contextmanager
def configured_target_to_extent():
    with portal() as portal_config:
        with initiator() as initiator_config:
            with target(
                'test-target', groups=[{
                    'portal': portal_config['id'],
                    'initiator': initiator_config['id'],
                    'auth': None,
                    'authmethod': 'NONE'
                }]
            ) as target_config:
                with extent('test_extent') as extent_config:
                    with target_extent(target_config['id'], extent_config['id'], 1):
                        yield {
                            'extent': extent_config,
                            'target': target_config,
                            'global': call('iscsi.global.config'),
                            'portal': portal_config,
                        }


@contextlib.contextmanager
def configure_iscsi_service():
    with configured_target_to_extent() as iscsi_config:
        try:
            call('service.start', 'iscsitarget')
            assert call('service.started', 'iscsitarget') is True
            yield iscsi_config
        finally:
            call('service.stop', 'iscsitarget')


@pytest.mark.parametrize('valid', [True, False])
def test_iscsi_auth_networks(valid):
    with configure_iscsi_service() as config:
        call(
            'iscsi.target.update',
            config['target']['id'],
            {'auth_networks': [] if valid else ['8.8.8.8/32']}
        )
        portal_listen_details = config['portal']['listen'][0]
        assert target_login_test(
            f'{portal_listen_details["ip"]}:{portal_listen_details["port"]}',
            f'{config["global"]["basename"]}:{config["target"]["name"]}',
        ) is valid


@pytest.mark.parametrize('valid', [True, False])
def test_iscsi_auth_networks_exact_ip(my_ip4, valid):
    with configure_iscsi_service() as config:
        call(
            'iscsi.target.update',
            config['target']['id'],
            {'auth_networks': [f"{my_ip4}/32"] if valid else ['8.8.8.8/32']}
        )
        portal_listen_details = config['portal']['listen'][0]
        assert target_login_test(
            f'{portal_listen_details["ip"]}:{portal_listen_details["port"]}',
            f'{config["global"]["basename"]}:{config["target"]["name"]}',
        ) is valid


@pytest.mark.parametrize('valid', [True, False])
def test_iscsi_auth_networks_netmask_24(my_ip4, valid):
    # good_ip will be our IP with the last byte cleared.
    good_ip = '.'.join(my_ip4.split('.')[:-1] + ['0'])
    # bad_ip will be our IP with the second last byte changed and last byte cleared
    n = (int(my_ip4.split('.')[2]) + 1) % 256
    bad_ip = '.'.join(good_ip.split('.')[:2] + [str(n), '0'])
    with configure_iscsi_service() as config:
        call(
            'iscsi.target.update',
            config['target']['id'],
            {'auth_networks': ["8.8.8.8/24", f"{good_ip}/24"] if valid else ["8.8.8.8/24", f"{bad_ip}/24"]}
        )
        portal_listen_details = config['portal']['listen'][0]
        assert target_login_test(
            f'{portal_listen_details["ip"]}:{portal_listen_details["port"]}',
            f'{config["global"]["basename"]}:{config["target"]["name"]}',
        ) is valid


@pytest.mark.parametrize('valid', [True, False])
def test_iscsi_auth_networks_netmask_16(my_ip4, valid):
    # good_ip will be our IP with the second last byte changed and last byte cleared
    n = (int(my_ip4.split('.')[2]) + 1) % 256
    good_ip = '.'.join(my_ip4.split('.')[:2] + [str(n), '0'])
    # bad_ip will be the good_ip with the second byte changed
    ip_list = good_ip.split('.')
    n = (int(ip_list[1]) + 1) % 256
    bad_ip = '.'.join([ip_list[0], str(n)] + ip_list[-2:])
    with configure_iscsi_service() as config:
        call(
            'iscsi.target.update',
            config['target']['id'],
            {'auth_networks': ["8.8.8.8/16", f"{good_ip}/16"] if valid else ["8.8.8.8/16", f"{bad_ip}/16"]}
        )
        portal_listen_details = config['portal']['listen'][0]
        assert target_login_test(
            f'{portal_listen_details["ip"]}:{portal_listen_details["port"]}',
            f'{config["global"]["basename"]}:{config["target"]["name"]}',
        ) is valid
