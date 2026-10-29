from __future__ import annotations

import errno
from typing import TYPE_CHECKING, Any

from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import QueryOptions, SharingWebshareEntry
from middlewared.service import ValidationErrors

if TYPE_CHECKING:
    from .sharing_crud import SharingWebsharePart


async def validate_webshare(
    part: SharingWebsharePart,
    data: SharingWebshareEntry,
    schema_name: str,
    verrors: ValidationErrors,
    old: SharingWebshareEntry | None = None,
) -> dict[str, str | None]:
    """Validate a share and report the dataset components its path resolved to.

    `old` is the share being updated, which must not be compared against itself.
    """
    # Creating a share or enabling a disabled one needs the entitlement; any other edit, including
    # disabling, is allowed so a system that lost it keeps its shares manageable.
    if old is None or (data.enabled and not old.enabled):
        entitlement = await part.call2(part.s.truenas.entitlements.check, LicenseFeature.WEBSHARE)
        if not entitlement.entitled:
            verrors.add(schema_name, entitlement.message)

    await validate_share_name(part, data.name, schema_name, verrors, old)

    path = await resolve_share_path(part, data, schema_name, verrors)

    if data.enabled:
        await validate_share_path(part, data, schema_name, verrors, old)

    await validate_home_base(part, data, schema_name, verrors, old)

    return path


async def resolve_share_path(
    part: SharingWebsharePart,
    data: SharingWebshareEntry,
    schema_name: str,
    verrors: ValidationErrors,
) -> dict[str, str | None]:
    """Validate the shared path and report the dataset and relative path it resolved to.

    The create model excludes both fields, so they are reported rather than set on `data`.
    """
    path_data: dict[str, Any] = {part.path_field: data.path}
    await part.validate_path_field(path_data, schema_name, verrors, split_path=True)
    return {"dataset": path_data.get("dataset"), "relative_path": path_data.get("relative_path")}


async def validate_share_name(
    part: SharingWebsharePart,
    name: str,
    schema_name: str,
    verrors: ValidationErrors,
    old: SharingWebshareEntry | None = None,
) -> None:
    filters: list[Any] = [["name", "C=", name]]
    if old:
        filters.append(["id", "!=", old.id])

    if await part.query(filters, QueryOptions(select=["name"])):
        verrors.add(f"{schema_name}.name", "Share with this name already exists.", errno.EEXIST)


async def validate_share_path(
    part: SharingWebsharePart,
    data: SharingWebshareEntry,
    schema_name: str,
    verrors: ValidationErrors,
    old: SharingWebshareEntry | None = None,
) -> None:
    filters: list[Any] = [["enabled", "=", True]]
    if old:
        filters.append(["id", "!=", old.id])

    others = await part.query(filters, QueryOptions(select=["name", "path"]))

    schema_path = f"{schema_name}.{part.path_field}"
    for other in others:
        if await part.middleware.call("filesystem.is_child", data.path, other.path):
            verrors.add(
                schema_path,
                f"This path is already covered by the Webshare {other.name!r} at {other.path}.",
                errno.EEXIST,
            )
        elif await part.middleware.call("filesystem.is_child", other.path, data.path):
            verrors.add(
                schema_path,
                f"This path contains the Webshare {other.name!r} at {other.path}.",
                errno.EEXIST,
            )


async def validate_home_base(
    part: SharingWebsharePart,
    data: SharingWebshareEntry,
    schema_name: str,
    verrors: ValidationErrors,
    old: SharingWebshareEntry | None = None,
) -> None:
    if not data.is_home_base:
        return

    filters: list[Any] = [["is_home_base", "=", True]]
    if old:
        filters.append(["id", "!=", old.id])

    if await part.query(filters, QueryOptions(select=["id"])):
        verrors.add(
            f"{schema_name}.is_home_base", "Only one share can be configured as home directory base.", errno.EEXIST
        )

    if data.readonly:
        verrors.add(
            f"{schema_name}.readonly",
            "The home directory base share cannot be read-only, because Webshare creates home directories under it.",
        )
