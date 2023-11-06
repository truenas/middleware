from middlewared.role import ROLES
from middlewared.service import Service, filterable, filterable_returns, filter_list
from middlewared.schema import Dict, List, Str


class PrivilegeService(Service):

    class Config:
        namespace = "privilege"
        cli_namespace = "auth.privilege"

    @filterable
    @filterable_returns(Dict(
        "role",
        Str("name"),
        Str("title"),
        List("includes", items=[Str("name")]),
    ))
    async def roles(self, filters, options):
        """
        Get all available roles.
        """
        roles = [
            {
                "name": name,
                "title": name,
                "includes": role.includes,
            }
            for name, role in ROLES.items()
        ]

        return filter_list(roles, filters, options)
