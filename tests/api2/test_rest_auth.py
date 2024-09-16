import operator
import os
import pytest
import time
from unittest.mock import ANY

from functions import DELETE, POST, PUT
from middlewared.test.integration.assets.account import user, group, privilege
from middlewared.test.integration.assets.iscsi import iscsi_extent, iscsi_target
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.audit import expect_audit_log, expect_audit_method_calls


class TestAccountPrivilege:

    def test_create_privilege_audit(self):
        privilege = None
        try:
            with expect_audit_method_calls([{
                'method': 'privilege.create',
                'params': [{
                    'name': 'Test',
                    'web_shell': False,
                }],
                'description': 'Create privilege Test',
            }]):
                payload = {
                    'name': 'Test',
                    'web_shell': False,
                }
                result = POST(f'/privilege/', payload)
                assert result.status_code == 200, result.text
                privilege = result.json()
        finally:
            if privilege is not None:
                call('privilege.delete', privilege['id'])

    def test_update_privilege_audit(self):
        with privilege({
            'name': 'Test',
            'web_shell': False,
        }) as p:
            with expect_audit_method_calls([{
                'method': 'privilege.update',
                'params': [p['id'], {}],
                'description': 'Update privilege Test',
            }]):
                result = PUT(f'/privilege/id/{p["id"]}', {})
                assert result.status_code == 200, result.text

    def test_delete_privilege_audit(self):
        with privilege({
            'name': 'Test',
            'web_shell': False,
        }) as p:
            with expect_audit_method_calls([{
                'method': 'privilege.delete',
                'params': [p['id']],
                'description': 'Delete privilege Test',
            }]):
                result = DELETE(f'/privilege/id/{p["id"]}')
                assert result.status_code == 200, result.text


class TestAccount:

    def test_create_account_audit(self):
        user_id = None
        try:
            with expect_audit_method_calls([{
                'method': 'user.create',
                'params': [{
                    'username': 'sergey',
                    'full_name': 'Sergey',
                    'group_create': True,
                    'home': '/nonexistent',
                    'password': '********',
                }],
                'description': 'Create user sergey',
            }]):
                payload = {
                    'username': 'sergey',
                    'full_name': 'Sergey',
                    'group_create': True,
                    'home': '/nonexistent',
                    'password': 'password',
                }
                result = POST(f'/user/', payload)
                assert result.status_code == 200, result.text
                user_id = result.json()
        finally:
            if user_id is not None:
                call('user.delete', user_id)

    def test_update_account_audit(self):
        with user({
            'username': 'user2',
            'full_name': 'user2',
            'group_create': True,
            'password': 'test1234',
        }) as u:
            with expect_audit_method_calls([{
                'method': 'user.update',
                'params': [u['id'], {}],
                'description': 'Update user user2',
            }]):
                result = PUT(f'/user/id/{u["id"]}', {})
                assert result.status_code == 200, result.text

    def test_delete_account_audit(self):
        with user({
            'username': 'user2',
            'full_name': 'user2',
            'group_create': True,
            'password': 'test1234',
        }) as u:
            with expect_audit_method_calls([{
                'method': 'user.delete',
                'params': [u['id'], {}],
                'description': 'Delete user user2',
            }]):
                result = DELETE(f'/user/id/{u["id"]}')
                assert result.status_code == 200, result.text

    def test_create_group_audit(self):
        group_id = None
        try:
            with expect_audit_method_calls([{
                'method': 'group.create',
                'params': [{'name': 'group2'}],
                'description': 'Create group group2',
            }]):
                result = POST(f'/group/', {'name': 'group2'})
                assert result.status_code == 200, result.text
                group_id = result.json()
        finally:
            if group_id is not None:
                call('group.delete', group_id)

    def test_update_group_audit(self):
        with group({'name': 'group2'}) as g:
            with expect_audit_method_calls([{
                'method': 'group.update',
                'params': [g['id'], {}],
                'description': 'Update group group2',
            }]):
                result = PUT(f'/group/id/{g["id"]}', {})
                assert result.status_code == 200, result.text

    def test_delete_group_audit(self):
        with group({'name': 'group2'}) as g:
            with expect_audit_method_calls([{
                'method': 'group.delete',
                'params': [g['id'], {}],
                'description': 'Delete group group2',
            }]):
                result = DELETE(f'/group/id/{g["id"]}')
                assert result.status_code == 200, result.text


