import os
import sys

import pytest
from middlewared.test.integration.assets.iscsi import (iscsi_extent,
                                                       iscsi_target)
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.audit import expect_audit_method_calls

sys.path.append(os.getcwd())
from functions import DELETE, POST, PUT

REDACTED_SECRET = '********'
MB = 1024 * 1024
MB_100 = 100 * MB
DEFAULT_ISCSI_PORT = 3260


@pytest.fixture(scope='module')
def initialize_zvol_for_iscsi_audit_tests(request):
    with dataset('audit-test-iscsi') as ds:
        zvol = f'{ds}/zvol'
        payload = {
            'name': zvol,
            'type': 'VOLUME',
            'volsize': MB_100,
            'volblocksize': '16K'
        }
        zvol_config = call('pool.dataset.create', payload)
        try:
            yield zvol
        finally:
            call('pool.dataset.delete', zvol_config['id'])


@pytest.mark.parametrize('api', ['ws', 'rest'])
def test_iscsi_auth_audit(api):
    auth_config = None
    tag = 1
    user1 = 'someuser1'
    user2 = 'someuser2'
    password1 = 'somepassword123'
    password2 = 'newpassword1234'
    try:
        # CREATE
        with expect_audit_method_calls([{
            'method': 'iscsi.auth.create',
            'params': [
                {
                    'tag': tag,
                    'user': user1,
                    'secret': REDACTED_SECRET,
                }
            ],
            'description': f'Create iSCSI Authorized Access {user1} ({tag})',
        }]):
            payload = {
                'tag': tag,
                'user': user1,
                'secret': password1,
            }
            if api == 'ws':
                auth_config = call('iscsi.auth.create', payload)
            elif api == 'rest':
                result = POST('/iscsi/auth/', payload)
                assert result.status_code == 200, result.text
                auth_config = result.json()
            else:
                raise ValueError(api)
        # UPDATE
        with expect_audit_method_calls([{
            'method': 'iscsi.auth.update',
            'params': [
                auth_config['id'],
                {
                    'user': user2,
                    'secret': REDACTED_SECRET,
                }],
            'description': f'Update iSCSI Authorized Access {user1} ({tag})',
        }]):
            payload = {
                'user': user2,
                'secret': password2,
            }
            if api == 'ws':
                auth_config = call('iscsi.auth.update', auth_config['id'], payload)
            elif api == 'rest':
                result = PUT(f'/iscsi/auth/id/{auth_config["id"]}', payload)
                assert result.status_code == 200, result.text
                auth_config = result.json()
            else:
                raise ValueError(api)
    finally:
        if auth_config is not None:
            # DELETE
            id_ = auth_config['id']
            with expect_audit_method_calls([{
                'method': 'iscsi.auth.delete',
                'params': [id_],
                'description': f'Delete iSCSI Authorized Access {user2} ({tag})',
            }]):
                if api == 'ws':
                    call('iscsi.auth.delete', id_)
                elif api == 'rest':
                    result = DELETE(f'/iscsi/auth/id/{id_}')
                    assert result.status_code == 200, result.text
                else:
                    raise ValueError(api)


@pytest.mark.parametrize('api', ['ws', 'rest'])
def test_iscsi_extent_audit(api, initialize_zvol_for_iscsi_audit_tests):
    extent_name1 = 'extent1'
    extent_name2 = 'extent2'
    disk = f'zvol/{initialize_zvol_for_iscsi_audit_tests}'
    try:
        # CREATE
        with expect_audit_method_calls([{
            'method': 'iscsi.extent.create',
            'params': [
                {
                    'type': 'DISK',
                    'disk': disk,
                    'name': extent_name1,
                }
            ],
            'description': f'Create iSCSI extent {extent_name1}',
        }]):
            payload = {
                'type': 'DISK',
                'disk': disk,
                'name': extent_name1,
            }
            if api == 'ws':
                extent_config = call('iscsi.extent.create', payload)
            elif api == 'rest':
                result = POST('/iscsi/extent/', payload)
                assert result.status_code == 200, result.text
                extent_config = result.json()
            else:
                raise ValueError(api)
        # UPDATE
        with expect_audit_method_calls([{
            'method': 'iscsi.extent.update',
            'params': [
                extent_config['id'],
                {
                    'name': extent_name2,
                }],
            'description': f'Update iSCSI extent {extent_name1}',
        }]):
            payload = {
                'name': extent_name2,
            }
            if api == 'ws':
                extent_config = call('iscsi.extent.update', extent_config['id'], payload)
            elif api == 'rest':
                result = PUT(f'/iscsi/extent/id/{extent_config["id"]}', payload)
                assert result.status_code == 200, result.text
                extent_config = result.json()
            else:
                raise ValueError(api)
    finally:
        if extent_config is not None:
            # DELETE
            id_ = extent_config['id']
            with expect_audit_method_calls([{
                'method': 'iscsi.extent.delete',
                'params': [id_],
                'description': f'Delete iSCSI extent {extent_name2}',
            }]):
                if api == 'ws':
                    call('iscsi.extent.delete', id_)
                elif api == 'rest':
                    result = DELETE(f'/iscsi/extent/id/{id_}')
                    assert result.status_code == 200, result.text
                else:
                    raise ValueError(api)


