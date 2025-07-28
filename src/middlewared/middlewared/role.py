from collections import defaultdict
from dataclasses import dataclass, field
from middlewared.utils.privilege_constants import ALLOW_LIST_FULL_ADMIN
from middlewared.utils.security import STIGType
import typing


@dataclass()
class Role:
    """
    An authenticated user role.

    :ivar includes: a list of other roles that this role includes. When user is granted this role, they will also
        receive permissions granted by all the included roles.
    :ivar full_admin: if `True` then this role will allow calling all methods.
    """
    includes: typing.List[str] = field(default_factory=list)
    full_admin: bool = False
    builtin: bool = True
    stig: STIGType = STIGType.GPOS  # By default roles are available under GPOS STIG


ROLES = {
    'ACCOUNT_READ': Role(),
    'ACCOUNT_WRITE': Role(includes=['ACCOUNT_READ']),

    'API_KEY_READ': Role(),
    'API_KEY_WRITE': Role(includes=['API_KEY_READ'], stig=None),

    'AUTH_SESSIONS_READ': Role(),
    'AUTH_SESSIONS_WRITE': Role(includes=['AUTH_SESSIONS_READ']),

    'BOOT_ENV_READ': Role(),
    'BOOT_ENV_WRITE': Role(includes=['BOOT_ENV_READ']),

    'DIRECTORY_SERVICE_READ': Role(),
    'DIRECTORY_SERVICE_WRITE': Role(includes=['DIRECTORY_SERVICE_READ']),

    'DISK_READ': Role(),
    'DISK_WRITE': Role(includes=['DISK_READ']),

    'FAILOVER_READ': Role(),
    'FAILOVER_WRITE': Role(includes=['FAILOVER_READ']),

    'FILESYSTEM_ATTRS_READ': Role(),
    'FILESYSTEM_ATTRS_WRITE': Role(includes=['FILESYSTEM_ATTRS_READ']),
    'FILESYSTEM_DATA_READ': Role(),
    'FILESYSTEM_DATA_WRITE': Role(includes=['FILESYSTEM_DATA_READ']),
    'FILESYSTEM_FULL_CONTROL': Role(includes=['FILESYSTEM_ATTRS_WRITE',
                                              'FILESYSTEM_DATA_WRITE']),

    'IPMI_READ': Role(),
    'IPMI_WRITE': Role(includes=['IPMI_READ']),

    'KMIP_READ': Role(),
    'KMIP_WRITE': Role(includes=['KMIP_READ']),

    'MAIL_WRITE': Role(),

    # Interact with privilege framework
    'PRIVILEGE_READ': Role(),
    'PRIVILEGE_WRITE': Role(includes=['PRIVILEGE_WRITE']),

    'REPORTING_READ': Role(),
    'REPORTING_WRITE': Role(includes=['REPORTING_READ']),

    'SUPPORT_READ': Role(),
    'SUPPORT_WRITE': Role(includes=['SUPPORT_READ']),

    'SSH_READ': Role(),
    'SSH_WRITE': Role(includes=['SSH_READ']),

    'SYSTEM_AUDIT_READ': Role(),
    'SYSTEM_AUDIT_WRITE': Role(),

    'FULL_ADMIN': Role(full_admin=True, builtin=False),

    # Limited ability to read / clear individual alerts
    'ALERT_LIST_READ': Role(),
    'ALERT_LIST_WRITE': Role(includes=['ALERT_LIST_READ']),

    # Global alert privileges to configure alert plugin
    'ALERT_READ': Role(includes=['ALERT_LIST_READ']),
    'ALERT_WRITE': Role(includes=['ALERT_LIST_WRITE', 'ALERT_READ']),

    'CLOUD_BACKUP_READ': Role(),
    'CLOUD_BACKUP_WRITE': Role(includes=['CLOUD_BACKUP_READ']),

    'CLOUD_SYNC_READ': Role(),
    'CLOUD_SYNC_WRITE': Role(includes=['CLOUD_SYNC_READ']),

    'SERVICE_READ': Role(),
    'SERVICE_WRITE': Role(),

    # for webui.enclosure.** namespace
    'ENCLOSURE_READ': Role(),
    'ENCLOSURE_WRITE': Role(includes=['ENCLOSURE_READ']),

    # Network roles
    'NETWORK_GENERAL_READ': Role(),
    'NETWORK_GENERAL_WRITE': Role(includes=['NETWORK_GENERAL_READ']),

    'NETWORK_INTERFACE_READ': Role(),
    'NETWORK_INTERFACE_WRITE': Role(includes=['NETWORK_INTERFACE_READ']),

    # VM roles
    'VM_READ': Role(),
    'VM_WRITE': Role(includes=['VM_READ'], stig=None),
    'VM_DEVICE_READ': Role(includes=['VM_READ']),
    'VM_DEVICE_WRITE': Role(includes=['VM_WRITE', 'VM_DEVICE_READ'], stig=None),

    # JBOF roles
    'JBOF_READ': Role(),
    'JBOF_WRITE': Role(includes=['JBOF_READ']),

    # Truecommand roles
    'TRUECOMMAND_READ': Role(),
    'TRUECOMMAND_WRITE': Role(includes=['TRUECOMMAND_READ'], stig=None),

    # Truenas connect roles
    'TRUENAS_CONNECT_READ': Role(),
    'TRUENAS_CONNECT_WRITE': Role(includes=['TRUENAS_CONNECT_READ'], stig=None),

    # Crypto roles
    'CERTIFICATE_READ': Role(),
    'CERTIFICATE_WRITE': Role(includes=['CERTIFICATE_READ']),

    # Apps roles
    'CATALOG_READ': Role(),
    'CATALOG_WRITE': Role(includes=['CATALOG_READ'], stig=None),
    'DOCKER_READ': Role(includes=[]),
    'DOCKER_WRITE': Role(includes=['DOCKER_READ'], stig=None),
    'APPS_READ': Role(includes=['CATALOG_READ']),
    'APPS_WRITE': Role(includes=['CATALOG_WRITE', 'APPS_READ'], stig=None),

    # FTP roles
    'SHARING_FTP_READ': Role(),
    'SHARING_FTP_WRITE': Role(includes=['SHARING_FTP_READ']),

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
    'SHARING_NVME_TARGET_READ': Role(),
    'SHARING_NVME_TARGET_WRITE': Role(includes=['SHARING_NVME_TARGET_READ']),
    'SHARING_SMB_READ': Role(),
    'SHARING_SMB_WRITE': Role(includes=['SHARING_SMB_READ']),
    'SHARING_READ': Role(includes=['SHARING_ISCSI_READ',
                                   'SHARING_NFS_READ',
                                   'SHARING_NVME_TARGET_READ',
                                   'SHARING_SMB_READ',
                                   'SHARING_FTP_READ']),
    'SHARING_WRITE': Role(includes=['SHARING_ISCSI_WRITE',
                                    'SHARING_NFS_WRITE',
                                    'SHARING_NVME_TARGET_WRITE',
                                    'SHARING_SMB_WRITE',
                                    'SHARING_FTP_WRITE']),

    'KEYCHAIN_CREDENTIAL_READ': Role(),
    'KEYCHAIN_CREDENTIAL_WRITE': Role(includes=['KEYCHAIN_CREDENTIAL_READ']),
    'REPLICATION_TASK_CONFIG_READ': Role(),
    'REPLICATION_TASK_CONFIG_WRITE': Role(includes=['REPLICATION_TASK_CONFIG_READ']),
    'REPLICATION_TASK_READ': Role(),
    'REPLICATION_TASK_WRITE': Role(includes=['REPLICATION_TASK_READ']),
    'REPLICATION_TASK_WRITE_PULL': Role(includes=['REPLICATION_TASK_WRITE']),
    'SNAPSHOT_TASK_READ': Role(),
    'SNAPSHOT_TASK_WRITE': Role(includes=['SNAPSHOT_TASK_READ']),

    'POOL_SCRUB_READ': Role(),
    'POOL_SCRUB_WRITE': Role(includes=['POOL_SCRUB_READ']),
    'POOL_READ': Role(includes=['POOL_SCRUB_READ']),
    'POOL_WRITE': Role(includes=['POOL_READ', 'POOL_SCRUB_WRITE']),
    'DATASET_READ': Role(),
    'DATASET_WRITE': Role(includes=['DATASET_READ']),
    'DATASET_DELETE': Role(),
    'SNAPSHOT_READ': Role(),
    'SNAPSHOT_WRITE': Role(includes=['SNAPSHOT_READ']),
    'SNAPSHOT_DELETE': Role(),

    'REPLICATION_ADMIN': Role(includes=['KEYCHAIN_CREDENTIAL_WRITE',
                                        'REPLICATION_TASK_CONFIG_WRITE',
                                        'REPLICATION_TASK_WRITE',
                                        'SNAPSHOT_TASK_WRITE',
                                        'SNAPSHOT_WRITE'],
                              builtin=False),

    'SHARING_ADMIN': Role(includes=['READONLY_ADMIN',
                                    'DATASET_WRITE',
                                    'SHARING_WRITE',
                                    'FILESYSTEM_ATTRS_WRITE',
                                    'SERVICE_READ'],
                          builtin=False),

    # System settings
    'SYSTEM_GENERAL_READ': Role(),
    'SYSTEM_GENERAL_WRITE': Role(includes=['SYSTEM_GENERAL_READ']),

    'SYSTEM_PRODUCT_READ': Role(),
    'SYSTEM_PRODUCT_WRITE': Role(includes=['SYSTEM_PRODUCT_WRITE']),

    'SYSTEM_ADVANCED_READ': Role(),
    'SYSTEM_ADVANCED_WRITE': Role(includes=['SYSTEM_ADVANCED_READ']),

    'SYSTEM_SECURITY_READ': Role(),
    'SYSTEM_SECURITY_WRITE': Role(includes=['SYSTEM_SECURITY_READ']),

    'SYSTEM_TUNABLE_READ': Role(),
    'SYSTEM_TUNABLE_WRITE': Role(includes=['SYSTEM_TUNABLE_READ']),

    'SYSTEM_CRON_READ': Role(),
    'SYSTEM_CRON_WRITE': Role(includes=['SYSTEM_CRON_READ']),

    'SYSTEM_UPDATE_READ': Role(),
    'SYSTEM_UPDATE_WRITE': Role(includes=['SYSTEM_UPDATE_READ']),

    # Virtualization
    'VIRT_GLOBAL_READ': Role(),
    'VIRT_GLOBAL_WRITE': Role(includes=['VIRT_GLOBAL_READ'], stig=None),
    'VIRT_INSTANCE_READ': Role(),
    'VIRT_INSTANCE_WRITE': Role(includes=['VIRT_INSTANCE_READ'], stig=None),
    'VIRT_INSTANCE_DELETE': Role(stig=None),
    'VIRT_IMAGE_READ': Role(),
    'VIRT_IMAGE_WRITE': Role(includes=['VIRT_IMAGE_READ'], stig=None),

    # ZFS Resources (query, create/update/delete)
    'ZFS_RESOURCE_READ': Role(),
}
ROLES['READONLY_ADMIN'] = Role(includes=[role for role in ROLES if role.endswith('_READ')], builtin=False)