class TestAuditFTP:

    def test_ftp_config_audit(self):
        """Test the auditing of FTP configuration changes"""
        initial_ftp_config = call('ftp.config')
        try:
            # UPDATE
            payload = {
                'clients': 1000,
                'banner': 'Hello, from New York'
            }
            with expect_audit_method_calls([{
                'method': 'ftp.update',
                'params': [payload],
                'description': 'Update FTP configuration',
            }]):
                result = PUT('/ftp/', payload)
                assert result.status_code == 200, result.text
        finally:
            # Restore initial state
            restore_payload = {
                'clients': initial_ftp_config['clients'],
                'banner': initial_ftp_config['banner']
            }
            result = PUT('/ftp/', restore_payload)
            assert result.status_code == 200, result.text


@pytest.fixture
def report_exists(request):
    report_pathname = request.config.cache.get('report_pathname', None)
    assert report_pathname is not None
    yield report_pathname


class TestAudit:

    @pytest.mark.parametrize('payload, success', [
        ({'retention': 20}, True),
        ({'retention': 0}, False)
    ])
    def test_audit_config_audit(self, payload, success):
        """Test the auditing of Audit configuration changes"""
        initial_audit_config = call('audit.config')
        rest_operator = operator.eq if success else operator.ne
        expected_log_template = {
            'service_data': {
                'vers': {
                    'major': 0,
                    'minor': 1,
                },
                'origin': ANY,
                'protocol': 'REST',
                'credentials': {
                    'credentials': 'LOGIN_PASSWORD',
                    'credentials_data': {'username': 'root'},
                },
            },
            'event': 'METHOD_CALL',
            'event_data': {
                'authenticated': True,
                'authorized': True,
                'method': 'audit.update',
                'params': [payload],
                'description': 'Update Audit Configuration',
            },
            'success': success
        }
        try:
            with expect_audit_log([expected_log_template]):
                result = PUT('/audit/', payload)
                assert rest_operator(result.status_code, 200), result.text
        finally:
            # Restore initial state
            restore_payload = {'retention': initial_audit_config['retention']}
            result = PUT('/audit/', restore_payload)
            assert result.status_code == 200, result.text

    def test_audit_export_audit(self):
        """Test the auditing of the audit export function"""
        payload = {'export_format': 'CSV'}
        with expect_audit_method_calls([{
            'method': 'audit.export',
            'params': [payload],
            'description': 'Export Audit Data',
        }]):
            results = POST('/audit/export/', payload)
            assert results.status_code == 200, results.text

    def test_audit_download_audit(self, report_exists):
        """Test the auditing of the audit download function"""
        init_audit_query = call('audit.query', {
            'query-filters': [['event_data.method', '=', 'audit.download_report']],
            'query-options': {'select': ['event_data', 'success']}
        })
        init_len = len(init_audit_query)

        report_name = os.path.basename(report_exists)
        results = POST('/audit/download_report/', {'report_name': report_name})
        assert results.status_code == 200, results.text

        post_audit_query = call('audit.query', {
            'query-filters': [['event_data.method', '=', 'audit.download_report']],
            'query-options': {'select': ['event_data', 'success']}
        })
        post_len = len(post_audit_query)

        # This usually requires only one cycle
        count_down = 10
        while count_down > 0 and post_len == init_len:
            time.sleep(1)
            count_down -= 1
            post_audit_query = call('audit.query', {
                'query-filters': [['event_data.method', '=', 'audit.download_report']],
                'query-options': {'select': ['event_data', 'success']}
            })
            post_len = len(post_audit_query)

        assert count_down > 0, 'Timed out waiting for the audit entry'
        assert post_len > init_len

        # Confirm this download is recorded
        entry = post_audit_query[-1]
        event_data = entry['event_data']
        params = event_data['params'][0]
        assert report_name in params['report_name']


@pytest.fixture(scope='class')
def nfs_audit_dataset():
    with dataset('audit-test-nfs') as ds:
        yield ds


