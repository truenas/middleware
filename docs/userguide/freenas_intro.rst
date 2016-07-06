.. centered:: FreeNAS® is © 2011-2016 iXsystems

.. centered:: FreeNAS® and the FreeNAS® logo are registered trademarks
              of iXsystems.

.. centered:: FreeBSD® is a registered trademark of the FreeBSD
              Foundation

Written by users of the FreeNAS® network-attached storage operating
system.

Version |release|

Copyright © 2011-2016
`iXsystems <https://www.ixsystems.com/>`_

This Guide covers the installation and use of FreeNAS® |release|.

The FreeNAS® Users Guide is a work in progress and relies on the
contributions of many individuals. If you are interested in helping us
to improve the Guide, read the instructions in the `README
<https://github.com/freenas/freenas/blob/master/docs/userguide/README.md>`_.
If you use IRC Freenode, you are welcome to join the #freenas channel
where you will find other FreeNAS® users.

The FreeNAS® Users Guide is freely available for sharing and
redistribution under the terms of the `Creative Commons Attribution
License <https://creativecommons.org/licenses/by/3.0/>`_. This means
that you have permission to copy, distribute, translate, and adapt the
work as long as you attribute iXsystems as the original source of the
Guide.

FreeNAS® and the FreeNAS® logo are registered trademarks of iXsystems.

Active Directory® is a registered trademark or trademark of Microsoft
Corporation in the United States and/or other countries.

Apple, Mac and Mac OS are trademarks of Apple Inc., registered in the
U.S. and other countries.

Chelsio® is a registered trademark of Chelsio Communications.

Cisco® is a registered trademark or trademark of Cisco Systems, Inc.
and/or its affiliates in the United States and certain other
countries.

Django® is a registered trademark of Django Software Foundation.

Facebook® is a registered trademark of Facebook Inc.

FreeBSD and the FreeBSD logo are registered trademarks of the FreeBSD
Foundation.

Fusion-io is a trademark or registered trademark of Fusion-io, Inc.

Intel, the Intel logo, Pentium Inside, and Pentium are trademarks of
Intel Corporation in the U.S. and/or other countries.

LinkedIn® is a registered trademark of LinkedIn Corporation.

Linux® is a registered trademark of Linus Torvalds.

Marvell® is a registered trademark of Marvell or its affiliates.

Oracle is a registered trademark of Oracle Corporation and/or its
affiliates.

Twitter is a trademark of Twitter, Inc. in the United States and other
countries.

UNIX® is a registered trademark of The Open Group.

VirtualBox® is a registered trademark of Oracle.

VMware® is a registered trademark of VMware, Inc.

Wikipedia® is a registered trademark of the Wikimedia Foundation,
Inc., a non-profit organization.

Windows® is a registered trademark of Microsoft Corporation in the
United States and other countries.

**Typographic Conventions**

The FreeNAS® |release| Users Guide uses the following typographic
conventions:

* Names of graphical elements such as buttons, icons, fields, columns,
  and boxes are enclosed within quotes. For example: click the "Import
  CA" button.

* Menu selections are italicized and separated by arrows. For example:
  :menuselection:`System --> Information`.

* Commands that are mentioned within text are highlighted in
  :command:`bold text`. Command examples and command output are
  contained in green code blocks.

* Volume, dataset, and file names are enclosed in a blue box
  :file:`/like/this`.

* Keystrokes are formatted in a blue box. For example: press
  :kbd:`Enter`.

* **bold text:** used to emphasize an important point.

* *italic text:* used to represent device names or text that is input
  into a GUI field.

.. _Introduction:

Introduction
============

FreeNAS® is an embedded open source network-attached storage (NAS)
operating system based on FreeBSD and released under a
`2-clause BSD license <https://opensource.org/licenses/BSD-2-Clause>`_.
A NAS has an operating system optimized for file storage and sharing.

FreeNAS® provides a browser-based, graphical configuration interface.
Its built-in networking protocols provide storage access to multiple
operating systems. A plugin system is provided for extending the
built-in features by installing additional software.

