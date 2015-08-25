.. centered:: FreeNAS® is © 2011-2015 iXsystems

.. centered:: FreeNAS® and the FreeNAS® logo are registered trademarks of iXsystems.
   
.. centered:: FreeBSD is a registered trademark of the FreeBSD Foundation

Written by users of the FreeNAS® network-attached storage operating system.

Version 9.3.1

Copyright © 2011-2015
`iXsystems <http://www.ixsystems.com/>`_

This Guide covers the installation and use of FreeNAS® 9.3.1.

The FreeNAS® Users Guide is a work in progress and relies on the contributions of many individuals. If you are interested in helping us to improve the Guide,
read the instructions in the `README <https://github.com/freenas/freenas/blob/master/docs/userguide/README>`_. If you use IRC Freenode, you are welcome to join
the #freenas channel where you will find other FreeNAS® users.

The FreeNAS® Users Guide is freely available for sharing and redistribution under the terms of the
`Creative Commons Attribution License <http://creativecommons.org/licenses/by/3.0/>`_. This means that you have permission to copy, distribute, translate, and adapt the
work as long as you attribute iXsystems as the original source of the Guide.

FreeNAS® and the FreeNAS® logo are registered trademarks of iXsystems.

Active Directory® is a registered trademark or trademark of Microsoft Corporation in the United States and/or other countries.

Apple, Mac and Mac OS are trademarks of Apple Inc., registered in the U.S. and other countries.

Chelsio® is a registered trademark of Chelsio Communications.

Cisco® is a registered trademark or trademark of Cisco Systems, Inc. and/or its affiliates in the United States and certain other countries.

Django® is a registered trademark of Django Software Foundation.

Facebook® is a registered trademark of Facebook Inc.

FreeBSD and the FreeBSD logo are registered trademarks of the FreeBSD Foundation.

Fusion-io is a trademark or registered trademark of Fusion-io, Inc.

Intel, the Intel logo, Pentium Inside, and Pentium are trademarks of Intel Corporation in the U.S. and/or other countries.

LinkedIn® is a registered trademark of LinkedIn Corporation.

Linux® is a registered trademark of Linus Torvalds.

Marvell® is a registered trademark of Marvell or its affiliates.

Oracle is a registered trademark of Oracle Corporation and/or its affiliates.

Twitter is a trademark of Twitter, Inc. in the United States and other countries.

UNIX® is a registered trademark of The Open Group.

VirtualBox® is a registered trademark of Oracle.

VMware® is a registered trademark of VMware, Inc.

Wikipedia® is a registered trademark of the Wikimedia Foundation, Inc., a non-profit organization.

Windows® is a registered trademark of Microsoft Corporation in the United States and other countries.

**Typographic Conventions**

The FreeNAS® 9.3.1 Users Guide uses the following typographic conventions:

* Names of graphical elements such as buttons, icons, fields, columns, and boxes are enclosed within quotes. For example: click the "Import CA" button.

* Menu selections are italicized and separated by arrows. For example: :menuselection:`System --> Information`.

* Commands that are mentioned within text are highlighted in :command:`bold text`. Command examples and command output are contained in green code blocks.

* Volume, dataset, and file names are enclosed in a blue box :file:`/like/this`.

* Keystrokes are formatted in a blue box. For example: press :kbd:`Enter`.

* **bold text:** used to emphasize an important point.

* *italic text:* used to represent device names or text that is input into a GUI field.

.. _Introduction:

Introduction
============

FreeNAS® is an embedded open source network-attached storage (NAS) operating system based on FreeBSD and released under a BSD license. A NAS is an operating
system that has been optimized for file storage and sharing.

FreeNAS® provides a browser-based, graphical configuration interface. Its built-in networking protocols can be configured to provide storage access to a
wide range of operating systems. A plugins system is provided for extending the built-in features by installing additional software.

.. _What's New Since 9.3-RELEASE:

What's New Since 9.3-RELEASE
----------------------------