READ_RESOURCE_BLACKLIST = (
    '.create', '.do_create',
    '.update', '.do_update',
    '.delete', '.do_delete',
)


class ResourceManager:
    def __init__(self, resource_title: str, resource_method: str, roles: typing.Dict[str, Role]):
        self.resource_title: str = resource_title
        self.resource_method: str = resource_method
        self.roles: typing.Dict[str, Role] = roles
        self.resources: typing.Dict[str, list[str]] = {}
        self.allowlists_for_roles: typing.Dict[str, list[dict[str, str]]] = defaultdict(list)

    def register_resource(self, resource_name: str, roles: typing.Iterable[str], exist_ok: bool):
        if resource_name in self.resources:
            if not exist_ok:
                raise ValueError(f"{self.resource_title} {resource_name!r} is already registered in this role manager")
        else:
            self.resources[resource_name] = []

        self.add_roles_to_resource(resource_name, roles)

    def add_roles_to_resource(self, resource_name: str, roles: typing.Iterable[str]):
        if resource_name not in self.resources:
            raise ValueError(f"{self.resource_title} {resource_name!r} is not registered in this role manager")

        for role in roles:
            if role not in self.roles:
                raise ValueError(f"Invalid role {role!r}")

            if role.endswith("_READ") and resource_name.endswith(READ_RESOURCE_BLACKLIST):
                raise ValueError(f'{resource_name}: resource may not be granted to {role}')

        self.resources[resource_name] += roles

        for role in roles:
            self.allowlists_for_roles[role].append({"method": self.resource_method, "resource": resource_name})

    def roles_for_resource(self, resource_name: str) -> typing.List[str]:
        roles = self.atomic_roles_for_resource(resource_name)

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

    def atomic_roles_for_resource(self, resource_name: str) -> set[str]:
        return set(self.resources.get(resource_name, []))