.. _What's New in |release|:

What's New in |version|
-----------------------

* Based on FreeBSD 10.3 which adds `these features
  <https://www.freebsd.org/releases/10.3R/relnotes.html>`_. This
  includes many new hardware drivers and updates to existing drivers.

* Samba has been updated to
  `4.3.4 <https://www.samba.org/samba/history/samba-4.3.4.html>`_.

* USB3 support is now enabled by default.

* The "Remote Graphite Server Hostname" field has been added to
  :menuselection:`System --> Advanced`.

* The "Firmware Update" button has been removed from
  :menuselection:`System --> Advanced`. Updates are now performed
  using :menuselection:`System --> Update`.

* The "Disabled" option has been removed from :menuselection:`Storage
  --> Replication Tasks --> Add Replication --> Encryption Cipher`.

* The "Disable Active Directory user/group cache" checkbox has been
  added to :menuselection:`Directory Service --> Active Directory -->
  Advanced Mode`.

* The "Kerberos keytab" drop-down menu has been renamed to "Kerberos
  Principal" in :menuselection:`Directory Service --> Active Directory
  --> Advanced Mode`.

* The CrucibleWDS plugin has been deprecated and replaced with
  `CloneDeploy <https://sourceforge.net/projects/clonedeploy/>`_.

* :command:`iohyve` has been added for creating, managing, and
  launching `bhyve <https://en.wikipedia.org/wiki/Bhyve>`_ guests from
  the command line. This utility requires an Intel or AMD
  processor that reports the "POPCNT" (POPulation CouNT) processor
  feature.

* `htop <http://hisham.hm/htop/>`_ has been added which can be run
  from :ref:`Shell`.

* The `jed <http://www.jedsoft.org/jed/>`_ editor has been added and
  can be run from :ref:`Shell`.

.. _What's New Since 9.10 was Released:

What's New Since 9.10 was Released
----------------------------------

FreeNAS® uses a "rolling release" model instead of point releases. The
:ref:`Update` mechanism makes it easy to keep up-to-date with the
latest security fixes, bug fixes, and new features. Some updates
affect the user interface, so this section lists any functional
changes that have occurred since 9.10 was released.

.. note:: The screenshots in this documentation assume that your
          system is fully updated to the latest STABLE version of
          FreeNAS® |version|. If a screen on your system looks
          different than the documentation, make sure that the system
          is fully up-to-date. If is is not, apply any outstanding
          updates.

* UEFI boot support has been added for both new installs and upgrades.
  Installer images contain hybrid BIOS/UEFI support so that they can
  be installed on both types of firmware.

* Support for Mellanox ConnectX-4 40Gb adapter cards has been added.

* Samba has been updated to
  `4.3.6 <https://www.samba.org/samba/history/samba-4.3.6.html>`_.

* Smartmontools has been updated to `6.5
  <https://www.smartmontools.org/browser/tags/RELEASE_6_5/smartmontools/NEWS>`_
  which adds
  `NVMe support <https://www.smartmontools.org/wiki/NVMe_Support>`_.

* The "Syslog level" drop-down menu has been added to
  :menuselection:`System --> General`.

* The "Keep" / "Unkeep" button has been added to
  :menuselection:`System --> Boot` and the "Keep" column has been
  added to this screen.

* The "Readonly" column has been added to :menuselection:`Storage -->
  Volumes --> View Volumes` so that it is easy to visualize which are
  read-only replications from another server.

* The "fruit", "shell_snap", "snapper", "unityed_media", and "worm"
  VFS objects have been added to :menuselection:`Sharing --> Windows
  (CIFS Shares) --> Add Windows (CIFS) Share --> Advanced Mode -->
  VFS Objects`, while the "notify_fam" VFS object has been removed.
  The "recycle", "shadow_copy2", "zfs_space", and "zfsacl" VFS objects
  have been hidden from this screen as they are always enabled.

