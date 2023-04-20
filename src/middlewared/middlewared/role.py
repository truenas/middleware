from collections import defaultdict
from dataclasses import dataclass, field


@dataclass()
class Role:
    """
    An authenticated user role.

    :ivar includes: a list of other roles that this role includes. When user is granted this role, they will also
        receive permissions granted by all of the included roles.
    """

    includes: [str] = field(default_factory=list)


ROLES = {
    'KEYCHAIN_CREDENTIAL_READ': Role(),
    'KEYCHAIN_CREDENTIAL_WRITE': Role(includes=['KEYCHAIN_CREDENTIAL_READ']),
    'REPLICATION_TASK_CONFIG_READ': Role(),
    'REPLICATION_TASK_CONFIG_WRITE': Role(includes=['REPLICATION_TASK_CONFIG_READ']),
    'REPLICATION_TASK_READ': Role(),
    'REPLICATION_TASK_WRITE': Role(includes=['REPLICATION_TASK_READ']),
    'REPLICATION_TASK_WRITE_PULL': Role(includes=['REPLICATION_TASK_WRITE']),
    'SNAPSHOT_TASK_READ': Role(),
    'SNAPSHOT_TASK_WRITE': Role(includes=['SNAPSHOT_TASK_READ']),

    'SNAPSHOT_READ': Role(),
    'SNAPSHOT_WRITE': Role(includes=['SNAPSHOT_READ']),
    'SNAPSHOT_DELETE': Role(),

    'REPLICATION_MANAGER': Role(includes=['KEYCHAIN_CREDENTIAL_WRITE',
                                          'REPLICATION_TASK_CONFIG_WRITE',
                                          'REPLICATION_TASK_WRITE',
                                          'SNAPSHOT_TASK_WRITE',
                                          'SNAPSHOT_WRITE']),
}


class RoleManager:
    def __init__(self, roles):
        self.roles = roles
        self.methods = {}
        self.allowlists_for_roles = defaultdict(list)

    def register_method(self, method_name, roles):
        if method_name in self.methods:
            raise ValueError(f"Method {method_name!r} is already registered in this role manager")

        for role in roles:
            if role not in self.roles:
                raise ValueError(f"Invalid role {role!r}")

        self.methods[method_name] = roles

        for role in roles:
            self.allowlists_for_roles[role].append({"method": "CALL", "resource": method_name})

    def roles_for_role(self, role):
        if role not in self.roles:
            return set()

        return set.union({role}, *[self.roles_for_role(included_role) for included_role in self.roles[role].includes])

    def allowlist_for_role(self, role):
        return sum([
            self.allowlists_for_roles[role]
            for role in self.roles_for_role(role)
        ], [])