Beginning with version 9.3, FreeNAS® uses a "rolling release" model instead of point releases. The new :ref:`Update` mechanism makes it easy to keep
up-to-date with the latest security fixes, bug fixes, and new features. Some updates affect the user interface so this section lists any functional changes
that have occurred since 9.3-RELEASE.

.. note:: the screenshots in this documentation assume that your system is fully updated to the latest STABLE version of FreeNAS® 9.3.1. If a screen on your
   system looks different than the documentation, make sure that the system is fully up-to-date and apply any outstanding updates if it is not.

* Samba was updated to `4.1.18 <https://www.samba.org/samba/history/samba-4.1.18.html>`_.

* Netatalk was updated to `3.1.7 <http://netatalk.sourceforge.net/3.1/ReleaseNotes3.1.7.html>`_.

* SSSD was updated to `1.11.7 <https://fedorahosted.org/sssd/wiki/Releases/Notes-1.11.7>`_.

* Nut has been updated to `2.7.3 <http://www.networkupstools.org/source/2.7/new-2.7.3.txt>`_ which adds support for several new devices, including the Tripp Lite SMART500RT1U UPS.

* The driver for the Intel X710 10GbE adapter was added.

* The supported Avago (formerly known as LSI) MegaRAID HBA firmware version has been updated to v20 and the alert regarding a version mismatch has been updated accordingly.

* The 12Gbps Avago HBA driver, mpr(4), has been updated to version 9 and an alert will be issued if there is a version mismatch. The :command:`sas3ircu` command line utility
  has also been added. This tool is similar in functionality to the :command:`sas2ircu` tool which is for MegaRAID HBAs using the mps(4) driver.

* The mrsas(4) Avago MegaRAID driver was added.

* Support for the Mach Xtreme MX-ES/MXUB3 and the Kingston DT100G2 USB drives has been added.

* Support for Avago MegaRAID SAS passthrough has been added.

* Man pages have been added and can be accessed from :ref:`Shell`.

* LZ4 compression is used on the boot pool in order to increase space for boot environments.

* Support for hot spare drive replacement has been added. If you have spare drives in your pool, and a drive fails, FreeNAS® should automatically remove the failed
  drive from the pool and replace it with the spare.

* An installation of STABLE, as of 201501212031, now creates two boot environments. The system will boot into the *default* boot environment and users can
  make their changes and update from this version. The other boot environment, named *Initial-Install* can be booted into if the system needs to be returned
  to a pristine, non-configured version of the installation.

* The "Create backup" and "Restore from a backup" options have been added to the FreeNAS® console setup menu shown in Figure 3a.

* The "Microsoft Account" checkbox has been added to :menuselection:`Account --> Users --> Add User`.

* The ability to set the boot pool scrub interval has been added to :menuselection:`System --> Boot`.

* The size of and the amount of used space in the boot pool is displayed in :menuselection:`System --> Boot`.

* The "Enable automatic upload of kernel crash dumps and daily telemetry" checkbox has been added to :menuselection:`System --> Advanced`.

* A "Backup" button has been added to :menuselection:`System --> Advanced`.

* The "Periodic Notification User" drop-down menu has been added to :menuselection:`System --> Advanced`.

* The "Performance Test" button has been removed from :menuselection:`System --> Advanced`.

* The system will issue an alert if an update fails and the details of the failure will be written to :file:`/data/update.failed`.

* The "Confirm Passphrase" field has been added to :menuselection:`System --> CAs --> Import CA`
  and :menuselection:`System --> Certificates --> Import Certificate`.

* The "Support" tab has been added to :menuselection:`System --> Support`, providing a convenient method for reporting a bug or requesting a new feature.

* The "Rsync Create" checkbox has been renamed to "Validate Remote Path" and the "Delay Updates" checkbox has been added to
  :menuselection:`Tasks --> Rsync Tasks --> Add Rsync Task`.

* The "VLAN ID" field has been added to :menuselection:`Network --> IPMI`.

* A reboot is no longer required when creating :ref:`Link Aggregations`.

