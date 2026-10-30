from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api.current import PrivilegeCreate
from middlewared.service import ValidationErrors

from .privilege_groups import get_groups, resolve_ds_groups, resolve_local_groups

if TYPE_CHECKING:
    from .privilege_crud import PrivilegeServicePart

__all__ = ("validate_privilege",)


async def validate_privilege(
    part: PrivilegeServicePart,
    schema_name: str,
    data: PrivilegeCreate,
    id_: int | None = None,
) -> None:
    verrors = ValidationErrors()

    await part._ensure_unique(verrors, schema_name, "name", data.name, id_)

    groups = await get_groups(part)
    for i, local_group_id in enumerate(data.local_groups):
        if not resolve_local_groups(groups, [local_group_id], include_nonexistent=False):
            verrors.add(
                f"{schema_name}.local_groups.{i}",
                f"{local_group_id}: local group does not exist. "
                "This error may be addressed by either re-creating the missing group "
                "with the specified group id or removing this entry from the privilege.",
            )
            # If the group does not exist then cannot check the userns_idmap
            continue

        # Currently only local groups may have privileges
        if groups.by_gid[local_group_id].userns_idmap:
            verrors.add(
                f"{schema_name}.local_groups.{i}",
                "Privileges may not be granted to groups that have a user namespace idmap configured.",
            )

    for i, ds_group_id in enumerate(data.ds_groups):
        if not await resolve_ds_groups(part, groups, [ds_group_id], include_nonexistent=False):
            verrors.add(
                f"{schema_name}.ds_groups.{i}",
                f"{ds_group_id}: directory service group does not exist. "
                "If the directory service state is healthy, then this error may be "
                "addressed by removing this entry from the privilege.",
            )

    for i, role in enumerate(data.roles):
        if role not in part.middleware.role_manager.roles:
            verrors.add(f"{schema_name}.roles.{i}", "Invalid role")

    verrors.check()
