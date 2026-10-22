from socket import AF_UNIX
import types

import pytest

from middlewared.api.current import ComposedPrivilege
from middlewared.auth import SessionManagerCredentials, UserSessionManagerCredentials
from middlewared.plugins.service.utils import app_has_write_privilege_for_service
from middlewared.utils.account.authenticator import UserPamAuthenticator
from middlewared.utils.auth import AA_LEVEL1
from middlewared.utils.origin import ConnectionOrigin
from middlewared.utils.privilege import (
    app_can_see_secrets,
    app_credential_full_admin_or_user,
    credential_full_admin_or_user,
    credential_has_full_admin,
    privilege_has_webui_access,
)
from middlewared.utils.privilege_constants import ALLOW_LIST_FULL_ADMIN

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
    ({'username': 'BOB', 'privilege': ComposedPrivilege(roles={'READONLY_ADMIN'}, allowlist=[])}, False),
    ({'username': 'BOB', 'privilege': ComposedPrivilege(roles={'FULL_ADMIN'}, allowlist=[])}, True),
    ({'username': 'BOB', 'privilege': ComposedPrivilege(roles=set(), allowlist=[ALLOW_LIST_FULL_ADMIN])}, True),
])
def test_privilege_has_full_admin(credential, expected):
    user_cred = UserSessionManagerCredentials(credential, AA_LEVEL1, pam_hdl)
    assert credential_has_full_admin(user_cred) == expected
    assert credential_full_admin_or_user(user_cred, 'canary') == expected
    assert credential_full_admin_or_user(user_cred, 'BOB')

    assert app_credential_full_admin_or_user(types.SimpleNamespace(authenticated_credentials=user_cred),
                                             'canary') == expected


