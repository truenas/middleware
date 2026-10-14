from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.api import api_method
from middlewared.api.current import (
    GroupCreate,
    GroupCreateArgs,
    GroupCreateResult,
    GroupDeleteArgs,
    GroupDeleteOptions,
    GroupDeleteResult,
    GroupEntry,
    GroupGetGroupObj,
    GroupGetGroupObjArgs,
    GroupGetGroupObjData,
    GroupGetGroupObjResult,
    GroupGetNextGidArgs,
    GroupGetNextGidResult,
    GroupHasPasswordEnabledUserArgs,
    GroupHasPasswordEnabledUserResult,
    GroupUpdate,
    GroupUpdateArgs,
    GroupUpdateResult,
)
from middlewared.service import GenericCRUDService, private
from middlewared.utils.types import AuditCallback

from .group_builtin import get_builtin_group_id
from .group_crud import GroupModel, GroupServicePart  # noqa: F401 (GroupModel registers the table)
from .group_members import get_password_enabled_users
from .group_obj import get_group_obj

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ("GroupService",)


class GroupService(GenericCRUDService[GroupEntry]):
    """
    Manage local groups
    """

    _svc_part: GroupServicePart

    class Config:
        datastore = "account.bsdgroups"
        datastore_prefix = "bsdgrp_"
        cli_namespace = "account.group"
        role_prefix = "ACCOUNT"
        entry = GroupEntry
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = GroupServicePart(self.context)

    @api_method(
        GroupCreateArgs,
        GroupCreateResult,
        audit="Create group",
        audit_extended=lambda data: data["name"],
        check_annotations=True,
    )
    async def do_create(self, data: GroupCreate) -> int:
        """
        Create a new group.
        """
        return await self._svc_part.do_create(data)

    @private
    async def create_internal(self, data: GroupCreate, reload_users: bool = True) -> int:
        return await self._svc_part.do_create(data, reload_users)

    @api_method(
        GroupUpdateArgs,
        GroupUpdateResult,
        audit="Update group",
        audit_callback=True,
        check_annotations=True,
    )
    async def do_update(self, audit_callback: AuditCallback, id_: int, data: GroupUpdate) -> int:
        """
        Update attributes of an existing group.
        """
        return await self._svc_part.do_update(audit_callback, id_, data)

    @api_method(
        GroupDeleteArgs,
        GroupDeleteResult,
        audit="Delete group",
        audit_callback=True,
        check_annotations=True,
    )
    async def do_delete(
        self,
        audit_callback: AuditCallback,
        id_: int,
        options: GroupDeleteOptions = GroupDeleteOptions(),
    ) -> int:
        """
        Delete group ``id``.
        """
        return await self._svc_part.do_delete(audit_callback, id_, options)

    @api_method(GroupGetNextGidArgs, GroupGetNextGidResult, roles=["ACCOUNT_READ"], check_annotations=True)
    async def get_next_gid(self) -> int:
        """
        Get the next available/free gid.
        """
        return await self._svc_part.get_next_gid()

    @api_method(GroupGetGroupObjArgs, GroupGetGroupObjResult, roles=["ACCOUNT_READ"], check_annotations=True)
    def get_group_obj(self, data: GroupGetGroupObj) -> GroupGetGroupObjData:
        """
        Returns dictionary containing information from struct grp for the group specified by either
        the ``groupname`` or ``gid``.

        If ``sid_info`` is specified, additional SMB / domain information is returned for the group.
        """
        return get_group_obj(self.context, data)

    @api_method(
        GroupHasPasswordEnabledUserArgs,
        GroupHasPasswordEnabledUserResult,
        roles=["ACCOUNT_READ"],
        check_annotations=True,
    )
    async def has_password_enabled_user(self, gids: list[int], exclude_user_ids: list[int] | None = None) -> bool:
        """
        Checks whether at least one local user with a password is a member of any of the ``gids``.
        """
        users = await get_password_enabled_users(self.context, gids, exclude_user_ids or [])
        return len(users) > 0

    @private
    async def get_password_enabled_users(
        self,
        gids: list[int],
        exclude_user_ids: list[int],
        groups: list[GroupEntry] | None = None,
    ) -> list[dict[str, Any]]:
        return await get_password_enabled_users(self.context, gids, exclude_user_ids, groups)

    @private
    async def get_builtin_group_id(self, group_name: str) -> int:
        return await get_builtin_group_id(self.context, group_name)
