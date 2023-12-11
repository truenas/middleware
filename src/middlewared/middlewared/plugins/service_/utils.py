import enum
from middlewared.utils.privilege import app_credential_full_admin_or_user

class ServiceWriteRole(enum.Enum):
    CIFS = 'SHARING_SMB_WRITE'
    NFS = 'SHARING_NFS_WRITE'
    ISCSITARGET = 'SHARING_ISCSI_WRITE'


def app_has_write_privilege_for_service(
    app: object | None,
    service: str
) -> bool:
    if app_credential_full_admin_or_user(app, None):
        return True

    if not app.authenticated_credentials:
        return False

    if app.authenticated_credentials.has_role('SERVICES_WRITE'):
        return True

    try:
        required_role = ServiceWriteRole[service.upper()]
    except KeyError:
        return False

    return app.authenticated_credentials.has_role(required_role.value)
