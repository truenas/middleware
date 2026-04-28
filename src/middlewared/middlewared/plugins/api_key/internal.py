from __future__ import annotations

import errno
from typing import TYPE_CHECKING, Any

from middlewared.api.current import ApiKeyEntry
from middlewared.plugins.auth_.login_ex_impl import login_ex_api_key_plain
from middlewared.service import CallError, ServiceContext, ValidationErrors
from middlewared.utils.privilege import credential_has_full_admin
from middlewared.utils.time_utils import utc_now
from truenas_pypam import PAMCode

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.utils.origin import ConnectionOrigin


__all__ = (
    'api_key_privilege_check',
    'authenticate_impl',
    'check_status',
    'revoke_impl',
    'validate_api_key_data',
)


def api_key_privilege_check(
    app: App | None,
    username: str,
    method_name: str,
) -> None:
    if app is None or app.authenticated_credentials is None or not app.authenticated_credentials.is_user_session:
        # Internal session - no privilege check required
        return

    creds = app.authenticated_credentials
    if credential_has_full_admin(creds):
        return

    # `has_role` is declared on the untyped base `SessionManagerCredentials`.
    if creds.has_role('API_KEY_WRITE'):  # type: ignore[no-untyped-call]
        return

    # `.user` only exists on the `UserSessionManagerCredentials` subclass
    # (and `TokenSessionManagerCredentials` when wrapping a user session) -
    # is_user_session has already been checked above.
    auth_user = creds.user['username']  # type: ignore[attr-defined]

    if auth_user != username:
        raise CallError(
            f'{auth_user}: authenticated user lacks privileges to create or '
            'modify API keys of other users.', errno.EACCES
        )


async def validate_api_key_data(
    context: ServiceContext,
    datastore: str,
    schema_name: str,
    data: dict[str, Any],
    verrors: ValidationErrors,
    id_: int | None = None,
) -> None:
    rows = await context.middleware.call(
        'datastore.query', datastore,
        [['name', '=', data['name']], ['id', '!=', id_]],
    )
    if rows:
        verrors.add(schema_name, 'name must be unique')

    if (expiration := data.get('expires_at')) is not None:
        if utc_now(naive=False) > expiration:
            verrors.add(schema_name, 'Expiration date is in the past')


async def check_status(context: ServiceContext) -> None:
    await context.call2(context.s.alert.alert_source_clear_run, 'ApiKeyRevoked')


async def authenticate_impl(
    context: ServiceContext,
    app: App,
    key: str,
    origin: ConnectionOrigin,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Wrapper around `auth.authenticate` for the file upload endpoint."""
    try:
        key_id = int(key.split('-', 1)[0])
    except ValueError:
        return None

    auth_ctx = app.authentication_context
    if not auth_ctx:
        raise CallError('Authentication context was not initialized')

    if auth_ctx.pam_hdl:
        raise CallError(f'{auth_ctx.pam_hdl}: Unexpected existing authenticator')

    entry: ApiKeyEntry = await context.call2(context.s.api_key.get_instance, key_id)

    pam_resp, cred = await context.to_thread(
        login_ex_api_key_plain,
        context.middleware,
        app=app,
        auth_ctx=auth_ctx,
        auth_data={
            'username': entry.username or 'root',
            'api_key': key,
        },
    )

    if pam_resp.code != PAMCode.PAM_SUCCESS or cred is None:
        return None

    return (cred.user, {
        'id': entry.id,
        'name': entry.name,
    })


async def revoke_impl(
    context: ServiceContext,
    datastore: str,
    key_id: int,
    reason: str,
) -> None:
    """Revoke an API key, deactivate it in the pam_tdb file, and clear/raise the alert."""
    await context.middleware.call(
        'datastore.update', datastore, key_id,
        {'expiry': -1, 'revoked_reason': reason},
    )
    await context.middleware.call('etc.generate', 'pam')
    await check_status(context)
