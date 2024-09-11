import pytest

from middlewared.test.integration.assets.iscsi import iscsi_extent, iscsi_target
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.audit import expect_audit_method_calls

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


def test_iscsi_auth_audit():
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
            auth_config = call('iscsi.auth.create', payload)
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
            auth_config = call('iscsi.auth.update', auth_config['id'], payload)
    finally:
        if auth_config is not None:
            # DELETE
            id_ = auth_config['id']
            with expect_audit_method_calls([{
                'method': 'iscsi.auth.delete',
                'params': [id_],
                'description': f'Delete iSCSI Authorized Access {user2} ({tag})',
            }]):
                call('iscsi.auth.delete', id_)


def test_iscsi_extent_audit(initialize_zvol_for_iscsi_audit_tests):
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
            extent_config = call('iscsi.extent.create', payload)
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
            extent_config = call('iscsi.extent.update', extent_config['id'], payload)
    finally:
        if extent_config is not None:
            # DELETE
            id_ = extent_config['id']
            with expect_audit_method_calls([{
                'method': 'iscsi.extent.delete',
                'params': [id_],
                'description': f'Delete iSCSI extent {extent_name2}',
            }]):
                call('iscsi.extent.delete', id_)


def test_iscsi_global_audit():
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
            global_config = call('iscsi.global.update', payload)
    finally:
        if global_config is not None:
            payload = {
                'alua': False,
                'listen_port': DEFAULT_ISCSI_PORT,
            }
            global_config = call('iscsi.global.update', payload)


def test_iscsi_host_audit():
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
            host_config = call('iscsi.host.create', payload)
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
            host_config = call('iscsi.host.update', host_config['id'], payload)
    finally:
        if host_config is not None:
            # DELETE
            id_ = host_config['id']
            with expect_audit_method_calls([{
                'method': 'iscsi.host.delete',
                'params': [id_],
                'description': f'Delete iSCSI host {ip}',
            }]):
                call('iscsi.host.delete', id_)


def test_iscsi_initiator_audit():
    initiator_config = None
    comment = 'Default initiator'
    comment2 = 'INITIATOR'
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
            initiator_config = call('iscsi.initiator.create', payload)
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
            initiator_config = call('iscsi.initiator.update', initiator_config['id'], payload)
    finally:
        if initiator_config is not None:
            # DELETE
            id_ = initiator_config['id']
            with expect_audit_method_calls([{
                'method': 'iscsi.initiator.delete',
                'params': [id_],
                'description': f'Delete iSCSI initiator {comment2}',
            }]):
                call('iscsi.initiator.delete', id_)


def test_iscsi_portal_audit():
    portal_config = None
    comment = 'Default portal'
    comment2 = 'PORTAL'
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
            portal_config = call('iscsi.portal.create', payload)
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
            portal_config = call('iscsi.portal.update', portal_config['id'], payload)
    finally:
        if portal_config is not None:
            # DELETE
            id_ = portal_config['id']
            with expect_audit_method_calls([{
                'method': 'iscsi.portal.delete',
                'params': [id_],
                'description': f'Delete iSCSI portal {comment2}',
            }]):
                call('iscsi.portal.delete', id_)


def test_iscsi_target_audit():
    target_config = None
    target_name = 'target1'
    target_alias1 = 'target1 alias'
    target_alias2 = 'Updated target1 alias'
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
            target_config = call('iscsi.target.create', payload)
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
            target_config = call('iscsi.target.update', target_config['id'], payload)
    finally:
        if target_config is not None:
            # DELETE
            id_ = target_config['id']
            with expect_audit_method_calls([{
                'method': 'iscsi.target.delete',
                'params': [id_, True],
                'description': f'Delete iSCSI target {target_name}',
            }]):
                call('iscsi.target.delete', id_, True)


def test_iscsi_targetextent_audit(initialize_zvol_for_iscsi_audit_tests):

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
                    targetextent_config = call('iscsi.targetextent.create', payload)
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
                    targetextent_config = call('iscsi.targetextent.update', targetextent_config['id'], payload)
            finally:
                if targetextent_config is not None:
                    # DELETE
                    id_ = targetextent_config['id']
                    with expect_audit_method_calls([{
                        'method': 'iscsi.targetextent.delete',
                        'params': [id_, True],
                        'description': 'Delete iSCSI target/LUN/extent mapping target1/1/extent1',
                    }]):
                        call('iscsi.targetextent.delete', id_, True)
