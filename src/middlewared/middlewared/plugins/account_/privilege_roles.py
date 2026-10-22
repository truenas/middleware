from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

from middlewared.api.current import PrivilegeRolesEntry, QueryOptions
from middlewared.role import ROLES
from middlewared.utils.filter_list import filter_list

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ("dump_role_manager", "get_roles")

ROLES_ENTRIES = [
    PrivilegeRolesEntry(
        name=name,
        title=name,
        includes=role.includes,
        builtin=role.builtin,
        stig=role.stig,
    )
    for name, role in ROLES.items()
]


def get_roles(
    filters: list[Any],
    options: QueryOptions,
) -> list[PrivilegeRolesEntry] | PrivilegeRolesEntry | int:
    return filter_list(ROLES_ENTRIES, filters, options, PrivilegeRolesEntry)


def dump_role_manager(middleware: Middleware) -> dict[str, Any]:
    """
    Private method for CI in order to dump current information in role manager
    This is consumed in tests/unit/test_role_manager.py

    And possibly more tests
    """
    role_manager = middleware.role_manager

    # deepcopy is okay here because this should basically never be called and
    # we'd rather err on side of paranoia
    return {
        "method_resources": deepcopy(role_manager.methods.resources),
        "method_allowlists": deepcopy(role_manager.methods.allowlists_for_roles),
        "event_resources": deepcopy(role_manager.events.resources),
        "event_allowlists": deepcopy(role_manager.events.allowlists_for_roles),
    }