* The "Exclude System Dataset" checkbox has been added to :menuselection:`Storage --> Periodic Snapshot Tasks --> Add Periodic Snapshot`.

* The :file:`/usr/local/bin/test_ssh.py` script has been added for testing the SSH connection for a defined replication task.

* The "Encryption Mode" and "Certificate" drop-down menus have been added to :menuselection:`Directory Service --> Active Directory`.

* A pop-up warning will appear if you go to change :menuselection:`Directory Service --> Active Directory --> Advanced Mode -> Idmap backend` as selecting the wrong
  backend will break Active Directory integration.

* The "Schema" drop-down menu has been added to :menuselection:`Directory Service --> LDAP`.

* The "Kerberos Settings" tab as been added to :ref:`Directory Service`.

* The ability to "Online" a previously offlined disk has been added to :menuselection:`Storage --> Volumes --> Volume Status`.

* The "Periodic Snapshot Task" drop-down menu has been added to :menuselection:`Sharing --> Windows (CIFS) --> Add Windows (CIFS) Share`.

* All available VFS objects have been added to :menuselection:`Sharing --> Windows (CIFS) --> Add Windows (CIFS) Share --> Advanced Mode --> VFS Objects`
  and the "aio_pthread" and "streams_xattr" VFS objects are enabled by default.

* The "Pool Available Size Threshold" field has been renamed to "Pool Available Space Threshold" in
  :menuselection:`Sharing --> Block (iSCSI) --> Target Global Configuration`.

* The "Discovery Auth Method" and "Discovery Auth Group" fields have moved from :menuselection:`Sharing --> Block (iSCSI) --> Target Global Configuration` to
  :menuselection:`Sharing --> Block (iSCSI) --> Portals --> Add Portal`.
  
* The "Logical Block Size" field has been moved from :menuselection:`Sharing --> Block (iSCSI) --> Targets --> Add Target` to
  :menuselection:`Sharing --> Block (iSCSI) --> Extents --> Add Extent`.

* The "Serial" field has been moved from  :menuselection:`Sharing --> Block (iSCSI) --> Targets --> Add Target` to :menuselection:`Sharing --> Block (iSCSI) --> Extents --> Add Extent`. 

* The :menuselection:`Sharing --> Block (iSCSI) --> Targets --> Add Target` screen now supports the creation of multiple iSCSI groups.

* The "Disable Physical Block Size Reporting" checkbox, "Available Space Threshold" field, and "LUN RPM" drop-down menu have been added to
  :menuselection:`Sharing --> Block (iSCSI) --> Extents --> Add Extent`.

* The "Home share name" field  has been added to :menuselection:`Services --> AFP`.

* The "DNS Backend" field has been removed from :menuselection:`Services --> Domain Controller` as BIND is not included in FreeNAS®.

* The "Require Kerberos for NFSv4" checkbox has been added to :menuselection:`Services --> NFS`.

* The "SNMP v3 Support" checkbox, "Username", "Password", and "Privacy Passphrase" fields, and "Authentication Type" and "Privacy Protocol" drop-down menus have been added to
  :menuselection:`Services --> SNMP` so that SNMPv3 can be configured.

* The "Power Off UPS" checkbox had been added to :menuselection:`Services --> UPS`.

* The MediaBrowser Plugin has been renamed to Emby.

* The :menuselection:`Jails --> Add Jails` button has been renamed to "Add Jail".

* A "Restart" button is now available when you click the entry for an installed jail.

* The "Mtree" field and "Read-only" checkbox have been added to :menuselection:`Jails --> Templates --> Add Jail Templates`.

* The "Mtree" field has been added to the "Edit" options for existing jail templates.

* The **-C**, **-D** and **-j** options have been added to :ref:`freenas-debug`.

* A :ref:`Support Icon` has been added to the top menubar, providing a convenient method for reporting a bug or requesting a new feature.

* The "Help" icon has been replaced by the :ref:`Guide` icon, providing an offline version of the FreeNAS® User Guide (this documentation).

