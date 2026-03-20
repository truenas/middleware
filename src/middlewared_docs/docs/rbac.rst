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

Low-level roles (``builtin=true``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Low-level roles are fine-grained roles attached directly to individual API
methods.  Examples: ``DISK_READ``, ``SHARING_SMB_WRITE``, ``ACCOUNT_READ``.
They are provided to allow selective expansion of access beyond what the
high-level roles cover.  Custom privileges can combine any set of these roles
to grant precisely the access required for a given use case.

High-level roles (``builtin=false``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

High-level roles are the four top-level roles surfaced in the UI and API for
privilege assignment:

* ``FULL_ADMIN``
* ``READONLY_ADMIN``
* ``SHARING_ADMIN``
* ``REPLICATION_ADMIN``

``READONLY_ADMIN`` is the minimum role required for UI access.  A privilege
that grants only low-level roles — without including at least ``READONLY_ADMIN``
— will not be sufficient to log in to the web interface.

Use ``privilege.roles`` (filter ``builtin=false``) to retrieve the current list
of high-level roles at runtime.

Role inclusion
~~~~~~~~~~~~~~

Roles can declare that they *include* other roles.  Inclusion is expanded
transitively, so a user assigned ``SHARING_ADMIN`` automatically gains all of
the low-level roles that ``READONLY_ADMIN`` expands into, plus the additional
write roles specific to sharing.

As a general convention, write roles include their corresponding read role.
For example, ``ACCOUNT_WRITE`` includes ``ACCOUNT_READ``, so granting write
access to a subsystem always implies read access to that same subsystem.

Roles are additive and cannot be scoped down.  There is no way to grant a
role while simultaneously excluding a subset of what it includes — for
example, it is not possible to assign ``FULL_ADMIN`` while blocking
``ACCOUNT_WRITE``.  If finer-grained control is required, build a custom
privilege from individual low-level roles rather than starting from a broad
high-level role.


High-Level Roles
----------------

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
     - All ``*_READ`` low-level roles
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

``READONLY_ADMIN`` expands into every ``*_READ`` low-level role defined in the
system.  A session with this role can call any ``*.query`` or
``*.get_instance`` endpoint and any other read-only method, but cannot create,
update, or delete any resource or change any configuration.

This role corresponds to the built-in ``READONLY_ADMINISTRATOR`` privilege.

GPOS STIG has no effect on this role — all ``*_READ`` low-level roles are
GPOS-available.

SHARING_ADMIN
~~~~~~~~~~~~~

``SHARING_ADMIN`` is a superset of ``READONLY_ADMIN`` with additional write
access scoped to storage and sharing:

* Create, update, and delete ZFS datasets
* Manage all file-sharing protocols: SMB, NFS, iSCSI, NVMe-oF, FTP, WebDAV
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
  the filter argument to return only the high-level roles
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
