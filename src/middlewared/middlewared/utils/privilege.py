from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

from middlewared.auth import TruenasNodeSessionManagerCredentials
from middlewared.role import ROLES

if TYPE_CHECKING:
    from middlewared.api.base.handler.full_admin import FullAdminField
    from middlewared.api.base.server.app import App
    from middlewared.auth import SessionManagerCredentials
    from middlewared.service_exception import ValidationErrors


def privilege_has_webui_access(privilege: dict[str, Any]) -> bool:
    """
    This method determines whether the specified privilege is sufficient
    to grant WebUI access. Current check is whether any of the roles for
    the privilege entry are not builtin, where "builtin" means an
    internal role that is used for defining access to particular methods
    (as opposed to non-builtin ones that were developed explicitly for
    assignment by administrators).

    The actual check performed here may change at a future time if we
    decide to add explicit `webui_access` flag to privilege.

    Returns True if privilege grants webui access and False if it does not.
    """
    return any(ROLES[role].builtin is False for role in privilege['roles'])


def credential_has_full_admin(credential: SessionManagerCredentials) -> bool:
    if credential.is_user_session and 'FULL_ADMIN' in credential.user['privilege']['roles']:  # type: ignore[attr-defined]
        return True

    if isinstance(credential, TruenasNodeSessionManagerCredentials):
        return True

    if credential.allowlist is None:
        return False

    return credential.allowlist.full_admin


def credential_full_admin_or_user(
    credential: SessionManagerCredentials | None,
    username: str
) -> bool:
    if credential is None:
        return False

    if credential_has_full_admin(credential):
        return True

    return credential.user['username'] == username  # type: ignore[attr-defined, no-any-return]


def app_credential_full_admin_or_user(
    app: App,
    username: str
) -> bool:
    """
    Privilege check for whether credential has full admin privileges
    or matches the specified username

    Returns True on success and False on failure

    Success:
    * app is None - internal middleware call
    * credential is a user session and has FULL_ADMIN role
    * credential has a wildcard entry in allow list
    * credential username matches `username` passed into this method
    """
    if app is None:
        return True

    return credential_full_admin_or_user(app.authenticated_credentials, username)


def privileges_group_mapping(
    privileges: list[dict[str, Any]],
    group_ids: list[int],
    groups_key: str,
) -> dict[str, Any]:
    roles = set()
    privileges_out = []

    group_ids_ = set(group_ids)
    for privilege in privileges:
        if set(privilege[groups_key]) & group_ids_:
            roles |= set(privilege['roles'])
            privileges_out.append(privilege)

    return {
        'roles': list(roles),
        'privileges': privileges_out
    }


def credential_is_limited_to_own_jobs(credential: SessionManagerCredentials | None) -> bool:
    if credential is None or not credential.is_user_session:
        return False

    return not credential_has_full_admin(credential)


_NOT_SUPPLIED = object()
"""Distinguishes a key that is absent from one whose value happens to be `None`."""


def app_needs_full_admin_check(app: App | None) -> bool:
    """Whether `app` must be checked against the `FullAdmin` fields of the method it is calling.

    False for an internal `middleware.call` (which has no `app` at all), for the HA peer, and for any credential
    that already holds `FULL_ADMIN`.
    """
    if app is None or app.authenticated_credentials is None:
        return False

    return not credential_has_full_admin(app.authenticated_credentials)


def check_full_admin_fields(
    schema_name: str,
    fields: Iterable[FullAdminField],
    new: Any,
    old: Any,
    verrors: ValidationErrors,
) -> None:
    """Add a validation error for every `FullAdmin` field that `new` mutates.

    Only a *change* is rejected, so a caller that reads an entry, edits an unrelated field and writes the whole
    thing back is unaffected. A field the caller did not mention is not a change, and neither is one whose value
    already matches what is stored.

    Call only when `app_needs_full_admin_check` returned true for the caller.

    :param schema_name: name of the payload parameter, prefixed to the attribute of each error.
    :param fields: the payload's `FullAdmin` fields, from `full_admin_payload_fields`.
    :param new: the payload as the caller supplied it, before validation fills in any defaults.
    :param old: the currently stored payload, or `None` when there is nothing stored yet (i.e. on create).
    :param verrors: collects the errors.
    """
    for path, default in fields:
        value = _lookup(new, path)
        if value is _NOT_SUPPLIED:
            continue

        current = _lookup(old, path) if old is not None else _NOT_SUPPLIED
        if current is _NOT_SUPPLIED:
            # Nothing to compare against: the entry does not exist yet, or it has no counterpart for this field.
            # Either way the baseline is what the caller would have got by staying silent.
            current = default

        if value == current:
            continue

        verrors.add(
            '.'.join((schema_name, *path)),
            'Changes to this parameter are restricted to users with full administrative privileges.',
        )


def _lookup(data: Any, path: Iterable[str]) -> Any:
    """Follow `path` into `data`, returning `_NOT_SUPPLIED` if any step is missing.

    `data` is a raw payload for most methods, but a validated model instance for a method declared with
    `check_annotations`, hence the attribute fallback.
    """
    for key in path:
        if isinstance(data, Mapping):
            if key not in data:
                return _NOT_SUPPLIED

            data = data[key]
        else:
            data = getattr(data, key, _NOT_SUPPLIED)
            if data is _NOT_SUPPLIED:
                return _NOT_SUPPLIED

    if hasattr(data, 'get_secret_value'):
        # Validating a `Secret` field wraps its value. Unwrap it so that it compares equal to the plain value the
        # same field holds in a raw payload.
        return data.get_secret_value()

    return data