class TestAuditNFS:

    def test_nfs_config_audit(self):
        """Test the auditing of NFS configuration changes"""
        initial_nfs_config = call('nfs.config')
        try:
            # UPDATE
            payload = {
                'mountd_log': not initial_nfs_config['mountd_log'],
                'mountd_port': 618,
                'protocols': ['NFSV4']
            }
            with expect_audit_method_calls([{
                'method': 'nfs.update',
                'params': [payload],
                'description': 'Update NFS configuration',
            }]):
                result = PUT('/nfs/', payload)
                assert result.status_code == 200, result.text
        finally:
            # Restore initial state
            restore_payload = {
                'mountd_log': initial_nfs_config['mountd_log'],
                'mountd_port': initial_nfs_config['mountd_port'],
                'protocols': initial_nfs_config['protocols']
            }
            result = PUT('/nfs/', restore_payload)
            assert result.status_code == 200, result.text

    def test_nfs_share_audit(self, nfs_audit_dataset):
        """Test the auditing of NFS share operations"""
        nfs_export_path = f'/mnt/{nfs_audit_dataset}'
        try:
            # CREATE
            payload = {
                'comment': 'My Test Share',
                'path': nfs_export_path,
                'security': ['SYS']
            }
            with expect_audit_method_calls([{
                'method': 'sharing.nfs.create',
                'params': [payload],
                'description': f'NFS share create {nfs_export_path}',
            }]):
                results = POST('/sharing/nfs/', payload)
                assert results.status_code == 200, results.text
                share_config = results.json()
            # UPDATE
            payload = {'security': []}
            with expect_audit_method_calls([{
                'method': 'sharing.nfs.update',
                'params': [
                    share_config['id'],
                    payload,
                ],
                'description': f'NFS share update {nfs_export_path}',
            }]):
                results = PUT(f'/sharing/nfs/id/{share_config["id"]}/', payload)
                assert results.status_code == 200, results.text
                share_config = results.json()
        finally:
            if share_config is not None:
                # DELETE
                id_ = share_config['id']
                with expect_audit_method_calls([{
                    'method': 'sharing.nfs.delete',
                    'params': [id_],
                    'description': f'NFS share delete {nfs_export_path}',
                }]):
                    result = DELETE(f'/sharing/nfs/id/{id_}')
                    assert result.status_code == 200, result.text


@pytest.fixture(scope='class')
def initialize_zvol_for_iscsi_audit_tests():
    MB = 1024 * 1024
    MB_100 = 100 * MB
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