* A warning message now occurs if you stop the iSCSI service when initiators are connected. Type :command:`ctladm islist` to determine the names of the
  connected initiators.

* An alert will be generated when a new update becomes available.

* An alert will be generated when a S.M.A.R.T. error occurs.

* An alert will be generated if a Certificate Authority or certificate is invalid or malformed.

* The :command:`zfslower.d` DTrace script has been added. This script is useful for determining the cause of latency, where a reasonable latency might be
  10 ms. If you run :command:`dtrace -s zfslower.d 10`, it will display all ZFS operations that take longer than 10ms. If no ZFS operations take longer than 10ms
  but the client is experiencing latency, you know it is not a filesystem issue.

.. index:: Hardware Recommendations
.. _Hardware Recommendations:

Hardware Recommendations
------------------------

Since FreeNAS® 9.3.1 is based on FreeBSD 9.3, it supports the same hardware found in the `FreeBSD Hardware Compatibility List
<http://www.freebsd.org/releases/9.3R/hardware.html>`__. Supported processors are listed in section
`2.1 amd64 <https://www.freebsd.org/releases/9.3R/hardware.html#proc>`_. Beginning with version 9.3, FreeNAS® is only available for 64-bit (also known as
amd64) processors.

.. note:: beginning with version 9.3, FreeNAS® boots from a GPT partition. This means that the system BIOS must be able to boot using either the legacy BIOS
          firmware interface or EFI.

Actual hardware requirements will vary depending upon what you are using your FreeNAS® system for. This section provides some guidelines to get you started.
You can also skim through the
`FreeNAS® Hardware Forum <https://forums.freenas.org/index.php?forums/hardware.18/>`_ for performance tips from other FreeNAS® users or to post questions
regarding the hardware best suited to meet your requirements. This
`forum post <https://forums.freenas.org/index.php?threads/hardware-recommendations-read-this-first.23069/>`_
provides some specific recommendations if you are planning on purchasing hardware. Refer to
`Building, Burn-In, and Testing your FreeNAS system <https://forums.freenas.org/index.php?threads/building-burn-in-and-testing-your-freenas-system.17750/>`_ for
detailed instructions on how to test new hardware.

.. _RAM:

RAM
~~~

The best way to get the most out of your FreeNAS® system is to install as much RAM as possible. The recommended minimum is 8 GB of RAM. The more RAM, the
better the performance, and the `FreeNAS® Forums <https://forums.freenas.org/index.php>`_
provide anecdotal evidence from users on how much performance is gained by adding more RAM.

Depending upon your use case, your system may require more RAM. Here are some general rules of thumb:

* If you plan to use ZFS deduplication, ensure you have at least 5 GB RAM per TB of storage to be deduplicated.

* If you plan to use Active Directory with a lot of users, add an additional 2 GB of RAM for winbind's internal cache.

* If you plan on :ref:`Using the phpVirtualBox Template`, increase the minimum RAM size by the amount of virtual memory you configure for the virtual machines. For example, if you
  plan to install two virtual machines, each with 4GB of virtual memory, the system will need at least 16GB of RAM.

* If you plan to use iSCSI, install at least 16GB of RAM, if performance is not critical, or at least 32GB of RAM if performance is a requirement.

* If you are installing FreeNAS® on a headless system, disable the shared memory settings for the video card in the BIOS.

If your system supports it and your budget allows for it, install ECC RAM. While more expensive, ECC RAM is highly recommended as it prevents in-flight
corruption of data before the error-correcting properties of ZFS come into play, thus providing consistency for the checksumming and parity calculations
performed by ZFS. If you consider your data to be important, use ECC RAM. This 
`Case Study <http://research.cs.wisc.edu/adsl/Publications/zfs-corruption-fast10.pdf>`_ describes the risks associated with memory corruption.

If you don't have at least 8GB of RAM, you should consider getting more powerful hardware before using FreeNAS® to store your data. Plenty of users expect
FreeNAS® to function with less than these requirements, just at reduced performance.  The bottom line is that these minimums are based on the feedback of
many users. Users that do not meet these requirements and who ask for help in the forums or IRC will likely be ignored because of the abundance of information
that FreeNAS® may not behave properly with less than 8GB of RAM.

