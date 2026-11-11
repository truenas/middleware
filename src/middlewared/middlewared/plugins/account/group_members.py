from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.api.current import GroupEntry

from .password import unixhash_is_valid

if TYPE_CHECKING:
    from middlewared.service import ServiceContext


async def get_password_enabled_users(
    context: ServiceContext,
    gids: list[int],
    exclude_user_ids: list[int],
    groups: list[GroupEntry] | None = None,
) -> list[dict[str, Any]]:
    if groups is None:
        groups = await context.call2(context.s.group.query, [["local", "=", True]])

    result = []
    result_user_ids = set()
    group_ids = {group.id for group in groups if group.gid in gids}

    for membership in await context.middleware.call(
        "datastore.query",
        "account.bsdgroupmembership",
        [
            [
                "OR",
                [
                    ["group", "in", group_ids],
                    ["user.bsdusr_group", "in", group_ids],  # primary group
                ],
            ],
            ["user", "nin", set(exclude_user_ids)],
        ],
        {"prefix": "bsdgrpmember_"},
    ):
        user = membership["user"]
        if user["id"] in result_user_ids:
            continue

        if user["bsdusr_locked"] or user["bsdusr_password_disabled"]:
            continue

        if not unixhash_is_valid(user["bsdusr_unixhash"]):
            continue

        result.append({k.removeprefix("bsdusr_"): v for k, v in user.items()})
        result_user_ids.add(user["id"])

    return result
