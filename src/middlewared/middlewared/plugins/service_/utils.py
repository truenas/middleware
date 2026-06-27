from __future__ import annotations

import enum
import typing

from middlewared.utils.privilege import credential_has_full_admin

if typing.TYPE_CHECKING:
    from middlewared.api.base.server.app import App


class ServiceWriteRole(enum.Enum):
    CIFS = 'SHARING_SMB_WRITE'
    NFS = 'SHARING_NFS_WRITE'
    ISCSITARGET = 'SHARING_ISCSI_WRITE'
    FTP = 'SHARING_FTP_WRITE'
    NVMET = 'SHARING_NVME_TARGET_WRITE'


def app_has_write_privilege_for_service(app: App | None, service: str) -> bool:
    if app is None:
        # Internal middleware call
        return True

    if app.authenticated_credentials is None:
        return False

    if not app.authenticated_credentials.is_user_session:
        return True

    if credential_has_full_admin(app.authenticated_credentials):
        return True

    if app.authenticated_credentials.has_role('SERVICE_WRITE'):
        return True

    try:
        required_role = ServiceWriteRole[service.upper()]
    except KeyError:
        return False

    return app.authenticated_credentials.has_role(required_role.value)