.. _Compact or USB Flash:

Compact or USB Flash
~~~~~~~~~~~~~~~~~~~~

The FreeNAS® operating system is installed to at least one device that is separate from the storage disks. The device can be a USB stick, compact flash,
or SSD. Technically, it can also be installed onto a hard drive, but this is discouraged as that drive will then become unavailable for data storage.

.. note:: if you will be burning the installation file to a USB stick, you will need **two** USB slots, each with an inserted USB device, where one USB stick
          contains the installer and the other USB stick is selected to install into. When performing the installation, be sure to select the correct USB
          device to install to. In other words, you can **not** install FreeNAS® into the same USB stick that you boot the installer from. After
          installation, remove the USB stick containing the installer, and if necessary, configure the BIOS to boot from the remaining USB stick.

When determining the type and size of device to install the operating system to, keep the following points in mind:

- the *bare* minimum size is 4GB. This provides room for the operating system and two boot environments. Since each update creates a boot environment, the
  *recommended* minimum is at least 8GB or 16GB as this provides room for more boot environments.

- if you plan to make your own boot environments, budget about 1GB of storage per boot environment. Consider deleting older boot environments once you are
  sure that a boot environment is no longer needed. Boot environments can be created and deleted using :menuselection:`System --> Boot`.

- when using a USB stick, it is recommended to use a name brand USB stick as ZFS will quickly find errors on cheap, not well made sticks.

- when using a USB stick, USB 3.0 support is disabled by default as it currently is not compatible with some hardware, including Haswell (Lynx point)
  chipsets. If you receive a "failed with error 19" message when trying to boot FreeNAS®, make sure that xHCI/USB3 is disabled in the system BIOS. While this
  will downclock the USB ports to 2.0, the bootup and shutdown times will not be significantly different. To see if USB 3.0 support works with your hardware,
  follow the instructions in :ref:`Tunables` to create a "Tunable" named *xhci_load*, set its value to *YES*, and reboot the system.
  
- if a reliable boot disk is required, use two identical devices and select them both during the installation. Doing so will create a mirrored boot device.

.. _Storage Disks and Controllers:

Storage Disks and Controllers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The
`Disk section <http://www.freebsd.org/releases/9.3R/hardware.html#DISK>`_
of the FreeBSD Hardware List lists the supported disk controllers. In addition, support for 3ware 6gbps RAID controllers has been added along with the CLI
utility :command:`tw_cli` for managing 3ware RAID controllers.

FreeNAS® supports hot pluggable drives. To use this feature, make sure that AHCI is enabled in the BIOS.

If you need reliable disk alerting and immediate reporting of a failed drive, use an HBA such as an Avago
MegaRAID controller or a 3Ware twa-compatible controller.

Suggestions for testing disks before adding them to a RAID array can be found in this
`forum post <https://forums.freenas.org/index.php?threads/checking-new-hdds-in-raid.12082/>`_.

`This article <http://technutz.com/purpose-built-nas-hard-drives/>`_
provides a good overview of hard drives which are well suited for a NAS.

If you have some money to spend and wish to optimize your disk subsystem, consider your read/write needs, your budget, and your RAID requirements:

* If you have steady, non-contiguous writes, use disks with low seek times. Examples are 10K or 15K SAS drives which cost about $1/GB. An example
  configuration would be six 600 GB 15K SAS drives in a RAID 10 which would yield 1.8 TB of usable space or eight 600 GB 15K SAS drives in a RAID 10 which
  would yield 2.4 TB of usable space.

* 7200 RPM SATA disks are designed for single-user sequential I/O and are not a good choice for multi-user writes.