* The "SMB3_02" and "SMB3_11" protocols have been added to the "Server
  minimum protocol" and "Server maximum protocol" drop-down menus
  :menuselection:`Services --> CIFS`. The default "Server maximum
  protocol" is now "SMB3".

* The "SMB2_22" and "SMB2_24" protocols have been removed from the
  "Server minimum protocol" and "Server maximum protocol" drop-down
  menus :menuselection:`Services --> CIFS` as they are not used by any
  Windows products.

* The "NFSv3 ownership model for NFSv4" checkbox has been added to
  :menuselection:`Services --> NFS`.

* The "Auxiliary Parameters" field of :menuselection:`Services -->
  UPS` has been split into two so that you can specify additional
  :file:`ups.conf` and :file:`upsd.conf` settings.

* An alert will be generated for these two conditions: an update
  failed or an update completed and the system needs a reboot in order
  to complete the updating process.

* :command:`iohyve` has been updated to version 0.7.5.

* Timestamps have been added to alerts.

* The :command:`nslookup` and :command:`dig` command line utilities
  have returned.

.. index:: Hardware Recommendations
.. _Hardware Recommendations:

Hardware Recommendations
------------------------

Since FreeNAS® |release| is based on FreeBSD 10.3, it supports the
same hardware found in the `FreeBSD Hardware Compatibility List
<http://www.freebsd.org/releases/10.3R/hardware.html>`__. Supported
processors are listed in section `2.1 amd64
<https://www.freebsd.org/releases/10.3R/hardware.html#proc>`_.
FreeNAS® is only available for 64-bit (also known as amd64)
processors.

.. note:: FreeNAS® boots from a GPT partition. This means that the
          system BIOS must be able to boot using either the legacy
          BIOS firmware interface or EFI.

Actual hardware requirements will vary depending upon what you are
using your FreeNAS® system for. This section provides some guidelines
to get you started. You can also skim through the `FreeNAS® Hardware
Forum <https://forums.freenas.org/index.php?forums/hardware.18/>`_ for
performance tips from other FreeNAS® users or to post questions
regarding the hardware best suited to meet your requirements. This
`forum post
<https://forums.freenas.org/index.php?threads/hardware-recommendations-read-this-first.23069/>`__
provides some specific recommendations if you are planning on
purchasing hardware. Refer to `Building, Burn-In, and Testing your
FreeNAS system
<https://forums.freenas.org/index.php?threads/building-burn-in-and-testing-your-freenas-system.17750/>`_
for detailed instructions on how to test new hardware.

.. _RAM:

RAM
~~~

The best way to get the most out of your FreeNAS® system is to install
as much RAM as possible. The recommended minimum is 8 GB of RAM. The
more RAM, the better the performance, and the
`FreeNAS® Forums <https://forums.freenas.org/index.php>`_ provide
anecdotal evidence from users on how much performance is gained by
adding more RAM.

Depending upon your use case, your system may require more RAM. Here
are some general rules of thumb:

* If you plan to use ZFS deduplication, ensure you have at least 5 GB
  RAM per TB of storage to be deduplicated.

* If you plan to use Active Directory with a lot of users, add an
  additional 2 GB of RAM for winbind's internal cache.

* If you plan on :ref:`Using the phpVirtualBox Template`, increase the
  minimum RAM size by the amount of virtual memory you configure for
  the virtual machines. For example, if you plan to install two
  virtual machines, each with 4 GB of virtual memory, the system will
  need at least 16 GB of RAM.

* If you plan to use iSCSI, install at least 16 GB of RAM, if
  performance is not critical, or at least 32 GB of RAM if performance
  is a requirement.

* If you are installing FreeNAS® on a headless system, disable the
  shared memory settings for the video card in the BIOS.

If your system supports it and your budget allows for it, install ECC
RAM. While more expensive, ECC RAM is highly recommended as it
prevents in-flight corruption of data before the error-correcting
properties of ZFS come into play, thus providing consistency for the
checksumming and parity calculations performed by ZFS. If you consider
your data to be important, use ECC RAM. This `Case Study
<http://research.cs.wisc.edu/adsl/Publications/zfs-corruption-fast10.pdf>`_
describes the risks associated with memory corruption.