@pytest.mark.parametrize('service,credential,expected', [
    ('cifs', {'privilege': ComposedPrivilege(roles={'READONLY_ADMIN'}, allowlist=[])}, False),
    ('cifs', {'privilege': ComposedPrivilege(roles={'FULL_ADMIN'}, allowlist=[])}, True),
    ('cifs', {'privilege': ComposedPrivilege(roles=set(), allowlist=[ALLOW_LIST_FULL_ADMIN])}, True),
    ('cifs', {'privilege': ComposedPrivilege(roles={'SHARING_SMB_WRITE'}, allowlist=[])}, True),
    ('cifs', {'privilege': ComposedPrivilege(roles={'SHARING_NFS_WRITE'}, allowlist=[])}, False),
    ('cifs', {'privilege': ComposedPrivilege(roles={'SHARING_ISCSI_WRITE'}, allowlist=[])}, False),
    ('cifs', {'privilege': ComposedPrivilege(roles={'SHARING_FTP_WRITE'}, allowlist=[])}, False),
    ('cifs', {'privilege': ComposedPrivilege(roles={'SHARING_NVME_TARGET_WRITE'}, allowlist=[])}, False),
    ('nfs', {'privilege': ComposedPrivilege(roles={'READONLY_ADMIN'}, allowlist=[])}, False),
    ('nfs', {'privilege': ComposedPrivilege(roles={'FULL_ADMIN'}, allowlist=[])}, True),
    ('nfs', {'privilege': ComposedPrivilege(roles=set(), allowlist=[ALLOW_LIST_FULL_ADMIN])}, True),
    ('nfs', {'privilege': ComposedPrivilege(roles={'SHARING_SMB_WRITE'}, allowlist=[])}, False),
    ('nfs', {'privilege': ComposedPrivilege(roles={'SHARING_NFS_WRITE'}, allowlist=[])}, True),
    ('nfs', {'privilege': ComposedPrivilege(roles={'SHARING_ISCSI_WRITE'}, allowlist=[])}, False),
    ('nfs', {'privilege': ComposedPrivilege(roles={'SHARING_FTP_WRITE'}, allowlist=[])}, False),
    ('nfs', {'privilege': ComposedPrivilege(roles={'SHARING_NVME_TARGET_WRITE'}, allowlist=[])}, False),
    ('iscsitarget', {'privilege': ComposedPrivilege(roles={'READONLY_ADMIN'}, allowlist=[])}, False),
    ('iscsitarget', {'privilege': ComposedPrivilege(roles={'FULL_ADMIN'}, allowlist=[])}, True),
    ('iscsitarget', {'privilege': ComposedPrivilege(roles=set(), allowlist=[ALLOW_LIST_FULL_ADMIN])}, True),
    ('iscsitarget', {'privilege': ComposedPrivilege(roles={'SHARING_SMB_WRITE'}, allowlist=[])}, False),
    ('iscsitarget', {'privilege': ComposedPrivilege(roles={'SHARING_NFS_WRITE'}, allowlist=[])}, False),
    ('iscsitarget', {'privilege': ComposedPrivilege(roles={'SHARING_ISCSI_WRITE'}, allowlist=[])}, True),
    ('iscsitarget', {'privilege': ComposedPrivilege(roles={'SHARING_FTP_WRITE'}, allowlist=[])}, False),
    ('iscsitarget', {'privilege': ComposedPrivilege(roles={'SHARING_NVME_TARGET_WRITE'}, allowlist=[])}, False),
    ('ftp', {'privilege': ComposedPrivilege(roles={'READONLY_ADMIN'}, allowlist=[])}, False),
    ('ftp', {'privilege': ComposedPrivilege(roles={'FULL_ADMIN'}, allowlist=[])}, True),
    ('ftp', {'privilege': ComposedPrivilege(roles=set(), allowlist=[ALLOW_LIST_FULL_ADMIN])}, True),
    ('ftp', {'privilege': ComposedPrivilege(roles={'SHARING_SMB_WRITE'}, allowlist=[])}, False),
    ('ftp', {'privilege': ComposedPrivilege(roles={'SHARING_NFS_WRITE'}, allowlist=[])}, False),
    ('ftp', {'privilege': ComposedPrivilege(roles={'SHARING_ISCSI_WRITE'}, allowlist=[])}, False),
    ('ftp', {'privilege': ComposedPrivilege(roles={'SHARING_FTP_WRITE'}, allowlist=[])}, True),
    ('ftp', {'privilege': ComposedPrivilege(roles={'SHARING_NVME_TARGET_WRITE'}, allowlist=[])}, False),
    ('nvmet', {'privilege': ComposedPrivilege(roles={'READONLY_ADMIN'}, allowlist=[])}, False),
    ('nvmet', {'privilege': ComposedPrivilege(roles={'FULL_ADMIN'}, allowlist=[])}, True),
    ('nvmet', {'privilege': ComposedPrivilege(roles=set(), allowlist=[ALLOW_LIST_FULL_ADMIN])}, True),
    ('nvmet', {'privilege': ComposedPrivilege(roles={'SHARING_SMB_WRITE'}, allowlist=[])}, False),
    ('nvmet', {'privilege': ComposedPrivilege(roles={'SHARING_NFS_WRITE'}, allowlist=[])}, False),
    ('nvmet', {'privilege': ComposedPrivilege(roles={'SHARING_ISCSI_WRITE'}, allowlist=[])}, False),
    ('nvmet', {'privilege': ComposedPrivilege(roles={'SHARING_FTP_WRITE'}, allowlist=[])}, False),
    ('nvmet', {'privilege': ComposedPrivilege(roles={'SHARING_NVME_TARGET_WRITE'}, allowlist=[])}, True),

])
def test_privilege_has_write_to_service(service, credential, expected):
    user_cred = UserSessionManagerCredentials({'username': 'BOB'} | credential, AA_LEVEL1, pam_hdl)
    assert app_has_write_privilege_for_service(types.SimpleNamespace(authenticated_credentials=user_cred),
                                               service) == expected


@pytest.mark.parametrize('roles,role_prefix,expected', [
    (['FULL_ADMIN'], None, True),
    (['FULL_ADMIN'], 'SHARING_SMB', True),
    (['SHARING_SMB_WRITE'], 'SHARING_SMB', True),
    (['SHARING_SMB_WRITE'], 'SHARING_NFS', False),
    (['SHARING_SMB_READ'], 'SHARING_SMB', False),
    (['READONLY_ADMIN'], 'SHARING_SMB', False),
    (['READONLY_ADMIN'], None, False),
])
def test_app_can_see_secrets_for_user_session(roles, role_prefix, expected):
    user_cred = UserSessionManagerCredentials(
        {'username': 'BOB', 'privilege': ComposedPrivilege(roles=set(roles), allowlist=[])}, AA_LEVEL1, pam_hdl,
    )
    app = types.SimpleNamespace(authenticated_credentials=user_cred)
    assert app_can_see_secrets(app, role_prefix) == expected


@pytest.mark.parametrize('app', [
    None,
    types.SimpleNamespace(authenticated_credentials=None),
    # Not a user session, i.e. an API key, which whitelists the methods it may call
    types.SimpleNamespace(authenticated_credentials=SessionManagerCredentials()),
])
def test_app_can_see_secrets_without_user_session(app):
    assert app_can_see_secrets(app, 'SHARING_SMB')
