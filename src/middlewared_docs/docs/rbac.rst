Role-Based Access Control
=========================

TrueNAS uses a role-based access control (RBAC) system to restrict which API
methods a session may call.  Roles are grouped into *privileges*, and privileges
are linked to local or directory-service groups.  When a user authenticates, the
TrueNAS resolves that user's group memberships to a set of active roles, which
are then checked against every API call the user makes.

Privilege management is performed via the ``privilege.*`` API namespace
(``privilege.create``, ``privilege.update``, ``privilege.delete``,
``privilege.query``).


Role Concepts
-------------

Individual roles (``builtin=true``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Individual roles are fine-grained roles attached directly to individual API
methods.  Examples: ``DISK_READ``, ``SHARING_SMB_WRITE``, ``ACCOUNT_READ``.
They are provided to allow selective expansion of access beyond what the
predefined group roles cover.  Custom privileges can combine any set of these
roles to grant precisely the access required for a given use case.

Predefined group roles (``builtin=false``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Predefined group roles are the four top-level roles surfaced in the UI and API
for privilege assignment:

* ``FULL_ADMIN``
* ``READONLY_ADMIN``
* ``SHARING_ADMIN``
* ``REPLICATION_ADMIN``

``READONLY_ADMIN`` is the minimum role required for UI access.  A privilege
that grants only individual roles — without including at least
``READONLY_ADMIN`` — will not be sufficient to log in to the web interface.

Use ``privilege.roles`` (filter ``builtin=false``) to retrieve the current list
of predefined group roles at runtime.

Role inclusion
~~~~~~~~~~~~~~

Roles can declare that they *include* other roles.  Inclusion is expanded
transitively, so a user assigned ``SHARING_ADMIN`` automatically gains all of
the individual roles that ``READONLY_ADMIN`` expands into, plus the additional
write roles specific to sharing.

As a general convention, write roles include their corresponding read role.
For example, ``ACCOUNT_WRITE`` includes ``ACCOUNT_READ``, so granting write
access to a subsystem always implies read access to that same subsystem.

Roles are additive and cannot be scoped down.  There is no way to grant a
role while simultaneously excluding a subset of what it includes — for
example, it is not possible to assign ``FULL_ADMIN`` while blocking
``ACCOUNT_WRITE``.  If finer-grained control is required, build a custom
privilege from individual roles rather than starting from a broad predefined
group role.


Predefined Group Roles
----------------------

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * - Role
     - Description
     - Notable included roles
   * - ``FULL_ADMIN``
     - Unrestricted access to all API methods
     - All roles
   * - ``READONLY_ADMIN``
     - Read-only access across all subsystems
     - All ``*_READ`` individual roles
   * - ``SHARING_ADMIN``
     - Manage datasets and all file-sharing protocols
     - ``READONLY_ADMIN`` + ``DATASET_WRITE`` + ``SHARING_WRITE`` +
       ``FILESYSTEM_ATTRS_WRITE`` + ``SERVICE_READ``
   * - ``REPLICATION_ADMIN``
     - Manage replication, snapshots, and keychain credentials
     - ``KEYCHAIN_CREDENTIAL_WRITE`` + ``REPLICATION_TASK_CONFIG_WRITE`` +
       ``REPLICATION_TASK_WRITE`` + ``SNAPSHOT_TASK_WRITE`` + ``SNAPSHOT_WRITE``

FULL_ADMIN
~~~~~~~~~~

``FULL_ADMIN`` grants unrestricted access to every API method.  It cannot be
scoped down — a session holding this role may call any method regardless of
what other roles are present or absent.

The local ``root`` and ``truenas_admin`` accounts implicitly hold this privilege.

Under GPOS STIG mode, any method not covered by a role becomes unreachable
for *all* users.

READONLY_ADMIN
~~~~~~~~~~~~~~

``READONLY_ADMIN`` expands into every ``*_READ`` individual role defined in the
system.  A session with this role can call any ``*.query`` or
``*.get_instance`` endpoint and any other read-only method, but cannot create,
update, or delete any resource or change any configuration.

This role corresponds to the built-in ``READONLY_ADMINISTRATOR`` privilege.

GPOS STIG has no effect on this role — all ``*_READ`` individual roles are
GPOS-available.

SHARING_ADMIN
~~~~~~~~~~~~~

``SHARING_ADMIN`` is a superset of ``READONLY_ADMIN`` with additional write
access scoped to storage and sharing:

* Create, update, and delete ZFS datasets
* Manage all file-sharing protocols: SMB, NFS, iSCSI, NVMe-oF, FTP, WebShare
* Modify filesystem ACLs and other filesystem attributes
* Read service status (but not change service settings)

A session with ``SHARING_ADMIN`` *cannot* manage user accounts, system-level
settings, network interfaces, storage pools, replication tasks, virtual
machines, or applications.

This role corresponds to the built-in ``SHARING_ADMINISTRATOR`` privilege.

GPOS STIG has no effect on this role — all included roles are GPOS-available.

REPLICATION_ADMIN
~~~~~~~~~~~~~~~~~

``REPLICATION_ADMIN`` provides write access to the replication subsystem:

* Replication tasks (push and pull)
* Periodic snapshot tasks
* ZFS snapshots
* Keychain credentials (SSH keypairs and cloud credentials used by replication)

A session with ``REPLICATION_ADMIN`` *cannot* manage datasets or pools
directly, configure sharing protocols, manage user accounts, or change system
settings.

There is no built-in local group for ``REPLICATION_ADMIN``; it must be
assigned through a custom privilege entry.

GPOS STIG has no effect on this role — all included roles are GPOS-available.


Individual Roles Reference
--------------------------

The table below lists all individual roles available for use in custom
privileges.  Roles marked *unavailable under STIG* cannot be granted to any
session when ``system.security`` has ``enable_gpos_stig=true``.

.. list-table::
   :header-rows: 1
   :widths: 25 45 30

   * - Subsystem
     - Roles
     - Notes
   * - Local Accounts
     - ``ACCOUNT_READ``, ``ACCOUNT_WRITE``
     -
   * - API Keys
     - ``API_KEY_READ``, ``API_KEY_WRITE``
     - ``API_KEY_WRITE`` unavailable under STIG
   * - Auth Sessions
     - ``AUTH_SESSIONS_READ``, ``AUTH_SESSIONS_WRITE``
     -
   * - Boot Environments
     - ``BOOT_ENV_READ``, ``BOOT_ENV_WRITE``
     -
   * - Certificates
     - ``CERTIFICATE_READ``, ``CERTIFICATE_WRITE``
     -
   * - Cloud Backup
     - ``CLOUD_BACKUP_READ``, ``CLOUD_BACKUP_WRITE``
     -
   * - Cloud Sync
     - ``CLOUD_SYNC_READ``, ``CLOUD_SYNC_WRITE``
     -
   * - Containers / LXC
     - ``CONTAINER_READ``, ``CONTAINER_WRITE``,
       ``CONTAINER_DEVICE_READ``, ``CONTAINER_DEVICE_WRITE``,
       ``CONTAINER_IMAGE_READ``, ``CONTAINER_IMAGE_WRITE``,
       ``LXC_CONFIG_READ``, ``LXC_CONFIG_WRITE``
     - All ``*_WRITE`` roles unavailable under STIG
   * - Dataset
     - ``DATASET_READ``, ``DATASET_WRITE``, ``DATASET_DELETE``
     -
   * - Directory Services
     - ``DIRECTORY_SERVICE_READ``, ``DIRECTORY_SERVICE_WRITE``
     -
   * - Disk
     - ``DISK_READ``, ``DISK_WRITE``
     -
   * - Apps / Docker
     - ``APPS_READ``, ``APPS_WRITE``,
       ``CATALOG_READ``, ``CATALOG_WRITE``,
       ``DOCKER_READ``, ``DOCKER_WRITE``
     - All ``*_WRITE`` roles unavailable under STIG
   * - Enclosure / JBOF
     - ``ENCLOSURE_READ``, ``ENCLOSURE_WRITE``,
       ``JBOF_READ``, ``JBOF_WRITE``
     -
   * - Failover
     - ``FAILOVER_READ``, ``FAILOVER_WRITE``
     -
   * - Filesystem
     - ``FILESYSTEM_ATTRS_READ``, ``FILESYSTEM_ATTRS_WRITE``,
       ``FILESYSTEM_DATA_READ``, ``FILESYSTEM_DATA_WRITE``,
       ``FILESYSTEM_FULL_CONTROL``
     -
   * - IPMI
     - ``IPMI_READ``, ``IPMI_WRITE``
     -
   * - Keychain Credentials
     - ``KEYCHAIN_CREDENTIAL_READ``, ``KEYCHAIN_CREDENTIAL_WRITE``
     -
   * - KMIP
     - ``KMIP_READ``, ``KMIP_WRITE``
     -
   * - Mail
     - ``MAIL_WRITE``
     -
   * - Network
     - ``NETWORK_GENERAL_READ``, ``NETWORK_GENERAL_WRITE``,
       ``NETWORK_INTERFACE_READ``, ``NETWORK_INTERFACE_WRITE``
     -
   * - Pool
     - ``POOL_READ``, ``POOL_WRITE``,
       ``POOL_SCRUB_READ``, ``POOL_SCRUB_WRITE``
     -
   * - Privilege
     - ``PRIVILEGE_READ``, ``PRIVILEGE_WRITE``
     -
   * - Replication
     - ``REPLICATION_TASK_CONFIG_READ``, ``REPLICATION_TASK_CONFIG_WRITE``,
       ``REPLICATION_TASK_READ``, ``REPLICATION_TASK_WRITE``,
       ``REPLICATION_TASK_WRITE_PULL``
     -
   * - Reporting
     - ``REPORTING_READ``, ``REPORTING_WRITE``
     -
   * - Services
     - ``SERVICE_READ``, ``SERVICE_WRITE``
     -
   * - Sharing — FTP
     - ``SHARING_FTP_READ``, ``SHARING_FTP_WRITE``
     -
   * - Sharing — iSCSI
     - ``SHARING_ISCSI_READ``, ``SHARING_ISCSI_WRITE``,
       ``SHARING_ISCSI_AUTH_READ``, ``SHARING_ISCSI_AUTH_WRITE``,
       ``SHARING_ISCSI_EXTENT_READ``, ``SHARING_ISCSI_EXTENT_WRITE``,
       ``SHARING_ISCSI_GLOBAL_READ``, ``SHARING_ISCSI_GLOBAL_WRITE``,
       ``SHARING_ISCSI_HOST_READ``, ``SHARING_ISCSI_HOST_WRITE``,
       ``SHARING_ISCSI_INITIATOR_READ``, ``SHARING_ISCSI_INITIATOR_WRITE``,
       ``SHARING_ISCSI_PORTAL_READ``, ``SHARING_ISCSI_PORTAL_WRITE``,
       ``SHARING_ISCSI_TARGET_READ``, ``SHARING_ISCSI_TARGET_WRITE``,
       ``SHARING_ISCSI_TARGETEXTENT_READ``, ``SHARING_ISCSI_TARGETEXTENT_WRITE``
     -
   * - Sharing — NFS
     - ``SHARING_NFS_READ``, ``SHARING_NFS_WRITE``
     -
   * - Sharing — NVMe-oF
     - ``SHARING_NVME_TARGET_READ``, ``SHARING_NVME_TARGET_WRITE``
     -
   * - Sharing — SMB
     - ``SHARING_SMB_READ``, ``SHARING_SMB_WRITE``
     -
   * - Sharing — WebShare
     - ``SHARING_WEBSHARE_READ``, ``SHARING_WEBSHARE_WRITE``
     -
   * - Sharing (aggregate)
     - ``SHARING_READ``, ``SHARING_WRITE``
     - Each expands into all ``SHARING_*_READ`` / ``SHARING_*_WRITE`` roles
   * - Snapshots
     - ``SNAPSHOT_READ``, ``SNAPSHOT_WRITE``, ``SNAPSHOT_DELETE``,
       ``SNAPSHOT_TASK_READ``, ``SNAPSHOT_TASK_WRITE``
     -
   * - SSH
     - ``SSH_READ``, ``SSH_WRITE``
     -
   * - Support
     - ``SUPPORT_READ``, ``SUPPORT_WRITE``
     -
   * - System Audit
     - ``SYSTEM_AUDIT_READ``, ``SYSTEM_AUDIT_WRITE``
     -
   * - System Settings
     - ``SYSTEM_ADVANCED_READ``, ``SYSTEM_ADVANCED_WRITE``,
       ``SYSTEM_CRON_READ``, ``SYSTEM_CRON_WRITE``,
       ``SYSTEM_GENERAL_READ``, ``SYSTEM_GENERAL_WRITE``,
       ``SYSTEM_PRODUCT_READ``, ``SYSTEM_PRODUCT_WRITE``,
       ``SYSTEM_SECURITY_READ``, ``SYSTEM_SECURITY_WRITE``,
       ``SYSTEM_TUNABLE_READ``, ``SYSTEM_TUNABLE_WRITE``,
       ``SYSTEM_UPDATE_READ``, ``SYSTEM_UPDATE_WRITE``
     -
   * - TrueCommand
     - ``TRUECOMMAND_READ``, ``TRUECOMMAND_WRITE``
     - ``TRUECOMMAND_WRITE`` unavailable under STIG
   * - TrueNAS Connect
     - ``TRUENAS_CONNECT_READ``, ``TRUENAS_CONNECT_WRITE``
     - ``TRUENAS_CONNECT_WRITE`` unavailable under STIG
   * - Virtual Machines
     - ``VM_READ``, ``VM_WRITE``,
       ``VM_DEVICE_READ``, ``VM_DEVICE_WRITE``
     - All ``*_WRITE`` roles unavailable under STIG
   * - ZFS Resources (filesystems, zvols)
     - ``ZFS_RESOURCE_READ``, ``ZFS_RESOURCE_WRITE``, ``ZFS_RESOURCE_DELETE``
     -


GPOS STIG Mode
--------------

When ``system.security`` has ``enable_gpos_stig=true``, the GPOS STIG profile
is active.  Under this profile certain write roles become **unavailable**,
meaning sessions that hold only those roles lose write access to the
corresponding subsystems.  The matching read roles remain available in all
cases.

The ``stig`` field in ``privilege.roles`` output indicates which STIG profiles
permit a role.  A value of ``null`` means the role is not permitted under any
STIG profile; a non-null value identifies the profile(s) that allow it.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Unavailable role(s)
     - Affected area
   * - ``API_KEY_WRITE``
     - API key management (``API_KEY_READ`` still permitted)
   * - ``VM_WRITE``, ``VM_DEVICE_WRITE``
     - Virtual machines
   * - ``CONTAINER_WRITE``, ``CONTAINER_DEVICE_WRITE``,
       ``CONTAINER_IMAGE_WRITE``, ``LXC_CONFIG_WRITE``
     - Containers and LXC
   * - ``DOCKER_WRITE``
     - Docker back-end
   * - ``APPS_WRITE``, ``CATALOG_WRITE``
     - Applications catalog
   * - ``TRUECOMMAND_WRITE``
     - TrueCommand integration
   * - ``TRUENAS_CONNECT_WRITE``
     - TrueNAS Connect cloud service

For ``FULL_ADMIN`` specifically, see the note in the `FULL_ADMIN`_ section above.


Managing Privileges
-------------------

Use the following API methods to manage privileges:

* ``privilege.create`` — create a new privilege and link it to one or more
  local or directory-service groups
* ``privilege.update`` — modify an existing privilege (change roles or group
  membership)
* ``privilege.delete`` — remove a custom privilege
* ``privilege.query`` — list all privileges, including the three built-in ones
* ``privilege.roles`` — list all roles; pass ``[["builtin", "=", false]]`` as
  the filter argument to return only the predefined group roles
* ``auth.me`` — returns the currently authenticated session, including the full
  list of roles that have been granted to it

.. note::

   **Enterprise license requirement.** Linking a privilege to a
   directory-service group (Active Directory or LDAP group) requires an
   Enterprise license.  On Community Edition, privileges can only be
   assigned to local Unix groups.

.. note::

   **Secret field redaction.** API responses automatically redact fields
   marked ``secret`` in the schema (for example, credentials and passwords)
   for any session that does not hold the ``FULL_ADMIN`` role.  Such fields
   are replaced with a redacted placeholder rather than being omitted, so the
   response structure remains consistent.