@pytest.mark.parametrize('api', ['ws', 'rest'])
def test_iscsi_global_audit(api):
    global_config = None
    try:
        # CREATE
        with expect_audit_method_calls([{
            'method': 'iscsi.global.update',
            'params': [
                {
                    'alua': True,
                    'listen_port': 13260,
                }
            ],
            'description': 'Update iSCSI',
        }]):
            payload = {
                'alua': True,
                'listen_port': 13260,
            }
            if api == 'ws':
                global_config = call('iscsi.global.update', payload)
            elif api == 'rest':
                result = PUT('/iscsi/global/', payload)
                assert result.status_code == 200, result.text
                global_config = result.json()
            else:
                raise ValueError(api)
    finally:
        if global_config is not None:
            payload = {
                'alua': False,
                'listen_port': DEFAULT_ISCSI_PORT,
            }
            if api == 'ws':
                global_config = call('iscsi.global.update', payload)
            elif api == 'rest':
                result = PUT('/iscsi/global/', payload)
                assert result.status_code == 200, result.text
                global_config = result.json()
            else:
                raise ValueError(api)


@pytest.mark.parametrize('api', ['ws', 'rest'])
def test_iscsi_host_audit(api):
    host_config = None
    ip = '1.2.3.4'
    iqn = 'iqn.1993-08.org.debian:01:1234567890'
    description = 'Development VM (debian)'
    try:
        # CREATE
        with expect_audit_method_calls([{
            'method': 'iscsi.host.create',
            'params': [
                {
                    'ip': ip,
                    'iqns': [iqn],
                }
            ],
            'description': f'Create iSCSI host {ip}',
        }]):
            payload = {
                'ip': ip,
                'iqns': [iqn],
            }
            if api == 'ws':
                host_config = call('iscsi.host.create', payload)
            elif api == 'rest':
                result = POST('/iscsi/host/', payload)
                assert result.status_code == 200, result.text
                host_config = result.json()
            else:
                raise ValueError(api)
        # UPDATE
        with expect_audit_method_calls([{
            'method': 'iscsi.host.update',
            'params': [
                host_config['id'],
                {
                    'description': description,
                }],
            'description': f'Update iSCSI host {ip}',
        }]):
            payload = {
                'description': description,
            }
            if api == 'ws':
                host_config = call('iscsi.host.update', host_config['id'], payload)
            elif api == 'rest':
                result = PUT(f'/iscsi/host/id/{host_config["id"]}', payload)
                assert result.status_code == 200, result.text
                host_config = result.json()
            else:
                raise ValueError(api)
    finally:
        if host_config is not None:
            # DELETE
            id_ = host_config['id']
            with expect_audit_method_calls([{
                'method': 'iscsi.host.delete',
                'params': [id_],
                'description': f'Delete iSCSI host {ip}',
            }]):
                if api == 'ws':
                    call('iscsi.host.delete', id_)
                elif api == 'rest':
                    result = DELETE(f'/iscsi/host/id/{id_}')
                    assert result.status_code == 200, result.text
                else:
                    raise ValueError(api)