class TestAuditISCSI:

    def test_iscsi_auth_audit(self):
        auth_config = None
        tag = 1
        user1 = 'someuser1'
        user2 = 'someuser2'
        password1 = 'somepassword123'
        password2 = 'newpassword1234'
        try:
            REDACTED_SECRET = '********'
            # CREATE
            with expect_audit_method_calls([{
                'method': 'iscsi.auth.create',
                'params': [{
                    'tag': tag,
                    'user': user1,
                    'secret': REDACTED_SECRET,
                }],
                'description': f'Create iSCSI Authorized Access {user1} ({tag})',
            }]):
                payload = {
                    'tag': tag,
                    'user': user1,
                    'secret': password1,
                }
                result = POST('/iscsi/auth/', payload)
                assert result.status_code == 200, result.text
                auth_config = result.json()
            # UPDATE
            with expect_audit_method_calls([{
                'method': 'iscsi.auth.update',
                'params': [
                    auth_config['id'],
                    {
                        'user': user2,
                        'secret': REDACTED_SECRET,
                    }
                ],
                'description': f'Update iSCSI Authorized Access {user1} ({tag})',
            }]):
                payload = {
                    'user': user2,
                    'secret': password2,
                }
                result = PUT(f'/iscsi/auth/id/{auth_config["id"]}', payload)
                assert result.status_code == 200, result.text
                auth_config = result.json()
        finally:
            if auth_config is not None:
                # DELETE
                id_ = auth_config['id']
                with expect_audit_method_calls([{
                    'method': 'iscsi.auth.delete',
                    'params': [id_],
                    'description': f'Delete iSCSI Authorized Access {user2} ({tag})',
                }]):
                    result = DELETE(f'/iscsi/auth/id/{id_}')
                    assert result.status_code == 200, result.text

    def test_iscsi_extent_audit(self, initialize_zvol_for_iscsi_audit_tests):
        extent_name1 = 'extent1'
        extent_name2 = 'extent2'
        disk = f'zvol/{initialize_zvol_for_iscsi_audit_tests}'
        try:
            # CREATE
            with expect_audit_method_calls([{
                'method': 'iscsi.extent.create',
                'params': [{
                    'type': 'DISK',
                    'disk': disk,
                    'name': extent_name1,
                }],
                'description': f'Create iSCSI extent {extent_name1}',
            }]):
                payload = {
                    'type': 'DISK',
                    'disk': disk,
                    'name': extent_name1,
                }
                result = POST('/iscsi/extent/', payload)
                assert result.status_code == 200, result.text
                extent_config = result.json()
            # UPDATE
            with expect_audit_method_calls([{
                'method': 'iscsi.extent.update',
                'params': [
                    extent_config['id'],
                    {'name': extent_name2}
                ],
                'description': f'Update iSCSI extent {extent_name1}',
            }]):
                payload = {'name': extent_name2}
                result = PUT(f'/iscsi/extent/id/{extent_config["id"]}', payload)
                assert result.status_code == 200, result.text
                extent_config = result.json()
        finally:
            if extent_config is not None:
                # DELETE
                id_ = extent_config['id']
                with expect_audit_method_calls([{
                    'method': 'iscsi.extent.delete',
                    'params': [id_],
                    'description': f'Delete iSCSI extent {extent_name2}',
                }]):
                    result = DELETE(f'/iscsi/extent/id/{id_}')
                    assert result.status_code == 200, result.text

    def test_iscsi_global_audit(self):
        DEFAULT_ISCSI_PORT = 3260
        global_config = None
        try:
            # CREATE
            with expect_audit_method_calls([{
                'method': 'iscsi.global.update',
                'params': [{
                    'alua': True,
                    'listen_port': 13260,
                }],
                'description': 'Update iSCSI',
            }]):
                payload = {
                    'alua': True,
                    'listen_port': 13260,
                }
                result = PUT('/iscsi/global/', payload)
                assert result.status_code == 200, result.text
                global_config = result.json()
        finally:
            if global_config is not None:
                payload = {
                    'alua': False,
                    'listen_port': DEFAULT_ISCSI_PORT,
                }
                result = PUT('/iscsi/global/', payload)
                assert result.status_code == 200, result.text
                global_config = result.json()

    def test_iscsi_host_audit(self):
        host_config = None
        ip = '1.2.3.4'
        iqn = 'iqn.1993-08.org.debian:01:1234567890'
        description = 'Development VM (debian)'
        try:
            # CREATE
            with expect_audit_method_calls([{
                'method': 'iscsi.host.create',
                'params': [{
                    'ip': ip,
                    'iqns': [iqn],
                }],
                'description': f'Create iSCSI host {ip}',
            }]):
                payload = {
                    'ip': ip,
                    'iqns': [iqn],
                }
                result = POST('/iscsi/host/', payload)
                assert result.status_code == 200, result.text
                host_config = result.json()
            # UPDATE
            with expect_audit_method_calls([{
                'method': 'iscsi.host.update',
                'params': [
                    host_config['id'],
                    {'description': description}
                ],
                'description': f'Update iSCSI host {ip}',
            }]):
                payload = {'description': description}
                result = PUT(f'/iscsi/host/id/{host_config["id"]}', payload)
                assert result.status_code == 200, result.text
                host_config = result.json()
        finally:
            if host_config is not None:
                # DELETE
                id_ = host_config['id']
                with expect_audit_method_calls([{
                    'method': 'iscsi.host.delete',
                    'params': [id_],
                    'description': f'Delete iSCSI host {ip}',
                }]):
                    result = DELETE(f'/iscsi/host/id/{id_}')
                    assert result.status_code == 200, result.text

    def test_iscsi_initiator_audit(self):
        initiator_config = None
        comment = f'Default initiator (rest)'
        comment2 = f'INITIATOR (rest)'
        try:
            # CREATE
            with expect_audit_method_calls([{
                'method': 'iscsi.initiator.create',
                'params': [{
                    'comment': comment,
                    'initiators': [],
                }],
                'description': f'Create iSCSI initiator {comment}',
            }]):
                payload = {
                    'comment': comment,
                    'initiators': [],
                }
                result = POST('/iscsi/initiator/', payload)
                assert result.status_code == 200, result.text
                initiator_config = result.json()
            # UPDATE
            with expect_audit_method_calls([{
                'method': 'iscsi.initiator.update',
                'params': [
                    initiator_config['id'],
                    {
                        'comment': comment2,
                        'initiators': ['1.2.3.4', '5.6.7.8'],
                    }
                ],
                'description': f'Update iSCSI initiator {comment}',
            }]):
                payload = {
                    'comment': comment2,
                    'initiators': ['1.2.3.4', '5.6.7.8'],
                }
                result = PUT(f'/iscsi/initiator/id/{initiator_config["id"]}', payload)
                assert result.status_code == 200, result.text
                initiator_config = result.json()
        finally:
            if initiator_config is not None:
                # DELETE
                id_ = initiator_config['id']
                with expect_audit_method_calls([{
                    'method': 'iscsi.initiator.delete',
                    'params': [id_],
                    'description': f'Delete iSCSI initiator {comment2}',
                }]):
                    result = DELETE(f'/iscsi/initiator/id/{id_}')
                    assert result.status_code == 200, result.text

    def test_iscsi_portal_audit(self):
        portal_config = None
        comment = f'Default portal (rest)'
        comment2 = f'PORTAL (rest)'
        try:
            # CREATE
            with expect_audit_method_calls([{
                'method': 'iscsi.portal.create',
                'params': [{
                    'listen': [{'ip': '0.0.0.0'}],
                    'comment': comment,
                    'discovery_authmethod': 'NONE',
                }],
                'description': f'Create iSCSI portal {comment}',
            }]):
                payload = {
                    'listen': [{'ip': '0.0.0.0'}],
                    'comment': comment,
                    'discovery_authmethod': 'NONE',
                }
                result = POST('/iscsi/portal/', payload)
                assert result.status_code == 200, result.text
                portal_config = result.json()
            # UPDATE
            with expect_audit_method_calls([{
                'method': 'iscsi.portal.update',
                'params': [
                    portal_config['id'],
                    {'comment': comment2}
                ],
                'description': f'Update iSCSI portal {comment}',
            }]):
                payload = {'comment': comment2}
                result = PUT(f'/iscsi/portal/id/{portal_config["id"]}', payload)
                assert result.status_code == 200, result.text
                portal_config = result.json()
        finally:
            if portal_config is not None:
                # DELETE
                id_ = portal_config['id']
                with expect_audit_method_calls([{
                    'method': 'iscsi.portal.delete',
                    'params': [id_],
                    'description': f'Delete iSCSI portal {comment2}',
                }]):
                    result = DELETE(f'/iscsi/portal/id/{id_}')
                    assert result.status_code == 200, result.text

    def test_iscsi_target_audit(self):
        target_config = None
        target_name = 'target1'
        target_alias1 = f'target1 alias (rest)'
        target_alias2 = f'Updated target1 alias (rest)'
        try:
            # CREATE
            with expect_audit_method_calls([{
                'method': 'iscsi.target.create',
                'params': [{
                    'name': target_name,
                    'alias': target_alias1,
                }],
                'description': f'Create iSCSI target {target_name}',
            }]):
                payload = {
                    'name': target_name,
                    'alias': target_alias1,
                }
                result = POST('/iscsi/target/', payload)
                assert result.status_code == 200, result.text
                target_config = result.json()
            # UPDATE
            with expect_audit_method_calls([{
                'method': 'iscsi.target.update',
                'params': [
                    target_config['id'],
                    {'alias': target_alias2}
                ],
                'description': f'Update iSCSI target {target_name}',
            }]):
                payload = {'alias': target_alias2}
                result = PUT(f'/iscsi/target/id/{target_config["id"]}', payload)
                assert result.status_code == 200, result.text
                target_config = result.json()
        finally:
            if target_config is not None:
                # DELETE
                id_ = target_config['id']
                with expect_audit_method_calls([{
                    'method': 'iscsi.target.delete',
                    'params': [id_, True],
                    'description': f'Delete iSCSI target {target_name}',
                }]):
                    result = DELETE(f'/iscsi/target/id/{id_}', True)
                    assert result.status_code == 200, result.text

    def test_iscsi_targetextent_audit(self, initialize_zvol_for_iscsi_audit_tests):
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
                        'params': [{
                            'target': target_config['id'],
                            'extent': extent_config['id'],
                            'lunid': 0,
                        }],
                        'description': 'Create iSCSI target/LUN/extent mapping target1/0/extent1',
                    }]):
                        payload = {
                            'target': target_config['id'],
                            'extent': extent_config['id'],
                            'lunid': 0,
                        }
                        result = POST('/iscsi/targetextent/', payload)
                        assert result.status_code == 200, result.text
                        targetextent_config = result.json()
                    # UPDATE
                    with expect_audit_method_calls([{
                        'method': 'iscsi.targetextent.update',
                        'params': [
                            targetextent_config['id'],
                            {'lunid': 1}
                        ],
                        'description': 'Update iSCSI target/LUN/extent mapping target1/0/extent1',
                    }]):
                        payload = {'lunid': 1}
                        result = PUT(f'/iscsi/targetextent/id/{targetextent_config["id"]}', payload)
                        assert result.status_code == 200, result.text
                        targetextent_config = result.json()
                finally:
                    if targetextent_config is not None:
                        # DELETE
                        id_ = targetextent_config['id']
                        with expect_audit_method_calls([{
                            'method': 'iscsi.targetextent.delete',
                            'params': [id_, True],
                            'description': 'Delete iSCSI target/LUN/extent mapping target1/1/extent1',
                        }]):
                            result = DELETE(f'/iscsi/targetextent/id/{id_}', True)
                            assert result.status_code == 200, result.text