If you have the budget and high performance is a key requirement, consider a
`Fusion-I/O card <http://www.fusionio.com/products/>`_
which is optimized for massive random access. These cards are expensive and are suited for high-end systems that demand performance. A Fusion-I/O card can be
formatted with a filesystem and used as direct storage; when used this way, it does not have the write issues typically associated with a flash device. A
Fusion-I/O card can also be used as a cache device when your ZFS dataset size is bigger than your RAM. Due to the increased throughput, systems running these
cards typically use multiple 10 GigE network interfaces.

If you will be using ZFS,
`Disk Space Requirements for ZFS Storage Pools <http://docs.oracle.com/cd/E19253-01/819-5461/6n7ht6r12/index.html>`_
recommends a minimum of 16 GB of disk space. Due to the way that ZFS creates swap, **you can not format less than 3 GB of space with ZFS**. However, on a
drive that is below the minimum recommended size you lose a fair amount of storage space to swap: for example, on a 4 GB drive, 2 GB will be reserved for
swap.

If you are new to ZFS and are purchasing hardware, read through
`ZFS Storage Pools Recommendations <http://www.solarisinternals.com/wiki/index.php/ZFS_Best_Practices_Guide#ZFS_Storage_Pools_Recommendations>`_
first.

ZFS uses dynamic block sizing, meaning that it is capable of striping different sized disks. However, if you care about performance, use disks of the same
size. Further, when creating a RAIDZ*, only the size of the smallest disk will be used on each disk.

.. _Network Interfaces:

Network Interfaces
~~~~~~~~~~~~~~~~~~

The
`Ethernet section <http://www.freebsd.org/releases/9.3R/hardware.html#ETHERNET>`_
of the FreeBSD Hardware Notes indicates which interfaces are supported by each driver. While many interfaces are supported, FreeNAS® users have seen the best
performance from Intel and Chelsio interfaces, so consider these brands if you are purchasing a new NIC. Realteks will perform poorly under CPU load as
interfaces with these chipsets do not provide their own processors.

At a minimum, a GigE interface is recommended. While GigE interfaces and switches are affordable for home use, modern disks can easily saturate 110 MB/s. If
you require higher network throughput, you can bond multiple GigE cards together using the LACP type of :ref:`Link Aggregations`. However, the switch will
need to support LACP which means you will need a more expensive managed switch.

If network performance is a requirement and you have some money to spend, use 10 GigE interfaces and a managed switch. If you are purchasing a managed switch,
consider one that supports LACP and jumbo frames as both can be used to increase network throughput. Refer to the
`10 Gig Networking Primer <https://forums.freenas.org/index.php?threads/10-gig-networking-primer.25749/>`_ for more information.

.. note:: at this time the following are not supported: InfiniBand, FibreChannel over Ethernet, or wireless interfaces.

If network speed is a requirement, consider both your hardware and the type of shares that you create. On the same hardware, CIFS will be slower than FTP or
NFS as Samba is
`single-threaded <https://www.samba.org/samba/docs/man/Samba-Developers-Guide/architecture.html>`_. If you will be using CIFS, use a fast CPU.

Wake on LAN (WOL) support is dependent upon the FreeBSD driver for the interface. If the driver supports WOL, it can be enabled using
`ifconfig(8) <http://www.freebsd.org/cgi/man.cgi?query=ifconfig>`_. To determine if WOL is supported on a particular interface, specify the interface name to
the following command. In this example, the capabilities line indicates that WOL is supported for the *re0* interface::

 ifconfig -m re0
 re0: flags=8943<UP,BROADCAST,RUNNING,PROMISC,SIMPLEX,MULTICAST> metric 0 mtu 1500
 options=42098<VLAN_MTU,VLAN_HWTAGGING,VLAN_HWCSUM,WOL_MAGIC,VLAN_HWTSO>
 capabilities=5399b<RXCSUM,TXCSUM,VLAN_MTU,VLAN_HWTAGGING,VLAN_HWCSUM,TSO4,WOL_UCAST,WOL_MCAST, WOL_MAGIC,VLAN_HWFILTER,VLAN_H WTSO>

If you find that WOL support is indicated but not working for a particular interface, create a bug report using the instructions in :ref:`Support`.

.. include:: zfsprimer.rst

