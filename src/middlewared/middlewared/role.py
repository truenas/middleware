from collections import defaultdict
from dataclasses import dataclass, field


@dataclass()
class Role:
    """
    An authenticated user role.

    :ivar includes: a list of other roles that this role includes. When user is granted this role, they will also
        receive permissions granted by all the included roles.
    :ivar full_admin: if `True` then this role will allow calling all methods.
    """

    includes: [str] = field(default_factory=list)
    full_admin: bool = False
    builtin: bool = True


ROLES = {
    'AUTH_SESSIONS_READ': Role(),
    'AUTH_SESSIONS_WRITE': Role(includes=['AUTH_SESSIONS_READ']),
    'FILESYSTEM_ATTRS_READ': Role(),
    'FILESYSTEM_ATTRS_WRITE': Role(includes=['FILESYSTEM_ATTRS_READ']),
    'FILESYSTEM_DATA_READ': Role(),
    'FILESYSTEM_DATA_WRITE': Role(includes=['FILESYSTEM_DATA_READ']),
    'FILESYSTEM_FULL_CONTROL': Role(includes=['FILESYSTEM_ATTRS_WRITE',
                                              'FILESYSTEM_DATA_WRITE']),
    'REPORTING_READ': Role(),

    'FULL_ADMIN': Role(full_admin=True, builtin=False),
    'READONLY': Role(includes=['ALERT_LIST_READ',
                               'AUTH_SESSIONS_READ',
                               'CLOUD_SYNC_READ',
                               'DATASET_READ',
                               'FILESYSTEM_ATTRS_READ',
                               'NETWORK_GENERAL_READ',
                               'SHARING_READ',
                               'KEYCHAIN_CREDENTIAL_READ',
                               'REPORTING_READ',
                               'REPLICATION_TASK_CONFIG_READ',
                               'REPLICATION_TASK_READ',
                               'SERVICE_READ',
                               'SNAPSHOT_TASK_READ'],
                     builtin=False),

    # Alert roles
    'ALERT_LIST_READ': Role(),

    'CLOUD_SYNC_READ': Role(),
    'CLOUD_SYNC_WRITE': Role(includes=['CLOUD_SYNC_READ']),

    'SERVICE_READ': Role(),
    'SERVICE_WRITE': Role(),

    # Network roles
    'NETWORK_GENERAL_READ': Role(),
    'NETWORK_INTERFACE_READ': Role(),
    'NETWORK_INTERFACE_WRITE': Role(includes=['NETWORK_INTERFACE_READ']),

    # iSCSI roles
    'SHARING_ISCSI_AUTH_READ': Role(),
    'SHARING_ISCSI_AUTH_WRITE': Role(includes=['SHARING_ISCSI_AUTH_READ']),
    'SHARING_ISCSI_EXTENT_READ': Role(),
    'SHARING_ISCSI_EXTENT_WRITE': Role(includes=['SHARING_ISCSI_EXTENT_READ']),
    'SHARING_ISCSI_GLOBAL_READ': Role(),
    'SHARING_ISCSI_GLOBAL_WRITE': Role(includes=['SHARING_ISCSI_GLOBAL_READ']),
    'SHARING_ISCSI_HOST_READ': Role(),
    'SHARING_ISCSI_HOST_WRITE': Role(includes=['SHARING_ISCSI_HOST_READ']),
    'SHARING_ISCSI_INITIATOR_READ': Role(),
    'SHARING_ISCSI_INITIATOR_WRITE': Role(includes=['SHARING_ISCSI_INITIATOR_READ']),
    'SHARING_ISCSI_PORTAL_READ': Role(),
    'SHARING_ISCSI_PORTAL_WRITE': Role(includes=['SHARING_ISCSI_PORTAL_READ']),
    'SHARING_ISCSI_TARGET_READ': Role(),
    'SHARING_ISCSI_TARGET_WRITE': Role(includes=['SHARING_ISCSI_TARGET_READ']),
    'SHARING_ISCSI_TARGETEXTENT_READ': Role(),
    'SHARING_ISCSI_TARGETEXTENT_WRITE': Role(includes=['SHARING_ISCSI_TARGETEXTENT_READ']),
    'SHARING_ISCSI_READ': Role(includes=['SHARING_ISCSI_AUTH_READ',
                                         'SHARING_ISCSI_EXTENT_READ',
                                         'SHARING_ISCSI_GLOBAL_READ',
                                         'SHARING_ISCSI_HOST_READ',
                                         'SHARING_ISCSI_INITIATOR_READ',
                                         'SHARING_ISCSI_PORTAL_READ',
                                         'SHARING_ISCSI_TARGET_READ',
                                         'SHARING_ISCSI_TARGETEXTENT_READ']),
    'SHARING_ISCSI_WRITE': Role(includes=['SHARING_ISCSI_AUTH_WRITE',
                                          'SHARING_ISCSI_EXTENT_WRITE',
                                          'SHARING_ISCSI_GLOBAL_WRITE',
                                          'SHARING_ISCSI_HOST_WRITE',
                                          'SHARING_ISCSI_INITIATOR_WRITE',
                                          'SHARING_ISCSI_PORTAL_WRITE',
                                          'SHARING_ISCSI_TARGET_WRITE',
                                          'SHARING_ISCSI_TARGETEXTENT_WRITE']),

    'SHARING_NFS_READ': Role(),
    'SHARING_NFS_WRITE': Role(includes=['SHARING_NFS_READ']),
    'SHARING_SMB_READ': Role(),
    'SHARING_SMB_WRITE': Role(includes=['SHARING_SMB_READ']),
    'SHARING_READ': Role(includes=['SHARING_ISCSI_READ',
                                   'SHARING_NFS_READ',
                                   'SHARING_SMB_READ']),
    'SHARING_WRITE': Role(includes=['SHARING_ISCSI_WRITE',
                                    'SHARING_NFS_WRITE',
                                    'SHARING_SMB_WRITE']),

    'KEYCHAIN_CREDENTIAL_READ': Role(),
    'KEYCHAIN_CREDENTIAL_WRITE': Role(includes=['KEYCHAIN_CREDENTIAL_READ']),
    'REPLICATION_TASK_CONFIG_READ': Role(),
    'REPLICATION_TASK_CONFIG_WRITE': Role(includes=['REPLICATION_TASK_CONFIG_READ']),
    'REPLICATION_TASK_READ': Role(),
    'REPLICATION_TASK_WRITE': Role(includes=['REPLICATION_TASK_READ']),
    'REPLICATION_TASK_WRITE_PULL': Role(includes=['REPLICATION_TASK_WRITE']),
    'SNAPSHOT_TASK_READ': Role(),
    'SNAPSHOT_TASK_WRITE': Role(includes=['SNAPSHOT_TASK_READ']),

    'DATASET_READ': Role(),
    'DATASET_WRITE': Role(includes=['DATASET_READ']),
    'DATASET_DELETE': Role(),
    'SNAPSHOT_READ': Role(),
    'SNAPSHOT_WRITE': Role(includes=['SNAPSHOT_READ']),
    'SNAPSHOT_DELETE': Role(),

    'REPLICATION_MANAGER': Role(includes=['KEYCHAIN_CREDENTIAL_WRITE',
                                          'REPLICATION_TASK_CONFIG_WRITE',
                                          'REPLICATION_TASK_WRITE',
                                          'SNAPSHOT_TASK_WRITE',
                                          'SNAPSHOT_WRITE'],
                                builtin=False),

    'SHARING_MANAGER': Role(includes=['DATASET_WRITE',
                                      'SHARING_WRITE',
                                      'FILESYSTEM_ATTRS_WRITE',
                                      'SERVICE_READ'],
                            builtin=False)
}