If you do not have at least 8 GB of RAM, consider getting more
powerful hardware before using FreeNAS® to store your data. Plenty of
users expect FreeNAS® to function with less than these requirements,
just at reduced performance.  The bottom line is that these minimums
are based on feedback from many users. Users that do not meet these
requirements and who ask for help in the forums or IRC will likely be
ignored because of the abundance of information that FreeNAS® may not
behave properly with less than 8 GB of RAM.

.. _Compact or USB Flash:

Compact or USB Flash
~~~~~~~~~~~~~~~~~~~~

The FreeNAS® operating system is installed to at least one device that
is separate from the storage disks. The device can be a USB stick,
compact flash, or SSD. Technically, it can also be installed onto a
hard drive, but this is discouraged as that drive will then become
unavailable for data storage.

.. note:: If you will be burning the installation file to a USB stick,
          you will need **two** USB slots, each with an inserted USB
          device, where one USB stick contains the installer and the
          other USB stick is selected to install into. When performing
          the installation, be sure to select the correct USB device
          to install to. In other words, you can **not** install
          FreeNAS® into the same USB stick that you boot the installer
          from. After installation, remove the USB stick containing
          the installer, and if necessary, configure the BIOS to boot
          from the remaining USB stick.

When determining the type and size of device to install the operating
system to, keep the following points in mind:

- the *bare minimum* size is 4 GB. This provides room for the
  operating system and two boot environments. Since each update
  creates a boot environment, the *recommended* minimum is at least 8
  GB or 16 GB as this provides room for more boot environments.

- if you plan to make your own boot environments, budget about 1 GB of
  storage per boot environment. Consider deleting older boot
  environments once you are sure that a boot environment is no longer
  needed. Boot environments can be created and deleted using
  :menuselection:`System --> Boot`.

- when using a USB stick, it is recommended to use a name brand USB
  stick as ZFS will quickly reveal errors on cheap, poorly made
  sticks.

- if a reliable boot disk is required, use two identical devices and
  select them both during the installation. Doing so will create a
  mirrored boot device.

.. _Storage Disks and Controllers:

Storage Disks and Controllers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The `Disk section
<http://www.freebsd.org/releases/10.3R/hardware.html#DISK>`_ of the
FreeBSD Hardware List lists the supported disk controllers. In
addition, support for 3ware 6 gbps RAID controllers has been added
along with the CLI utility :command:`tw_cli` for managing 3ware RAID
controllers.

FreeNAS® supports hot pluggable drives. To use this feature, make sure
that AHCI is enabled in the BIOS.

If you need reliable disk alerting and immediate reporting of a failed
drive, use an HBA such as an Avago MegaRAID controller or a 3Ware
twa-compatible controller.

Suggestions for testing disks before adding them to a RAID array can
be found in this `forum post
<https://forums.freenas.org/index.php?threads/checking-new-hdds-in-raid.12082/>`__.

`This article <http://technutz.com/purpose-built-nas-hard-drives/>`_
provides a good overview of hard drives which are well suited for a
NAS.

If you have some money to spend and wish to optimize your disk
subsystem, consider your read/write needs, your budget, and your RAID
requirements:

* If you have steady, non-contiguous writes, use disks with low seek
  times. Examples are 10K or 15K SAS drives which cost about $1/GB. An
  example configuration would be six 600 GB 15K SAS drives in a RAID
  10 which would yield 1.8 TB of usable space or eight 600 GB 15K SAS
  drives in a RAID 10 which would yield 2.4 TB of usable space.

* 7200 RPM SATA disks are designed for single-user sequential I/O and
  are not a good choice for multi-user writes.

If you have the budget and high performance is a key requirement,
consider a `Fusion-I/O card <http://www.fusionio.com/products/>`_
which is optimized for massive random access. These cards are
expensive and are suited for high-end systems that demand performance.
A Fusion-I/O card can be formatted with a filesystem and used as
direct storage; when used this way, it does not have the write issues
typically associated with a flash device. A Fusion-I/O card can also
be used as a cache device when your ZFS dataset size is bigger than
your RAM. Due to the increased throughput, systems running these cards
typically use multiple 10 GigE network interfaces.

