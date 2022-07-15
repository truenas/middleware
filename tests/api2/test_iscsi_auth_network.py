import os
import sys

apifolder = os.getcwd()
sys.path.append(apifolder)

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh

import contextlib
from auto_config import ip

ZVOL_NAME = 'target343'
TARGET_NAME = 'target1'


@contextlib.contextmanager
def portal():
    portal_config = call('iscsi.portal.create', {'listen': [{'ip': ip, 'port': 3260}], 'discovery_authmethod': 'NONE'})
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
            with target('test_target', groups=[{'portal': portal_config['id'], 'initiator': initiator_config['id'], 'auth': None, 'authmethod': 'NONE'}]):
                pass


@contextlib.contextmanager
def iscsi_service():
    global_config = call('iscsi.global.update', {'isns_servers': [f'{ip}:3260']})
    portal = call('iscsi.portal.create', {'listen': [{'ip': ip, 'port': 3260}],
                                          'discovery_authmethod': 'NONE'})
    initiator = call('iscsi.initiator.create', {})
    target = call('iscsi.target.create', {'name': TARGET_NAME, 'groups': [{'portal': portal['id'],
                                                                         'initiator': initiator['id'],
                                                                         'auth': None, 'authmethod': 'NONE'}]})
    pool_name = call('kubernetes.config')['pool']
    call('pool.dataset.create', {'name': f'{pool_name}/{ZVOL_NAME}', 'type': 'VOLUME',
                                 'volsize': 51200, 'volblocksize': '512'})
    extent = call('iscsi.extent.create', {"name": "target1", "disk": f'zvol/{pool_name}/{ZVOL_NAME}'})
    call('iscsi.targetextent.create', {"target": target['id'], "extent": extent['id']})
    call('service.start', 'iscsitarget')
    yield {'target': target, 'portal': portal, 'global_config': global_config}
    call('service.stop', 'iscsitarget')
    call('iscsi.target.delete', target['id'])
    call('iscsi.initiator.delete', initiator['id'])
    call('iscsi.portal.delete', portal['id'])
    call('iscsi.extent.delete', extent['id'])
    call('pool.dataset.delete', f'{pool_name}/{ZVOL_NAME}')


@contextlib.contextmanager
def login_iscsi_target(target_name, base_name, portal_ip):
    try:
        ssh(f'iscsiadm -m node --targetname {target_name}:{base_name} --portal {portal_ip} --login')
        yield True
        ssh(f'iscsiadm -m node --targetname {target_name}:{base_name} --portal {portal_ip} --logout')
    except Exception as e:
        yield False


def authorized_ip_login_test(target, global_config, portal):
    call('iscsi.target.update', target['id'], {'auth_networks': [f'{ip}/24']})
    with login_iscsi_target(global_config["basename"], target["name"], ip) as is_login:
        assert is_login is True


def unauthorized_ip_login_test(target, global_config, portal):
    call('iscsi.target.update', target['id'], {'auth_networks': [f'40.40.40.0/24']})
    with login_iscsi_target(global_config["basename"], target["name"], ip) as is_login:
        assert is_login is False


def test_iscsi_target_auth_networks():
    with iscsi_service() as iscsi:
        authorized_ip_login_test(iscsi['target'], iscsi['global_config'], iscsi['portal'])
        unauthorized_ip_login_test(iscsi['target'], iscsi['global_config'], iscsi['portal'])
