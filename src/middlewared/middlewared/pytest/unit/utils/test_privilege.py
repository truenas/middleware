import pytest
import types

from middlewared.auth import UserSessionManagerCredentials
from middlewared.utils.account.authenticator import UserPamAuthenticator
from middlewared.utils.auth import AA_LEVEL1
from middlewared.utils.origin import ConnectionOrigin
from middlewared.utils.privilege import (
    app_credential_full_admin_or_user,
    credential_has_full_admin,
    credential_full_admin_or_user,
    privilege_has_webui_access,
)
from middlewared.plugins.service_.utils import app_has_write_privilege_for_service
from socket import AF_UNIX


origin = ConnectionOrigin(family=AF_UNIX, pid=1, uid=0, gid=0, loginuid=0)
pam_hdl = UserPamAuthenticator(username='test', origin=origin)


@pytest.mark.parametrize('privilege,expected', [
    ({'roles': ['READONLY_ADMIN'], 'allowlist': []}, True),
    ({'roles': ['SHARING_ADMIN'], 'allowlist': []}, True),
    ({'roles': ['FULL_ADMIN'], 'allowlist': []}, True),
    ({'roles': ['SHARING_SMB_READ'], 'allowlist': []}, False),
])
def test_privilege_has_webui_access(privilege, expected):
    assert privilege_has_webui_access(privilege) == expected


@pytest.mark.parametrize('credential,expected', [
    ({'username': 'BOB', 'privilege': {'allowlist': [], 'roles': ['READONLY_ADMIN']}}, False),
    ({'username': 'BOB', 'privilege': {'allowlist': [], 'roles': ['FULL_ADMIN']}}, True),
    ({'username': 'BOB', 'privilege': {'allowlist': [{'method': '*', 'resource': '*'}], 'roles': []}}, True),
])
def test_privilege_has_full_admin(credential, expected):
    user_cred = UserSessionManagerCredentials(credential, AA_LEVEL1, pam_hdl)
    assert credential_has_full_admin(user_cred) == expected
    assert credential_full_admin_or_user(user_cred, 'canary') == expected
    assert credential_full_admin_or_user(user_cred, 'BOB')

    assert app_credential_full_admin_or_user(types.SimpleNamespace(authenticated_credentials=user_cred),
                                             'canary') == expected


@pytest.mark.parametrize('service,credential,expected', [
    ('cifs', {'privilege': {'allowlist': [], 'roles': ['READONLY_ADMIN']}}, False),
    ('cifs', {'privilege': {'allowlist': [], 'roles': ['FULL_ADMIN']}}, True),
    ('cifs', {'privilege': {'roles': [], 'allowlist': [{'method': '*', 'resource': '*'}]}}, True),
    ('cifs', {'privilege': {'allowlist': [], 'roles': ['SHARING_SMB_WRITE']}}, True),
    ('cifs', {'privilege': {'allowlist': [], 'roles': ['SHARING_NFS_WRITE']}}, False),
    ('cifs', {'privilege': {'allowlist': [], 'roles': ['SHARING_ISCSI_WRITE']}}, False),
    ('cifs', {'privilege': {'allowlist': [], 'roles': ['SHARING_FTP_WRITE']}}, False),
    ('cifs', {'privilege': {'allowlist': [], 'roles': ['SHARING_NVME_TARGET_WRITE']}}, False),
    ('nfs', {'privilege': {'allowlist': [], 'roles': ['READONLY_ADMIN']}}, False),
    ('nfs', {'privilege': {'allowlist': [], 'roles': ['FULL_ADMIN']}}, True),
    ('nfs', {'privilege': {'roles': [], 'allowlist': [{'method': '*', 'resource': '*'}]}}, True),
    ('nfs', {'privilege': {'allowlist': [], 'roles': ['SHARING_SMB_WRITE']}}, False),
    ('nfs', {'privilege': {'allowlist': [], 'roles': ['SHARING_NFS_WRITE']}}, True),
    ('nfs', {'privilege': {'allowlist': [], 'roles': ['SHARING_ISCSI_WRITE']}}, False),
    ('nfs', {'privilege': {'allowlist': [], 'roles': ['SHARING_FTP_WRITE']}}, False),
    ('nfs', {'privilege': {'allowlist': [], 'roles': ['SHARING_NVME_TARGET_WRITE']}}, False),
    ('iscsitarget', {'privilege': {'allowlist': [], 'roles': ['READONLY_ADMIN']}}, False),
    ('iscsitarget', {'privilege': {'allowlist': [], 'roles': ['FULL_ADMIN']}}, True),
    ('iscsitarget', {'privilege': {'roles': [], 'allowlist': [{'method': '*', 'resource': '*'}]}}, True),
    ('iscsitarget', {'privilege': {'allowlist': [], 'roles': ['SHARING_SMB_WRITE']}}, False),
    ('iscsitarget', {'privilege': {'allowlist': [], 'roles': ['SHARING_NFS_WRITE']}}, False),
    ('iscsitarget', {'privilege': {'allowlist': [], 'roles': ['SHARING_ISCSI_WRITE']}}, True),
    ('iscsitarget', {'privilege': {'allowlist': [], 'roles': ['SHARING_FTP_WRITE']}}, False),
    ('iscsitarget', {'privilege': {'allowlist': [], 'roles': ['SHARING_NVME_TARGET_WRITE']}}, False),
    ('ftp', {'privilege': {'allowlist': [], 'roles': ['READONLY_ADMIN']}}, False),
    ('ftp', {'privilege': {'allowlist': [], 'roles': ['FULL_ADMIN']}}, True),
    ('ftp', {'privilege': {'roles': [], 'allowlist': [{'method': '*', 'resource': '*'}]}}, True),
    ('ftp', {'privilege': {'allowlist': [], 'roles': ['SHARING_SMB_WRITE']}}, False),
    ('ftp', {'privilege': {'allowlist': [], 'roles': ['SHARING_NFS_WRITE']}}, False),
    ('ftp', {'privilege': {'allowlist': [], 'roles': ['SHARING_ISCSI_WRITE']}}, False),
    ('ftp', {'privilege': {'allowlist': [], 'roles': ['SHARING_FTP_WRITE']}}, True),
    ('ftp', {'privilege': {'allowlist': [], 'roles': ['SHARING_NVME_TARGET_WRITE']}}, False),
    ('nvmet', {'privilege': {'allowlist': [], 'roles': ['READONLY_ADMIN']}}, False),
    ('nvmet', {'privilege': {'allowlist': [], 'roles': ['FULL_ADMIN']}}, True),
    ('nvmet', {'privilege': {'roles': [], 'allowlist': [{'method': '*', 'resource': '*'}]}}, True),
    ('nvmet', {'privilege': {'allowlist': [], 'roles': ['SHARING_SMB_WRITE']}}, False),
    ('nvmet', {'privilege': {'allowlist': [], 'roles': ['SHARING_NFS_WRITE']}}, False),
    ('nvmet', {'privilege': {'allowlist': [], 'roles': ['SHARING_ISCSI_WRITE']}}, False),
    ('nvmet', {'privilege': {'allowlist': [], 'roles': ['SHARING_FTP_WRITE']}}, False),
    ('nvmet', {'privilege': {'allowlist': [], 'roles': ['SHARING_NVME_TARGET_WRITE']}}, True),

])
def test_privilege_has_write_to_service(service, credential, expected):
    user_cred = UserSessionManagerCredentials({'username': 'BOB'} | credential, AA_LEVEL1, pam_hdl)
    assert app_has_write_privilege_for_service(types.SimpleNamespace(authenticated_credentials=user_cred),
                                               service) == expected
