from middlewared.role import ROLES
from middlewared.service import Service, filterable, filterable_returns, filter_list, no_authz_required
from middlewared.schema import Bool, Dict, List, Str


class PrivilegeService(Service):

    class Config:
        namespace = "privilege"
        cli_namespace = "auth.privilege"

    @no_authz_required
    @filterable
    @filterable_returns(Dict(
        "role",
        Str("name"),
        Str("title"),
        List("includes", items=[Str("name")]),
        Bool("builtin")
    ))
    async def roles(self, filters, options):
        """
        Get all available roles.

        Each entry contains the following keys:

        `name` - the internal name of the role

        `includes` - list of other roles that this role includes. When user is
        granted this role, they will also receive permissions granted by all
        the included roles.

        `builtin` - role exists for internal backend purposes for access
        control.
        """
        roles = [
            {
                "name": name,
                "title": name,
                "includes": role.includes,
                "builtin": role.builtin,
            }
            for name, role in ROLES.items()
        ]

        return filter_list(roles, filters, options)