class RoleManager:
    def __init__(self, roles: typing.Dict[str, Role]):
        self.roles = roles
        self.methods = ResourceManager("Method", "CALL", self.roles)
        self.events = ResourceManager("Event", "SUBSCRIBE", self.roles)

    def register_method(self, method_name: str, roles: typing.Iterable[str], *, exist_ok: bool = False):
        self.methods.register_resource(method_name, roles, exist_ok)

    def add_roles_to_method(self, method_name: str, roles: typing.Iterable[str]):
        self.methods.add_roles_to_resource(method_name, roles)

    def register_event(self, event_name: str, roles: typing.Iterable[str], *, exist_ok: bool = False):
        self.events.register_resource(event_name, roles, exist_ok)

    def role_stig_check(self, role_name: str, enabled_stig: STIGType) -> bool:
        """
        Determine whether role is available in current STIG configuration
        enabled_stig is an intflag enum because in future we may add more
        STIGs that can be enabled to unlock portions of product that are
        currently unavailable under GPOS STIG.
        """
        if not enabled_stig:
            # No STIG set that is limiting available roles
            return True

        role = self.roles[role_name]
        if role.stig is None:
            # No STIG settings exist that grant this role
            return False

        return bool(role.stig & enabled_stig)

    def roles_for_role(self, role: str, enabled_stig: STIGType | None) -> typing.Set[str]:
        if role not in self.roles:
            return set()

        if self.roles[role].full_admin:
            # Convert FULL_ADMIN to all stig-allowed roles.
            return set([role_name for role_name, role in self.roles.items() if self.role_stig_check(role_name, enabled_stig)])

        return set.union({role}, *[
            self.roles_for_role(included_role, enabled_stig)
            for included_role in self.roles[role].includes if self.role_stig_check(included_role, enabled_stig)
        ])

    def allowlist_for_role(self, role: str, enabled_stig: STIGType) -> typing.List[dict[str, str]]:
        if role in self.roles and self.roles[role].full_admin:
            if enabled_stig:
                return sum([
                    self.methods.allowlists_for_roles[role] + self.events.allowlists_for_roles[role]
                    for role in self.roles_for_role(role, enabled_stig)
                ], [])

            # Only non-stig FULL_ADMIN privilege can access REST endpoints
            return [ALLOW_LIST_FULL_ADMIN.copy()]

        return sum([
            self.methods.allowlists_for_roles[role] + self.events.allowlists_for_roles[role]
            for role in self.roles_for_role(role, enabled_stig)
        ], [])

    def roles_for_method(self, method_name: str) -> typing.List[str]:
        return self.methods.roles_for_resource(method_name)

    def atomic_roles_for_method(self, method_name: str) -> set[str]:
        return self.methods.atomic_roles_for_resource(method_name)

    def roles_for_event(self, event_name: str) -> typing.List[str]:
        return self.events.roles_for_resource(event_name)

    def atomic_roles_for_event(self, method_name: str) -> set[str]:
        return self.events.atomic_roles_for_resource(method_name)
