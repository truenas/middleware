Boot Process
============

.. contents:: Table of Contents
    :depth: 3

TrueNAS is based on Debian, so it's just another modern Linux system with standard systemd boot process: a giant tangled
graph of hundreds of units executed in parallel. This document describes a few key moments a developer should know
when making changes to this complicated setup.

Early units
-----------

TrueNAS has a number of systemd units that should be executed as early in the boot process as possible. All of these
units include

.. code-block:: ini

    [Unit]
    DefaultDependencies=no

to avoid depending on anything and be executed first.

Here are the most important of these units in their execution order.

Group 0: Start middleware daemon
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Middleware daemon is a key component to TrueNAS system management so it (and its prerequisites) should be started
first.

* `ix-conf.service`: Extracts `Extract /conf/base` over root filesystem, overwriting all the filesystem modifications
  that could be made during previous boots.
* `ix-update.service`: Performs :doc:`database migrations <../database/migrations>` and other update (or config upload)
  tasks.
* `middlewared.service`: Starts middleware daemon making TrueNAS API available for internal use.

Group 1: Pre-configure system services
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

At this step we prepare configuration for all file sharing daemons and other system services to be started. All these
units must be started exactly between `middlewared.service` and the rest of the normal systemd boot process:

.. code-block:: ini

    [Unit]
    DefaultDependencies=no

    After=middlewared.service
    Before=local-fs.target
    Before=network-pre.target

Here are the most important ones:

* `ix-etc.service`: Generates `/etc` configuration files for all services TrueNAS uses.
* `ix-zfs.service`: Imports ZFS storage pools.
* `ix-netif.service`: Configures network (replaces `systemd-networkd`)

Starting system services
------------------------

After all configuration files were written, filesystems were configured and network interfaces were brought up, TrueNAS
yields to systemd to start its common UNIX services: NTP, NFS, SSH, Samba... As most of them can be disabled in TrueNAS
configuration, this raises a question: what determines which services should be started and which should be not?

The perfect solution would be to make `ix-etc` read configuration database and enable/disable corresponding systemd
units. Unfortunately, that won't work (at least, currently). systemd calculates its boot graph when `init` process
is first started and there is no known way to make it re-calculate it based on units we enable/disable during the
boot process. As a consequence, all necessary systemd units must be enabled before systemd boot process even starts.

On a normal system we enable/disable systemd units upon user request during runtime. This configuration is preserved
in the root filesystem across reboots and the boot process works as it should. However, when we upgrade a TrueNAS
installation, a new root filesystem is created and all the systemd units are disabled there; after restart, no services
would be running. To fix that, we also maintain a list of enabled/disabled systemd units in `/data/user-services.json`.
That way, the installer will be able to enable/disable systemd units in a newly created filesystem without being aware
how to read the configuration database file and map the list of enabled TrueNAS services to systemd units.