@pytest.mark.parametrize('api', ['ws', 'rest'])
def test_iscsi_initiator_audit(api):
    initiator_config = None
    comment = f'Default initiator ({api})'
    comment2 = f'INITIATOR ({api})'
    try:
        # CREATE
        with expect_audit_method_calls([{
            'method': 'iscsi.initiator.create',
            'params': [
                {
                    'comment': comment,
                    'initiators': [],
                }
            ],
            'description': f'Create iSCSI initiator {comment}',
        }]):
            payload = {
                'comment': comment,
                'initiators': [],
            }
            if api == 'ws':
                initiator_config = call('iscsi.initiator.create', payload)
            elif api == 'rest':
                result = POST('/iscsi/initiator/', payload)
                assert result.status_code == 200, result.text
                initiator_config = result.json()
            else:
                raise ValueError(api)
        # UPDATE
        with expect_audit_method_calls([{
            'method': 'iscsi.initiator.update',
            'params': [
                initiator_config['id'],
                {
                    'comment': comment2,
                    'initiators': ['1.2.3.4', '5.6.7.8'],
                }],
            'description': f'Update iSCSI initiator {comment}',
        }]):
            payload = {
                'comment': comment2,
                'initiators': ['1.2.3.4', '5.6.7.8'],
            }
            if api == 'ws':
                initiator_config = call('iscsi.initiator.update', initiator_config['id'], payload)
            elif api == 'rest':
                result = PUT(f'/iscsi/initiator/id/{initiator_config["id"]}', payload)
                assert result.status_code == 200, result.text
                initiator_config = result.json()
            else:
                raise ValueError(api)
    finally:
        if initiator_config is not None:
            # DELETE
            id_ = initiator_config['id']
            with expect_audit_method_calls([{
                'method': 'iscsi.initiator.delete',
                'params': [id_],
                'description': f'Delete iSCSI initiator {comment2}',
            }]):
                if api == 'ws':
                    call('iscsi.initiator.delete', id_)
                elif api == 'rest':
                    result = DELETE(f'/iscsi/initiator/id/{id_}')
                    assert result.status_code == 200, result.text
                else:
                    raise ValueError(api)


@pytest.mark.parametrize('api', ['ws', 'rest'])
def test_iscsi_portal_audit(api):
    portal_config = None
    comment = f'Default portal ({api})'
    comment2 = f'PORTAL ({api})'
    try:
        # CREATE
        with expect_audit_method_calls([{
            'method': 'iscsi.portal.create',
            'params': [
                {
                    'listen': [{'ip': '0.0.0.0'}],
                    'comment': comment,
                    'discovery_authmethod': 'NONE',
                }
            ],
            'description': f'Create iSCSI portal {comment}',
        }]):
            payload = {
                'listen': [{'ip': '0.0.0.0'}],
                'comment': comment,
                'discovery_authmethod': 'NONE',
            }
            if api == 'ws':
                portal_config = call('iscsi.portal.create', payload)
            elif api == 'rest':
                result = POST('/iscsi/portal/', payload)
                assert result.status_code == 200, result.text
                portal_config = result.json()
            else:
                raise ValueError(api)
        # UPDATE
        with expect_audit_method_calls([{
            'method': 'iscsi.portal.update',
            'params': [
                portal_config['id'],
                {
                    'comment': comment2,
                }],
            'description': f'Update iSCSI portal {comment}',
        }]):
            payload = {
                'comment': comment2,
            }
            if api == 'ws':
                portal_config = call('iscsi.portal.update', portal_config['id'], payload)
            elif api == 'rest':
                result = PUT(f'/iscsi/portal/id/{portal_config["id"]}', payload)
                assert result.status_code == 200, result.text
                portal_config = result.json()
            else:
                raise ValueError(api)
    finally:
        if portal_config is not None:
            # DELETE
            id_ = portal_config['id']
            with expect_audit_method_calls([{
                'method': 'iscsi.portal.delete',
                'params': [id_],
                'description': f'Delete iSCSI portal {comment2}',
            }]):
                if api == 'ws':
                    call('iscsi.portal.delete', id_)
                elif api == 'rest':
                    result = DELETE(f'/iscsi/portal/id/{id_}')
                    assert result.status_code == 200, result.text
                else:
                    raise ValueError(api)


