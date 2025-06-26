from copy import deepcopy

from middlewared.api.current import PrivilegeRolesEntry

from middlewared.role import ROLES
from middlewared.service import Service, filterable_api_method, filter_list, private


class PrivilegeService(Service):

    class Config:
        namespace = "privilege"
        cli_namespace = "auth.privilege"

    @filterable_api_method(item=PrivilegeRolesEntry, authorization_required=False)
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
                "stig": role.stig,
            }
            for name, role in ROLES.items()
        ]

        return filter_list(roles, filters, options)

    @private
    async def dump_role_manager(self):
        """
        Private method for CI in order to dump current information in role manager
        This is consumed in tests/unit/test_role_manager.py

        And possibly more tests
        """

        # deepcopy is okay here because this should basically never be called and
        # we'd rather err on side of paranoia
        method_resources = deepcopy(self.middleware.role_manager.methods.resources)
        method_allowlists = deepcopy(self.middleware.role_manager.methods.allowlists_for_roles)

        event_resources = deepcopy(self.middleware.role_manager.events.resources)
        event_allowlists = deepcopy(self.middleware.role_manager.events.allowlists_for_roles)

        return {
            'method_resources': method_resources,
            'method_allowlists': method_allowlists,
            'event_resources': event_resources,
            'event_allowlists': event_allowlists
        }
