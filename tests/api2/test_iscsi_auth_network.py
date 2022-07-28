import functools
import ipaddress
import os
import pytest
import sys

apifolder = os.getcwd()
sys.path.append(apifolder)

from middlewared.test.integration.assets.iscsi import target_login_test
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh

import contextlib
from auto_config import ip


@contextlib.contextmanager
def portal():
    portal_config = call('iscsi.portal.create', {'listen': [{'ip': ip}], 'discovery_authmethod': 'NONE'})
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


@functools.lru_cache(maxsize=None)
def get_nas_ip_subnet():
    for interface in call('interface.query'):
        for alias in (interface.get('state', {}).get('aliases', [])):
            if alias['address'] == ip:
                return alias['netmask']
    else:
        raise Exception(f'Unable to determine NAS {ip!r} IP subnet')


@pytest.mark.parametrize('valid', [True, False])
def test_iscsi_auth_networks(valid):
    with configure_iscsi_service() as config:
        auth_network = str(ipaddress.ip_network(f'{ip}/{get_nas_ip_subnet()}', False)) if valid else '8.8.8.8/32'
        call(
            'iscsi.target.update',
            config['target']['id'],
            {'auth_networks': [auth_network]}
        )
        portal_listen_details = config['portal']['listen'][0]
        assert target_login_test(
            f'{portal_listen_details["ip"]}:{portal_listen_details["port"]}',
            f'{config["global"]["basename"]}:{config["target"]["name"]}',
        ) is valid
