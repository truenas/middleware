import os
import sys

apifolder = os.getcwd()
sys.path.append(apifolder)
from middlewared.test.integration.utils import call, ssh

import contextlib
import pytest
from auto_config import ip

ZVOL_NAME = 'target343'
TARGET_NAME = 'target1'


@contextlib.contextmanager
def dependencies():
    ssh('chmod +x /usr/bin/apt*')
    ssh('apt install open-iscsi')
    yield


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
    with dependencies():
        with iscsi_service() as iscsi:
            authorized_ip_login_test(iscsi['target'], iscsi['global_config'], iscsi['portal'])
            unauthorized_ip_login_test(iscsi['target'], iscsi['global_config'], iscsi['portal'])