@pytest.mark.parametrize('api', ['ws', 'rest'])
def test_iscsi_target_audit(api):
    target_config = None
    target_name = 'target1'
    target_alias1 = f'target1 alias ({api})'
    target_alias2 = f'Updated target1 alias ({api})'
    try:
        # CREATE
        with expect_audit_method_calls([{
            'method': 'iscsi.target.create',
            'params': [
                {
                    'name': target_name,
                    'alias': target_alias1,
                }
            ],
            'description': f'Create iSCSI target {target_name}',
        }]):
            payload = {
                'name': target_name,
                'alias': target_alias1,
            }
            if api == 'ws':
                target_config = call('iscsi.target.create', payload)
            elif api == 'rest':
                result = POST('/iscsi/target/', payload)
                assert result.status_code == 200, result.text
                target_config = result.json()
            else:
                raise ValueError(api)
        # UPDATE
        with expect_audit_method_calls([{
            'method': 'iscsi.target.update',
            'params': [
                target_config['id'],
                {
                    'alias': target_alias2,
                }],
            'description': f'Update iSCSI target {target_name}',
        }]):
            payload = {
                'alias': target_alias2,
            }
            if api == 'ws':
                target_config = call('iscsi.target.update', target_config['id'], payload)
            elif api == 'rest':
                result = PUT(f'/iscsi/target/id/{target_config["id"]}', payload)
                assert result.status_code == 200, result.text
                target_config = result.json()
            else:
                raise ValueError(api)
    finally:
        if target_config is not None:
            # DELETE
            id_ = target_config['id']
            with expect_audit_method_calls([{
                'method': 'iscsi.target.delete',
                'params': [id_, True],
                'description': f'Delete iSCSI target {target_name}',
            }]):
                if api == 'ws':
                    call('iscsi.target.delete', id_, True)
                elif api == 'rest':
                    result = DELETE(f'/iscsi/target/id/{id_}', True)
                    assert result.status_code == 200, result.text
                else:
                    raise ValueError(api)


@pytest.mark.parametrize('api', ['ws', 'rest'])
def test_iscsi_targetextent_audit(api, initialize_zvol_for_iscsi_audit_tests):

    payload = {
        'type': 'DISK',
        'disk': f'zvol/{initialize_zvol_for_iscsi_audit_tests}',
        'name': 'extent1',
    }
    with iscsi_extent(payload) as extent_config:
        with iscsi_target({'name': 'target1', 'alias': 'Audit test'}) as target_config:
            targetextent_config = None
            try:
                # CREATE
                with expect_audit_method_calls([{
                    'method': 'iscsi.targetextent.create',
                    'params': [
                        {
                            'target': target_config['id'],
                            'extent': extent_config['id'],
                            'lunid': 0,
                        }
                    ],
                    'description': 'Create iSCSI target/LUN/extent mapping target1/0/extent1',
                }]):
                    payload = {
                        'target': target_config['id'],
                        'extent': extent_config['id'],
                        'lunid': 0,
                    }
                    if api == 'ws':
                        targetextent_config = call('iscsi.targetextent.create', payload)
                    elif api == 'rest':
                        result = POST('/iscsi/targetextent/', payload)
                        assert result.status_code == 200, result.text
                        targetextent_config = result.json()
                    else:
                        raise ValueError(api)
                # UPDATE
                with expect_audit_method_calls([{
                    'method': 'iscsi.targetextent.update',
                    'params': [
                        targetextent_config['id'],
                        {
                            'lunid': 1,
                        }],
                    'description': 'Update iSCSI target/LUN/extent mapping target1/0/extent1',
                }]):
                    payload = {
                        'lunid': 1,
                    }
                    if api == 'ws':
                        targetextent_config = call('iscsi.targetextent.update', targetextent_config['id'], payload)
                    elif api == 'rest':
                        result = PUT(f'/iscsi/targetextent/id/{targetextent_config["id"]}', payload)
                        assert result.status_code == 200, result.text
                        targetextent_config = result.json()
                    else:
                        raise ValueError(api)
            finally:
                if targetextent_config is not None:
                    # DELETE
                    id_ = targetextent_config['id']
                    with expect_audit_method_calls([{
                        'method': 'iscsi.targetextent.delete',
                        'params': [id_, True],
                        'description': 'Delete iSCSI target/LUN/extent mapping target1/1/extent1',
                    }]):
                        if api == 'ws':
                            call('iscsi.targetextent.delete', id_, True)
                        elif api == 'rest':
                            result = DELETE(f'/iscsi/targetextent/id/{id_}', True)
                            assert result.status_code == 200, result.text
                        else:
                            raise ValueError(api)
