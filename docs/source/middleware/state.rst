Middleware State Directories
############################

.. contents:: Table of Contents
    :depth: 4

The middlewared process stores state in several directories on the local filesystem. There
are many situations in which the developer may opt to store state information outside of the
configuration database. In this case the onus is on the developer to choose an appropriate
location for this state based on persistence requirements. The following is a brief introduction
to how volatile and persistent state is stored. The most up-to-date definitions for storage
locations are in the truenas/middleware repository, and truenas/scale-build (for datasets
created during installation and upgrade).


Volatile state
**************

Volatile middleware state is stored in the middleware run directory `/var/run/middleware`.
The expected permissions on the volatile state directory are 0o755. This is typically where
sentinel files should be placed. This is defined by `MIDDLEWARE_RUN_DIR` in `middlewared/utils`.


Persistent state
****************

There are several directories that are used to store persistent state related to the middlewared
process and TrueNAS servers.

`/conf` -- this ZFS dataset is readonly and contains configuration that is not expected to change at runtime.
An example of this would be our audit rulesets or some metadata about the boot pool when it is installed.
This dataset is not cloned during the upgrade process and information is not preserved as part of configuration
backups.

`/data` -- this ZFS dataset contains the TrueNAS configuration file `freenas-v1.db` and various install-specific
configuration files that must persist across TrueNAS upgrades. Items that need to be included in the configuration
tarball should generally be placed here. Permissions on this directory must be 0o755, but many files here should
be set to 0o700. All files and directories should be owned by root:root.

`/data/subsystems` -- this directory contains application-specific configuration that must persist between
installs that is not suitable for datastore insertion. The convention is to create a new directory with the name of
the middleware plugin that needs persistent state. Configuration information stored in these directories must be
included in the TrueNAS configuration backup and restored on configuration upload.

`/var/lib/truenas-middleware` -- this directory contains persistent middleware state that is applicable to the
current boot environment only. It is a safe place to store data that we want to persist across reboots, but not
across upgrades. This is defined by the `MIDDLEWARE_BOOT_ENV_STATE_DIR` in `middlewared/utils`. The permissions
on this directory should be 0o755 and it should be owned by root:root.

`/root` -- this dataset contains the middleware directory services cache. The permissions on this directory
should be 0o700 and it should be owned by root:root.

`/var/db/system` -- this is the mountpoint for the system dataset. The storage pool for the system dataset is
runtime configurable and in single node systems may be located on the boot pool. If the server is an HA appliance
the system dataset will always be on a data pool. Examples of when to place state in the system dataset are
if the state must remain consistent for the active storage controller in an HA pair (for example nfs4 state file)
or if we want the state's storage pool to be user-configurable. The system dataset mountpoint has expected
permissions of 0o755 and ownership of root:root.

`/audit` -- this is the dataset containing our auditing databases. It is cloned during the upgrade process and
so persists across upgrades. The auditing databases are not expected to be preserved during backup and restore
operations and are unique to the individual truenas install. Expected permissions are 0o700 and owned by root:root.
Procedure for adding new audit databases are documented separately.
