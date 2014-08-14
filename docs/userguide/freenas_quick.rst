:orphan:

Configuration Quick Start
=========================

This section demonstrates the initial preparation that should be performed before you start to configure the FreeNAS® system. It then provides an overview of
the configuration workflow.

.. note:: it is important to use the GUI (or the console) for all configuration changes. FreeNAS® uses a configuration database to store its settings. While
   you can use the command line to modify your configuration, changes made at the command line are not written to the configuration database. This means that
   any changes made at the command line will not persist after a reboot and will be overwritten by the values in the configuration database during an upgrade.

Set the Root Password
---------------------

The first time you access the FreeNAS® administrative interface, a pop-up window will prompt you to set the *root* password. You should set a hard to guess
password as anyone who knows this password can gain access to the FreeNAS® administrative GUI.

.. note:: for security reasons, the SSH service and *root* SSH logins are disabled by default. Unless these are set, the only way to access a shell as
   *root* is to gain physical access to the console menu or to access the web shell within the administrative GUI. This means that the FreeNAS® system should
   be kept physically secure and that the administrative GUI should be behind a properly configured firewall and protected by a secure password.


Set the Email Address
---------------------

FreeNAS® provides an Alert icon in the upper right corner to provide a visual indication of events that warrant administrative attention. The alert system
automatically emails the *root* user account whenever an alert is issued.

To set the email address for the *root* account, go to :menuselection:`Account --> Users --> View Users`. Click the "Change E-mail" button associated with the
*root* user account and input the email address of the person to receive the administrative emails.

Enable Console Logging
----------------------

To view system messages within the graphical administrative interface, go to :menuselection:`System --> Advanced`. Check the box "Show console
messages in the footer" and click "Save". The output of :command:`tail -f /var/log/messages` will now be displayed at the bottom of the screen. If you click
the console messages area, it will pop-up as a window, allowing you to scroll through the output and to copy its contents.

You are now ready to start configuring the FreeNAS® system. Typically, the configuration workflow will use the following steps in their listed order.

Create Storage
--------------

FreeNAS® supports the creation of both UFS and ZFS volumes; however, ZFS volumes are recommended to get the most out of your FreeNAS® system.

When creating a volume, you have several choices depending upon your storage requirements and whether or not data already exists on the disk(s). The following
options are available:

#.  Auto-import an existing UFS disk, gstripe (RAID0), gmirror (RAID1), or graid3 (RAID3) in :menuselection:`Storage --> Volumes --> Auto Import Volume`.

#.  Auto-import an existing ZFS disk, stripe, mirror, RAIDZ1, RAIDZ2, or RAIDZ3 in :menuselection:`Storage --> Volumes --> Auto Import Volume`.

#.  Import a disk that is formatted with UFS, NTFS, MSDOS, or EXT2 in :menuselection:`Storage --> Volumes --> Import Volume.

#.  Format disk(s) with UFS and optionally create a gstripe (RAID0), gmirror (RAID1), or graid3 (RAID3) in
    :menuselection:`Storage --> Volumes --> UFS Volume Manager`.

#.  Format disk(s) with ZFS and optionally create a stripe, mirror, RAIDZ1, RAIDZ2, or RAIDZ3 in :menuselection:`Storage -->Volumes --> ZFS Volume Manager`.

If you format your disk(s) with ZFS, additional options are available:

#.  Divide the ZFS pool into datasets to provide more flexibility when configuring user access to data.

#.  Create a Zvol to be used when configuring an iSCSI device extent.

Create Users/Groups
-------------------

FreeNAS® supports a variety of user access scenarios:

* the use of an anonymous or guest account that everyone in the network uses to access the stored data

* the creation of individual user accounts where each user has access to their own ZFS dataset

* the addition of individual user accounts to groups where each group has access to their own volume or ZFS dataset

* the import of existing accounts from an OpenLDAP or Active Directory server

When configuring your FreeNAS® system, **select one of the following,** depending upon whether or not the network has an existing OpenLDAP or Active
Directory domain. OpenLDAP and Active Directory are mutually exclusive, meaning that you can not use both but must choose one or the other.

#.  Manually create users and groups. User management is described in Users and group management is described in Groups.

#.  Import existing Active Directory account information using the instructions in Active Directory.

#.  Import existing OpenLDAP account information using the instructions in LDAP.

Configure Permissions
---------------------

Setting permissions is an important aspect of configuring access to storage data. The graphical administrative interface is meant to set the **initial**
permissions in order to make a volume or dataset accessible as a share. Once a share is available, the client operating system should be used to fine-tune the
permissions of the files and directories that are created by the client.

Configured volumes and datasets will appear in :menuselection:`Storage --> Volumes`. Each volume and dataset will have its own "Change Permissions" option,
allowing for greater flexibility when providing access to data.

Before creating your shares, determine which users should have access to which data. This will help you to determine if multiple volumes, datasets, and/or
shares should be created to meet the permissions needs of your environment.

Configure Sharing
-----------------

Once your volumes have been configured with permissions, you are ready to configure the type of share or service that you determine is suitable for your
network.

FreeNAS® supports several types of shares and sharing services for providing storage data to the clients in a network. It is recommended that you
**select only one type of share per volume or dataset** in order to prevent possible conflicts between different types of shares. The type of share you
create depends upon the operating system(s) running in your network, your security requirements, and expectations for network transfer speeds. The following
types of shares and services are available:

* **Apple (AFP):** FreeNAS® uses Netatalk to provide sharing services to Apple clients. This type of share is a good choice if all of your computers run
  Mac OS X.

* **Unix (NFS):** this type of share is accessible by Mac OS X, Linux, BSD, and professional/enterprise versions of Windows. It is a good choice if there
  are many different operating systems in your network.

* **Windows (CIFS):** FreeNAS® uses Samba to provide the SMB/CIFS sharing service. This type of share is accessible by Windows, Mac OS X, Linux, and BSD
  computers, but it is slower than an NFS share. If your network contains only Windows systems, this is a good choice.

* **FTP:** this service provides fast access from any operating system, using a cross-platform FTP and file manager client application such as Filezilla.
  FreeNAS® supports encryption and chroot for FTP.

* **SSH:** this service provides encrypted connections from any operating system using SSH command line utilities or the graphical WinSCP application for
  Windows clients.

* **iSCSI:** FreeNAS® supports the export of virtual disk drives that are accessible to clients running iSCSI initiator software.

Start Service(s)
----------------

Once you have configured your share or service, you will need to start its associated service(s) in order to implement the configuration. By default, all
services are off until you start them. The status of services is managed using :menuselection:`Services --> Control Services`. To start a service, click its
red "OFF" button. After a second or so, it will change to a blue ON, indicating that the service has been enabled. Watch the console messages as the service
starts to determine if there are any error messages.

Test Configuration
------------------

If the service successfully starts, try to make a connection to the service from a client system. For example, use Windows Explorer to try to connect to a
CIFS share, use an FTP client such as Filezilla to try to connect to an FTP share, or use Finder on a Mac OS X system to try to connect to an AFP share.

If the service starts correctly and you can make a connection but receive permissions errors, check that the user has permissions to the volume/dataset being
accessed.

Backup Configuration
--------------------

Once you have tested your configuration, be sure to back it up. Go to :menuselection:`System --> General` and click the "Save Config" button. Your browser
will provide an option to save a copy of the configuration database.

You should **backup your configuration whenever you make configuration changes and always before upgrading FreeNAS®**.