class RoleManager:
    def __init__(self, roles):
        self.roles = roles
        self.methods = {}
        self.allowlists_for_roles = defaultdict(list)

    def register_method(self, method_name, roles):
        if method_name in self.methods:
            raise ValueError(f"Method {method_name!r} is already registered in this role manager")

        self.methods[method_name] = []
        self.add_roles(method_name, roles)

    def add_roles(self, method_name, roles):
        if method_name not in self.methods:
            raise ValueError(f"Method {method_name!r} is not registered in this role manager")

        for role in roles:
            if role not in self.roles:
                raise ValueError(f"Invalid role {role!r}")

        self.methods[method_name] += roles

        for role in roles:
            self.allowlists_for_roles[role].append({"method": "CALL", "resource": method_name})

    def roles_for_role(self, role):
        if role not in self.roles:
            return set()

        return set.union({role}, *[self.roles_for_role(included_role) for included_role in self.roles[role].includes])

    def allowlist_for_role(self, role):
        if role in self.roles and self.roles[role].full_admin:
            return [{"method": "CALL", "resource": "*"}]

        return sum([
            self.allowlists_for_roles[role]
            for role in self.roles_for_role(role)
        ], [])

    def roles_for_method(self, method_name):
        roles = set(self.methods.get(method_name, []))

        changed = True
        while changed:
            changed = False
            for role_name, role in self.roles.items():
                if role_name not in roles:
                    for child_role_name in role.includes:
                        if child_role_name in roles:
                            roles.add(role_name)
                            changed = True

        return sorted(roles)
