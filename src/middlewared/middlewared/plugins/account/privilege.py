from __future__ import annotations

from collections.abc import Collection
from typing import TYPE_CHECKING, Any, cast

from middlewared.api import Event, api_method
from middlewared.api.current import (
    ComposedPrivilege,
    GroupEntry,
    PrivilegeBecomeReadonlyArgs,
    PrivilegeBecomeReadonlyResult,
    PrivilegeCreate,
    PrivilegeCreateArgs,
    PrivilegeCreateResult,
    PrivilegeDeleteArgs,
    PrivilegeDeleteResult,
    PrivilegeEntry,
    PrivilegeRolesEntry,
    PrivilegeUpdate,
    PrivilegeUpdateArgs,
    PrivilegeUpdateResult,
    QueryOptions,
    UserEntry,
    UserWebUiLoginDisabledAddedEvent,
)
from middlewared.service import CallError, GenericCRUDService, filterable_api_method, private
from middlewared.utils.allowlist import Allowlist, AllowListItem
from middlewared.utils.privilege import BuiltinPrivileges
from middlewared.utils.types import AuditCallback

from .privilege_admins import before_group_delete, before_user_deactivation, local_administrators, used_local_gids
from .privilege_compose import (
    GroupsKey,
    compose_privilege,
    full_privilege,
    privileges_for_groups,
    roles_for_user,
)
from .privilege_crud import PrivilegeModel, PrivilegeServicePart  # noqa: F401 (PrivilegeModel registers the table)
from .privilege_roles import dump_role_manager, get_roles

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.main import Middleware

__all__ = ("PrivilegeService",)


class PrivilegeService(GenericCRUDService[PrivilegeEntry]):

    _svc_part: PrivilegeServicePart

    class Config:
        datastore = "account.privilege"
        cli_namespace = "auth.privilege"
        entry = PrivilegeEntry
        role_prefix = "PRIVILEGE"
        generic = True
        events = [
            Event(
                name="user.web_ui_login_disabled",
                description="Sent when root user login to the Web UI is disabled.",
                roles=["FULL_ADMIN"],
                models={
                    "ADDED": UserWebUiLoginDisabledAddedEvent,
                }
            )
        ]

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = PrivilegeServicePart(self.context)

    @api_method(
        PrivilegeCreateArgs,
        PrivilegeCreateResult,
        audit="Create privilege",
        audit_extended=lambda data: data["name"],
        check_annotations=True,
    )
    async def do_create(self, data: PrivilegeCreate) -> PrivilegeEntry:
        """
        Create a privilege.
        """
        return await self._svc_part.do_create(data)

    @api_method(
        PrivilegeUpdateArgs,
        PrivilegeUpdateResult,
        audit="Update privilege",
        audit_callback=True,
        check_annotations=True,
    )
    async def do_update(self, audit_callback: AuditCallback, id_: int, data: PrivilegeUpdate) -> PrivilegeEntry:
        """
        Update the privilege ``id``.
        """
        return await self._svc_part.do_update(audit_callback, id_, data)

    @api_method(
        PrivilegeDeleteArgs,
        PrivilegeDeleteResult,
        audit="Delete privilege",
        audit_callback=True,
        check_annotations=True,
    )
    async def do_delete(self, audit_callback: AuditCallback, id_: int) -> bool:
        """
        Delete the privilege ``id``.
        """
        return await self._svc_part.do_delete(audit_callback, id_)

    @api_method(
        PrivilegeBecomeReadonlyArgs,
        PrivilegeBecomeReadonlyResult,
        roles=["READONLY_ADMIN"],
        pass_app=True,
        pass_app_require=True,
        check_annotations=True,
    )
    async def become_readonly(self, app: App) -> None:
        """ Reduce the privileges of the current user credentials to ``READONLY_ADMINS``.
        This action prevents the session from making configuration changes. It also redacts
        sensitive data in API output. """
        credentials = app.authenticated_credentials
        if credentials is None:
            raise CallError("An unauthenticated session has no privileges to reduce")

        if not credentials.is_user_session:
            raise CallError(f"{credentials.class_name()}: unexpected credential type")

        # Compose a privilege based on only the READONLY_ADMINISTRATOR builtin privilege
        ro_admin = await self.middleware.call(
            "datastore.query",
            "account.privilege",
            [["builtin_name", "=", BuiltinPrivileges.READONLY_ADMINISTRATOR.value]],
            {"get": True},
        )
        composed_privilege = await compose_privilege(self.context, [ro_admin])

        # Set the current credential allowlist based on this privilege. The schema types the entries
        # loosely, but every one of them is an `AllowListItem`.
        allowlist = Allowlist(cast("list[AllowListItem]", composed_privilege.allowlist))
        credentials.allowlist = allowlist
        credentials.user["privilege"] = composed_privilege  # type: ignore[attr-defined]

    @filterable_api_method(item=PrivilegeRolesEntry, authorization_required=False, check_annotations=True)
    async def roles(
        self,
        filters: list[Any],
        options: QueryOptions,
    ) -> list[PrivilegeRolesEntry] | PrivilegeRolesEntry | int:
        """
        Get all available roles.
        """
        return get_roles(filters, options)

    @private
    async def before_user_password_disable(self, user: UserEntry) -> None:
        await before_user_deactivation(
            self.context,
            user,
            "After disabling password for this user no password-enabled local user",
        )

    @private
    async def before_user_delete(self, user: UserEntry) -> None:
        await before_user_deactivation(self.context, user, "After deleting this user no local user")

    @private
    async def before_group_delete(self, group: GroupEntry) -> None:
        await before_group_delete(self.context, group)

    @private
    async def used_local_gids(self) -> dict[int, dict[str, Any]]:
        return await used_local_gids(self.context)

    @private
    async def privileges_for_groups(
        self,
        groups_key: GroupsKey,
        group_ids: Collection[int],
    ) -> list[dict[str, Any]]:
        return await privileges_for_groups(self.context, groups_key, group_ids)

    @private
    async def compose_privilege(self, privileges: list[dict[str, Any]]) -> ComposedPrivilege:
        return await compose_privilege(self.context, privileges)

    @private
    async def roles_for_user(self, username: str) -> list[str]:
        return await roles_for_user(self.context, username)

    @private
    async def full_privilege(self) -> ComposedPrivilege:
        return full_privilege()

    @private
    async def always_has_root_password_enabled(
        self,
        users: list[UserEntry] | None = None,
        groups: list[GroupEntry] | None = None,
    ) -> bool:
        return await self._svc_part.always_has_root_password_enabled(users, groups)

    @private
    async def local_administrators(
        self,
        exclude_user_ids: list[int] | None = None,
        users: list[UserEntry] | None = None,
        groups: list[GroupEntry] | None = None,
    ) -> list[UserEntry]:
        return await local_administrators(self.context, exclude_user_ids, users, groups)

    @private
    async def dump_role_manager(self) -> dict[str, Any]:
        return dump_role_manager(self.middleware)