If you will be using ZFS, `Disk Space Requirements for ZFS Storage
Pools
<http://docs.oracle.com/cd/E19253-01/819-5461/6n7ht6r12/index.html>`_
recommends a minimum of 16 GB of disk space. Due to the way that ZFS
creates swap, **you cannot format less than 3 GB of space with ZFS**.
However, on a drive that is below the minimum recommended size you
lose a fair amount of storage space to swap: for example, on a 4 GB
drive, 2 GB will be reserved for swap.

If you are new to ZFS and are purchasing hardware, read through `ZFS
Storage Pools Recommendations
<http://www.solarisinternals.com/wiki/index.php/ZFS_Best_Practices_Guide#ZFS_Storage_Pools_Recommendations>`_
first.

ZFS uses dynamic block sizing, meaning that it is capable of striping
different sized disks. However, if you care about performance, use
disks of the same size. Further, when creating a RAIDZ*, only the size
of the smallest disk will be used on each disk.

.. _Network Interfaces:

Network Interfaces
~~~~~~~~~~~~~~~~~~

The `Ethernet section
<http://www.freebsd.org/releases/10.3R/hardware.html#ethernet>`_ of
the FreeBSD Hardware Notes indicates which interfaces are supported by
each driver. While many interfaces are supported, FreeNAS® users have
seen the best performance from Intel and Chelsio interfaces, so
consider these brands if you are purchasing a new NIC. Realteks will
perform poorly under CPU load as interfaces with these chipsets do not
provide their own processors.

At a minimum, a GigE interface is recommended. While GigE interfaces
and switches are affordable for home use, modern disks can easily
saturate 110 MB/s. If you require higher network throughput, you can
bond multiple GigE cards together using the LACP type of :ref:`Link
Aggregations`. However, the switch will need to support LACP which
means you will need a more expensive managed switch.

If network performance is a requirement and you have some money to
spend, use 10 GigE interfaces and a managed switch. If you are
purchasing a managed switch, consider one that supports LACP and jumbo
frames as both can be used to increase network throughput. Refer to
the `10 Gig Networking Primer
<https://forums.freenas.org/index.php?threads/10-gig-networking-primer.25749/>`_
for more information.

.. note:: At this time, the following are not supported: InfiniBand,
          FibreChannel over Ethernet, or wireless interfaces.

If network speed is a requirement, consider both your hardware and the
type of shares that you create. On the same hardware, CIFS will be
slower than FTP or NFS as Samba is `single-threaded
<https://www.samba.org/samba/docs/man/Samba-Developers-Guide/architecture.html>`_.
If you will be using CIFS, use a fast CPU.

Wake on LAN (WOL) support is dependent upon the FreeBSD driver for the
interface. If the driver supports WOL, it can be enabled using
`ifconfig(8) <http://www.freebsd.org/cgi/man.cgi?query=ifconfig>`_. To
determine if WOL is supported on a particular interface, specify the
interface name to the following command. In this example, the
capabilities line indicates that WOL is supported for the *re0*
interface::

 ifconfig -m re0
 re0: flags=8943<UP,BROADCAST,RUNNING,PROMISC,SIMPLEX,MULTICAST> metric 0 mtu 1500
 options=42098<VLAN_MTU,VLAN_HWTAGGING,VLAN_HWCSUM,WOL_MAGIC,VLAN_HWTSO>
 capabilities=5399b<RXCSUM,TXCSUM,VLAN_MTU,VLAN_HWTAGGING,VLAN_HWCSUM,TSO4,WOL_UCAST,WOL_MCAST, WOL_MAGIC,VLAN_HWFILTER,VLAN_H WTSO>

If you find that WOL support is indicated but not working for a
particular interface, create a bug report using the instructions in
:ref:`Support`.

.. include:: zfsprimer.rst
