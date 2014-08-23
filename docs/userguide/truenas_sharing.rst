:orphan:

Sharing Configuration
---------------------

Once you have a volume, create at least one share so that the storage is accessible by the other computers in your network. The type of share you create
depends upon the operating system(s) running in your network, your security requirements, and expectations for network transfer speeds.

.. note:: shares are created to provide and control access to an area of storage. Before creating your shares, it is recommended to make a list of the users
that will need access to storage data, which operating systems these users are using, whether or not all users should have the same permissions to the stored
data, and whether or not these users should authenticate before accessing the data. This information can help you determine which type of share(s) you need to
create, whether or not you need to create multiple datasets in order to divide up the storage into areas with differing access and permission requirements,
and how complex it will be to setup your permission requirements. It should be noted that a share is used to provide access to data. If you delete a share, it
removes access to data but does not delete the data itself.

The following types of shares and services are available:

**Apple (AFP) Shares**: the Apple File Protocol (AFP) type of share is a good choice if all of your computers run Mac OS X.

**Unix (NFS) Shares**: the Network File System (NFS) type of share is accessible by Mac OS X, Linux, BSD, and the professional/enterprise versions (not the
home editions) of Windows. It is a good choice if there are many different operating systems in your network. Depending upon the operating system, it may
require the installation or configuration of client software on the desktop.

**Windows (CIFS) Shares**: the Common Internet File System (CIFS) type of share is accessible by Windows, Mac OS X, Linux, and BSD computers, but it is slower
than an NFS share due to the single-threaded design of Samba. It provides more configuration options than NFS and is a good choice on a network containing
only Windows systems. However, it is a poor choice if the CPU on the TrueNAS® system is limited; if your CPU is maxed out, you need to upgrade the CPU or
consider another type of share.

If you are looking for a solution that allows fast access from any operating system, consider configuring the FTP service instead of a share and use a
cross-platform FTP and file manager client application such as
`Filezilla <http://filezilla-project.org/>`_. Secure FTP can be configured if the data needs to be encrypted.

If data security is a concern and your network's users are familiar with SSH command line utilities or
`WinSCP <http://winscp.net/>`_, consider configuring the SSH service instead of a share. It will be slower than unencrypted FTP due to the overhead of
encryption, but the data passing through the network will be encrypted.

.. note:: while the GUI will let you do it, it is a bad idea to share the same volume or dataset using multiple types of access methods. Different types of
shares and services use different file locking methods. For example, if the same volume is configured to use both NFS and FTP, NFS will lock a file for
editing by an NFS user, but a FTP user can simultaneously edit or delete that file. This will result in lost edits and confused users. Another example: if a
volume is configured for both AFP and CIFS, Windows users may be confused by the extra filenames used by Mac files and delete the ones they don't understand;
this will corrupt the files on the AFP share. Pick the one type of share or service that makes the most sense for the types of clients that will access that
volume, and configure that volume for that one type of share or service. If you need to support multiple types of shares, divide the volume into datasets and
use one dataset per share.

This section will demonstrate how to create AFP, NFS, and CIFS shares. FTP and SSH configurations are described in `Services Configuration`_.

Apple (AFP) Shares
~~~~~~~~~~~~~~~~~~

TrueNAS® uses the
`Netatalk <http://netatalk.sourceforge.net/>`_
AFP server to share data with Apple systems. Configuring AFP shares is a multi-step process that requires you to create or import users and groups, set
volume/dataset permissions, create the AFP share(s), configure the `AFP`_ service, then enable the AFP service in `Services --> Control Services`.

This section describes the configuration screen for creating the AFP share. It then provides configuration examples for creating a guest share, configuring
Time Machine to backup to a dataset on the TrueNAS® system, and for connecting to the share from a Mac OS X client.

Creating AFP Shares
^^^^^^^^^^^^^^^^^^^

If you click `Sharing --> Apple (AFP) Shares --> Add Apple (AFP) Share`, you will see the screen shown in Figure 9.1a. Some settings are only available in
Advanced Mode. To see these settings, either click the "Advanced Mode" button or configure the system to always display these settings by checking the box
"Show advanced fields by default" in `System --> Settings --> Advanced`.

Table 9.1a summarizes the available options when creating an AFP share. Refer to
`Setting up Netatalk <http://netatalk.sourceforge.net/2.2/htmldocs/configuration.html>`_ for a more detailed explanation of the available options.

Once you press the "OK" button when creating the AFP share, a pop-up menu will ask "Would you like to enable this service?" Click "Yes" and `Services -->
Control Services` will open and indicate whether or not the AFP service successfully started.

**Figure 9.1a: Creating an AFP Share**

|10000000000002FD00000265AF05370F_png|

.. |10000000000002FD00000265AF05370F_png| image:: images/afp.png
    :width: 6.4283in
    :height: 5.1083in

**Table 9.1a: AFP Share Configuration Options**

+------------------------------+---------------+-------------------------------------------------------------------------------------------------------------+
| Setting                      | Value         | Description                                                                                                 |
|                              |               |                                                                                                             |
+==============================+===============+=============================================================================================================+
| Name                         | string        | volume name that will appear in the Mac computer's "connect to server" dialogue; limited to 27 characters   |
|                              |               | and can not contain a period                                                                                |
|                              |               |                                                                                                             |
+------------------------------+---------------+-------------------------------------------------------------------------------------------------------------+
| Share Comment                | string        | optional                                                                                                    |
|                              |               |                                                                                                             |
+------------------------------+---------------+-------------------------------------------------------------------------------------------------------------+
| Path                         | browse button | browse to the volume/dataset to share                                                                       |
|                              |               |                                                                                                             |
+------------------------------+---------------+-------------------------------------------------------------------------------------------------------------+
| Allow List                   | string        | comma delimited list of allowed users and/or groups where groupname begins with a @                         |
|                              |               |                                                                                                             |
+------------------------------+---------------+-------------------------------------------------------------------------------------------------------------+
| Deny List                    | string        | comma delimited list of denied users and/or groups where groupname begins with a @                          |
|                              |               |                                                                                                             |
+------------------------------+---------------+-------------------------------------------------------------------------------------------------------------+
| Read-only Access             | string        | comma delimited list of users and/or groups who only have read access where groupname begins with a @       |
|                              |               |                                                                                                             |
+------------------------------+---------------+-------------------------------------------------------------------------------------------------------------+
| Read-write Access            | string        | comma delimited list of users and/or groups who have read and write access where groupname begins with a @  |
|                              |               |                                                                                                             |
+------------------------------+---------------+-------------------------------------------------------------------------------------------------------------+
| Time Machine                 | checkbox      | due to a limitation in how Mac deals with low-diskspace issues when multiple Mac's share the same volume,   |
|                              |               | checking *Time Machine* on multiple shares is discouraged as it may result in intermittent failed backups   |
|                              |               |                                                                                                             |
+------------------------------+---------------+-------------------------------------------------------------------------------------------------------------+
| Zero Device Numbers          | checkbox      | only available in "Advanced Mode"; enable when the device number is not constant across a reboot            |
|                              |               |                                                                                                             |
+------------------------------+---------------+-------------------------------------------------------------------------------------------------------------+
| No Stat                      | checkbox      | only available in "Advanced Mode"; if checked, AFP won't stat the volume path when enumerating the volumes  |
|                              |               | list; useful for automounting or volumes created by a preexec script                                        |
|                              |               |                                                                                                             |
+------------------------------+---------------+-------------------------------------------------------------------------------------------------------------+
| AFP3 UNIX Privs              | checkbox      | enables Unix privileges supported by OSX 10.5 and higher; do not enable if the network contains Mac OS X    |
|                              |               | 10.4 clients or lower as they do not support these                                                          |
|                              |               |                                                                                                             |
+------------------------------+---------------+-------------------------------------------------------------------------------------------------------------+
| Default file permission      | checkboxes    | only works with Unix ACLs; new files created on the share are set with the selected permissions             |
|                              |               |                                                                                                             |
+------------------------------+---------------+-------------------------------------------------------------------------------------------------------------+
| Default directory permission | checkboxes    | only works with Unix ACLs; new directories created on the share are set with the selected permissions       |
|                              |               |                                                                                                             |
+------------------------------+---------------+-------------------------------------------------------------------------------------------------------------+
| Default umask                | integer       | umask for newly created files, default is *000* (anyone can read, write, and execute)                       |
|                              |               |                                                                                                             |
+------------------------------+---------------+-------------------------------------------------------------------------------------------------------------+


Connecting to AFP Shares As Guest
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

AFP supports guest logins, meaning that all of your Mac OS X users can access the AFP share without requiring their user accounts to first be created on or
imported into the the TrueNAS® system.

.. note:: if you create a guest share as well a share that requires authentication, AFP will only map users who login as guest to the guest share. This means
   that if a user logs in to the share that requires authentication, the permissions on the guest share may prevent that user from writing to the guest share.
   The only way to allow both guest and authenticated users to write to a guest share is to set the permissions on the guest share to *777* or to add the
   authenticated users to a guest group and set the permissions to *77x*.

In this configuration example, the AFP share has been configured for guest access as follows:

#.  A ZFS volume named :file:`/mnt/data` has its permissions set to the built-in *nobody* user account and
    *nobody* group.

#.  An AFP share has been created with the following attributes:

*   Name: *freenas* (this is the name that will appear to Mac OS X clients)

*   Path: :file:`/mnt/data`

*   Allow List: set to *nobody*

*   Read-write Access: set to *nobody*

#.  `Services --> AFP` has been configured as follows:

*   Server Name: *freenas*

*   Guest Access: checkbox is checked

*   *nobody* is selected in the "Guest account" drop-down menu

Once the AFP service has been started in `Services --> Control Services`, Mac OS X users can connect to the AFP share by clicking `Go --> Connect to Server`.
In the example shown in Figure 9.1b, the user has input *afp://* followed by the IP address of the TrueNAS® system.

**Figure 9.1b: Connect to Server Dialogue**

|100000000000024B000001232956E90B_png|

.. |100000000000024B000001232956E90B_png| image:: images/connect.png
    :width: 6.9252in
    :height: 3.4327in

Click the "Connect" button. Once connected, Finder will automatically open. The name of the AFP share will be displayed in the SHARED section in the left
frame and the contents of the share will be displayed in the right frame. In the example shown in Figure 9.1c, :file:`/mnt/data` has one folder named images.
The user can now copy files to and from the share.

**Figure 9.1c: Viewing the Contents of the Share From a Mac System**

|10000000000001C60000015C9803C256_png|

.. |10000000000001C60000015C9803C256_png| image:: images/macshare.png
    :width: 6.9272in
    :height: 3.6102in

To disconnect from the volume, click the "eject" button in the "Shared" sidebar.

Using Time Machine
^^^^^^^^^^^^^^^^^^

Mac OS X includes the Time Machine application which can be used to schedule automatic backups. In this configuration example, Time Machine will be configured
to backup to an AFP share on a TrueNAS® system. To configure the AFP share on the TrueNAS® system:

#.  A ZFS dataset named :file:`/mnt/data/backup_user1` with a quota of *60G* was created in `Storage --> Volumes --> Create ZFS Dataset`.

#.  A user account was created as follows:

*   Username: *user1*

*   Home Directory: :file:`/mnt/data/backup_user1`

*   the "Full Name", "E-mail", and "Password" fields were set where the "Username" and "Password" match the values for the user on the Mac OS X system

#.  An AFP share with a "Name" of *backup_user1* has been created with the following attributes:

*   Path: :file:`/mnt/data/backup_user1`

*   Allow List: set to *user1*

*   Read-write Access: set to *user1*

*   Time Machine: checkbox is checked

#.  `Services --> AFP has` been configured as follows:

*   Guest Access: checkbox is unchecked

#.  The AFP service has been started in `Services --> Control Services`.

To configure Time Machine on the Mac OS X client, go to `System Preferences --> Time Machine` which will open the screen shown in Figure 9.1d. Click "ON" and
a pop-up menu should show the TrueNAS® system as a backup option. In our example, it is listed as *backup_user1 on "freenas"*. Highlight the entry
representing the TrueNAS® system and click the "Use Backup Disk" button. A connection bar will open and will prompt for the user account's password--in this
example, the password for the *user1* account.

**Figure 9.1d: Configuring Time Machine on Mac OS X Lion**

|10000000000002A3000001C1F794EDB8_png|

.. |10000000000002A3000001C1F794EDB8_png| image:: images/tm.png
    :width: 6.9252in
    :height: 4.6055in

Time Machine will create a full backup after waiting two minutes. It will then create a one hour incremental backup for the next 24 hours, and then one backup
each day, each week and each month.
**Since the oldest backups are deleted when the ZFS dataset becomes full, make sure that the quota size you set is sufficient to hold the backups.** Note that
a default installation of Mac OS X is ~21 GB in size.

If you receive a "Time Machine could not complete the backup. The backup disk image could not be created (error 45)" error when backing up to the TrueNAS®
system, you will need to create a sparsebundle image using
`these instructions <http://forum1.netgear.com/showthread.php?t=49482>`_.

If you receive the message "Time Machine completed a verification of your backups. To improve reliability, Time Machine must create a new backup for you." and
you do not want to perform another complete backup or lose past backups, follow the instructions in this
`post <http://www.garth.org/archives/2011,08,27,169,fix-time-machine-sparsebundle-nas-based-backup-errors.html>`_. Note that this can occur after performing a
scrub as Time Machine may mistakenly believe that the sparsebundle backup is corrupt.

Unix (NFS) Shares
~~~~~~~~~~~~~~~~~

TrueNAS® supports the Network File System (NFS) for sharing volumes over a network. Once the NFS share is configured, clients use the :command:`mount`
command to mount the share. Once mounted, the share appears as just another directory on the client system. Some Linux distros require the installation of
additional software in order to mount an NFS share. On Windows systems, enable Services for NFS in the Ultimate or Enterprise editions or install an NFS
client application.

.. note:: for performance reasons, `iSCSI`_ is preferred to NFS shares when FreeNAS is installed on ESXi. If you are considering creating NFS shares on ESXi,
   read through the performance analysis at
   `Running ZFS over NFS as a VMware Store <http://blog.laspina.ca/ubiquitous/running-zfs-over-nfs-as-a-vmware-store>`_.

Configuring NFS is a multi-step process that requires you to create NFS share(s), configure NFS in `Services --> NFS`, then start NFS in `Services -->
Services`. It does not require you to create users or groups as NFS uses IP addresses to determine which systems are allowed to access the NFS share.

This section demonstrates how to create an NFS share, provides a configuration example, demonstrates how to connect to the share from various operating
systems, and provides some troubleshooting tips.

Creating NFS Shares
^^^^^^^^^^^^^^^^^^^

To create an NFS share, click Sharing --> Unix (NFS) Shares --> Add Unix (NFS) Share, shown in Figure 9.2a. Table 9.2a summarizes the options in this screen.

**Figure 9.2a: Creating an NFS Share**

|10000000000003690000025F9C6A39F9_png|

.. |10000000000003690000025F9C6A39F9_png| image:: images/nfs.png
    :width: 6.9252in
    :height: 4.7744in

Once you press the "OK" button when creating the NFS share, a pop-up menu will ask "Would you like to enable this service?" Click "Yes" and `Services -->
Control Services` will open and indicate whether or not the NFS service successfully started.

**Table 9.2a: NFS Share Options**

+-----------------------+----------------+-------------------------------------------------------------------------------------------------------------------+
| Setting               | Value          | Description                                                                                                       |
|                       |                |                                                                                                                   |
+=======================+================+===================================================================================================================+
| Comment               | string         | used to set the share name; if left empty, share name will be the list of selected Paths                          |
|                       |                |                                                                                                                   |
+-----------------------+----------------+-------------------------------------------------------------------------------------------------------------------+
| Authorized networks   | string         | space delimited list of allowed network addresses in the form *1.2.3.0/24* where the number after the slash is a  |
|                       |                | CIDR mask                                                                                                         |
|                       |                |                                                                                                                   |
+-----------------------+----------------+-------------------------------------------------------------------------------------------------------------------+
| Authorized            | string         | space delimited list of allowed IP addresses or hostnames                                                         |
| IP addresses or hosts |                |                                                                                                                   |
|                       |                |                                                                                                                   |
+-----------------------+----------------+-------------------------------------------------------------------------------------------------------------------+
| All directories       | checkbox       | if checked, the client can mount any subdirectory within the "Path"                                               |
|                       |                |                                                                                                                   |
+-----------------------+----------------+-------------------------------------------------------------------------------------------------------------------+
| Read only             | checkbox       | prohibits writing to the share                                                                                    |
|                       |                |                                                                                                                   |
+-----------------------+----------------+-------------------------------------------------------------------------------------------------------------------+
| Quiet                 | checkbox       | inhibits some syslog diagnostics which can be useful to avoid some annoying error messages; see                   |
|                       |                | `exports(5) <http://www.freebsd.org/cgi/man.cgi?query=exports>`_                                                  |
|                       |                | for examples                                                                                                      |
|                       |                |                                                                                                                   |
+-----------------------+----------------+-------------------------------------------------------------------------------------------------------------------+
| Maproot User          | drop-down menu | if a user is selected, the *root* user is limited to that user's permissions                                      |
|                       |                |                                                                                                                   |
+-----------------------+----------------+-------------------------------------------------------------------------------------------------------------------+
| Maproot Group         | drop-down menu | if a group is selected, the *root* user will also be limited to that group's permissions                          |
|                       |                |                                                                                                                   |
+-----------------------+----------------+-------------------------------------------------------------------------------------------------------------------+
| Mapall User           | drop-down menu | the specified user's permissions are used by all clients                                                          |
|                       |                |                                                                                                                   |
+-----------------------+----------------+-------------------------------------------------------------------------------------------------------------------+
| Mapall Group          | drop-down menu | the specified group's permission are used by all clients                                                          |
|                       |                |                                                                                                                   |
+-----------------------+----------------+-------------------------------------------------------------------------------------------------------------------+
| Path                  | browse button  | browse to the volume/dataset/directory to share; click "Add extra path" to select multiple paths                  |
|                       |                |                                                                                                                   |
+-----------------------+----------------+-------------------------------------------------------------------------------------------------------------------+


When creating the NFS share, keep the following points in mind:

#.  The "Maproot" and "Mapall" options are exclusive, meaning you can only use one or the other--the GUI will not let you use both. The "Mapall" options
    supersede the "Maproot" options. If you only wish to restrict the *root* user's permissions, set the "Maproot" option. If you wish to restrict the
    permissions of all users, set the "Mapall" option.

#.  Each volume or dataset is considered to be its own filesystem and NFS is not able to cross filesystem boundaries.

#.  The network or host must be unique per share and per filesystem or directory.

#.  The "All directories" option can only be used once per share per filesystem.

To better understand these restrictions, consider the following scenario where there are:

*   2 networks named *10.0.0.0/8* and
    *20.0.0.0/8*

*   a ZFS volume named :file:`volume1` with 2 datasets named :file:`dataset1` and :file:`dataset2`

*   :file:`dataset1` has a directory named :file:`directory1`

Because of restriction #3, you will receive an error if you try to create one NFS share as follows:

*   Authorized networks: *10.0.0.0/8 20.0.0.0/8*

*   Path: :file:`/mnt/volume1/dataset1` and :file:`/mnt/volume1/dataset1/directory1`

Instead, you should select the "Path" of :file:`/mnt/volume1/dataset1` and check the "All directories" box.

However, you could restrict that directory to one of the networks by creating two shares as follows.

First NFS share:

*   Authorized networks: *10.0.0.0/8*

*   Path: :file:`/mnt/volume1/dataset1`

Second NFS share:

*   Authorized networks: *20.0.0.0/8 *

*   Path: :file:`/mnt/volume1/dataset1/directory1`

Note that this requires the creation of two shares as it can not be accomplished in one share.

Sample NFS Share Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default the "Mapall" options shown in Figure 7.2a show as *N/A*. This means that when a user connects to the NFS share, they connect with the permissions
associated with their user account. This is a security risk if a user is able to connect as *root* as they will have complete access to the share.

A better scenario is to do the following:

#.  Specify the built-in *nobody* account to be used for NFS access.

#.  In the permissions of the volume/dataset that is being shared, change the owner and group to *nobody* and set the permissions according to your
    specifications.

#.  Select *nobody* in the "Mapall User" and "Mapall Group" drop-down menus for the share.

With this configuration, it does not matter which user account connects to the NFS share, as it will be mapped to the *nobody* user account and will only have
the permissions that you specified on the volume/dataset. For example, even if the *root* user is able to connect, it will not gain
*root* access to the share.

Connecting to the NFS Share
^^^^^^^^^^^^^^^^^^^^^^^^^^^

In the following examples, an NFS share on a TrueNAS® system with the IP address of *192.168.2.2* has been configured as follows:

#.  A ZFS volume named :file:`/mnt/data` has its permissions set to the *nobody* user account and the
    *nobody* group.

#.  A NFS share has been created with the following attributes:

*   Path: :file:`/mnt/data`

*   Authorized Network: *192.168.2.0/24*

*   "MapAll User" and "MapAll Group" are both set to *nobody*

*   the "All Directories" checkbox has been checked

From BSD or Linux Clients
"""""""""""""""""""""""""

To make this share accessible on a BSD or a Linux system, run the following command as the superuser (or with :command:`sudo`) from the client system. Repeat
on each client that needs access to the NFS share::

 mount -t nfs 192.168.2.2:/mnt/data /mnt

The :command:`mount` command uses the following options:

*   **-t nfs:** specifies the type of share.

*   **192.168.2.2:** replace with the IP address of the TrueNAS® system

*   **/mnt/data:** replace with the name of the NFS share

*   **/mnt:** a mount point on the client system. This must be an existing,
    **empty** directory. The data in the NFS share will be made available to the client in this directory.

The :command:`mount` command should return to the command prompt without any error messages, indicating that the share was successfully mounted.

Once mounted, this configuration allows users on the client system to copy files to and from :file:`/mnt` (the mount point) and all files will be owned by
*nobody:nobody*. Any changes to :file:`/mnt` will be saved to the TrueNAS® system's :file:`/mnt/data` volume.

Should you wish to make any changes to the NFS share's settings or wish to make the share inaccessible, first unmount the share on the client as the
superuser::

 umount /mnt

From Microsoft Clients
""""""""""""""""""""""

Windows systems can connect to NFS shares using Services for NFS (refer to the documentation for your version of Windows for instructions on how to find,
activate, and use this service) or a third-party NFS client. Connecting to NFS shares is often faster than connecting to CIFS shares due to the
`single-threaded limitation <http://www.samba.org/samba/docs/man/Samba-Developers-Guide/architecture.html>`_ of Samba.

Instructions for connecting from an Enterprise version of Windows 7 can be found at
`Mount Linux NFS Share on Windows 7 <http://www.hackourlife.com/mount-linux-nfs-share-on-windows-7/>`_.

`Nekodrive <http://code.google.com/p/nekodrive/downloads/list>`_
provides an open source graphical NFS client. To use this client, you will need to install the following on the Windows system:

*   `7zip <http://www.7-zip.org/>`_ to extract the Nekodrive download files

*   NFSClient and NFSLibrary from the Nekodrive download page; once downloaded, extract these files using 7zip

*   `.NET Framework 4.0 <http://www.microsoft.com/download/en/details.aspx?id=17851>`_

Once everything is installed, run the NFSClient executable to start the GUI client. In the example shown in Figure 9.2b, the user has connected to the example
:file:`/mnt/data` share of the TrueNAS® system at *192.168.2.2*.

.. note:: Nekodrive does not support Explorer drive mapping via NFS. If you need this functionality,
   `try this utility <http://www.citi.umich.edu/projects/nfsv4/windows/readme.html>`_ instead.

**Figure 9.2b: Using the Nekodrive NFSClient from Windows 7 Home Edition**

|nekodrive.png|


From Mac OS X Clients
"""""""""""""""""""""

To mount the NFS volume from a Mac OS X client, click on Go --> Connect to Server. In the Server Address field, input *nfs://* followed by the IP address of
the TrueNAS® system and the name of the volume/dataset being shared by NFS. The example shown in Figure 9.2c continues with our example of
*192.168.2.2:/mnt/data*.

Once connected, Finder will automatically open. The IP address of the TrueNAS® system will be displayed in the SHARED section in the left frame and the
contents of the share will be displayed in the right frame. In the example shown in Figure 9.2d, :file:`/mnt/data` has one folder named :file:`images`. The
user can now copy files to and from the share.

**Figure 9.2c: Mounting the NFS Share from Mac OS X**

|100000000000024D0000012FE1DE1BD5_png|

.. |100000000000024D0000012FE1DE1BD5_png| image:: images/macshare.png
    :width: 6.9252in
    :height: 3.5618in

**Figure 9.2d: Viewing the NFS Share in Finder**

|10000000000001B9000001650B2A66FA_png|

.. |10000000000001B9000001650B2A66FA_png| image:: images/finder.png
    :width: 6.2193in
    :height: 4.5102in

Troubleshooting
^^^^^^^^^^^^^^^

Some NFS clients do not support the NLM (Network Lock Manager) protocol used by NFS. You will know that this is the case if the client receives an error that
all or part of the file may be locked when a file transfer is attempted. To resolve this error, add the option **-o nolock** when running the :file:`mount`
command on the client in order to allow write access to the NFS share.

If you receive an error about a "time out giving up" when trying to mount the share from a Linux system, make sure that the portmapper service is running on
the Linux client and start it if it is not. If portmapper is running and you still receive timeouts, force it to use TCP by including **-o tcp** in your
:file:`mount` command.

If you receive an error "RPC: Program not registered", upgrade to the latest version of TrueNAS® and restart the NFS service after the upgrade in order to
clear the NFS cache.

If your clients are receiving "reverse DNS" or errors, add an entry for the IP address of the TrueNAS® system in the "Host name database" field of `Network
--> Global Configuration`.

If the client receives timeout errors when trying to mount the share, add the IP address and hostname of the client to the "Host name data base" field of
`Network --> Global Configuration`.

Windows (CIFS) Shares
~~~~~~~~~~~~~~~~~~~~~

TrueNAS® uses
`Samba <http://samba.org/>`_
to share volumes using Microsoft's CIFS protocol. CIFS is built into the Windows and Mac OS X operating systems and most Linux and BSD systems pre-install the
Samba client which provides support for CIFS. If your distro did not, install the Samba client using your distro's software repository.

Configuring CIFS shares is a multi-step process that requires you to set permissions, create CIFS share(s), configure the CIFS service in `Services --> CIFS`,
then enable the CIFS service in `Services --> Control Services`. If your Windows network has a Windows server running Active Directory, you will also need to
configure the Active Directory service in `Services --> Directory Services --> Active Directory`. Depending upon your authentication requirements, you may
need to create or import users and groups.

This section will demonstrate some common configuration scenarios:

*   If you would like an overview of the configurable parameters, see `Creating CIFS Shares`_.

*   If you would like an example of how to configure access that does not require authentication, see `Configuring Anonymous Access`_.

*   If you would like each user to authenticate before accessing the share, see `Configuring Local User Access`_.

*   If you would like to use Shadow Copies, see `Configuring Shadow Copies`_.

*   If you are having problems accessing your CIFS share, see `Troubleshooting Tips`_.

Creating CIFS Shares
^^^^^^^^^^^^^^^^^^^^

Figure 9.3a shows the configuration screen that appears when you click `Sharing --> Windows (CIFS Shares) --> Add Windows (CIFS) Share`. Some settings are
only available in "Advanced Mode". To see these settings, either click the "Advanced Mode" button or configure the system to always display these settings by
checking the box "Show advanced fields by default" in `System --> Settings --> Advanced`.

Table 9.3a summarizes the options when creating a CIFS share.

`smb.conf(5) <http://www.sloop.net/smb.conf.html>`_
provides more details for each configurable option. Once you press the "OK" button when creating the CIFS share, a pop-up menu will ask "Would you like to
enable this service?" Click "Yes" and `Services --> Control Services` will open and indicate whether or not the CIFS service successfully started.

**Figure 9.3a: Adding a CIFS Share**

|100000000000030500000232522600DC_png|

.. |100000000000030500000232522600DC_png| image:: images/cifs.png
    :width: 6.4957in
    :height: 4.6835in

**Table 9.3a: Options for a CIFS Share**

+------------------------------+---------------+------------------------------------------------------------------------------------------------------------+
| Setting                      | Value         | Description                                                                                                |
|                              |               |                                                                                                            |
+==============================+===============+============================================================================================================+
| Name                         | string        | mandatory; name of share                                                                                   |
|                              |               |                                                                                                            |
+------------------------------+---------------+------------------------------------------------------------------------------------------------------------+
| Comment                      | string        | optional description                                                                                       |
|                              |               |                                                                                                            |
+------------------------------+---------------+------------------------------------------------------------------------------------------------------------+
| Path                         | browse button | select volume/dataset/directory to share                                                                   |
|                              |               |                                                                                                            |
+------------------------------+---------------+------------------------------------------------------------------------------------------------------------+
| Apply Default Permissions    | checkbox      | sets the ACLs to allow read/write for owner/group and read-only for others; should only be unchecked when  |
|                              |               | creating a share on a system that already has custom ACLs set                                              |
|                              |               |                                                                                                            |
+------------------------------+---------------+------------------------------------------------------------------------------------------------------------+
| Export Read Only             | checkbox      | prohibits write access to the share                                                                        |
|                              |               |                                                                                                            |
+------------------------------+---------------+------------------------------------------------------------------------------------------------------------+
| Browsable to Network Clients | checkbox      | enables Windows clients to browse the shared directory using Windows Explorer                              |
|                              |               |                                                                                                            |
+------------------------------+---------------+------------------------------------------------------------------------------------------------------------+
| Export Recycle Bin           | checkbox      | deleted files are instead moved to a hidden :file:`.recycle` directory in the root folder of the share     |
|                              |               |                                                                                                            |
+------------------------------+---------------+------------------------------------------------------------------------------------------------------------+
| Show Hidden Files            | checkbox      | if enabled, will display filenames that begin with a dot (Unix hidden files)                               |
|                              |               |                                                                                                            |
+------------------------------+---------------+------------------------------------------------------------------------------------------------------------+
| Allow Guest Access           | checkbox      | if checked, no password is required to connect to the share and all users share the permissions of the     |
|                              |               | guest user defined in `Services --> CIFS`                                                                  |
|                              |               |                                                                                                            |
+------------------------------+---------------+------------------------------------------------------------------------------------------------------------+
| Only Allow Guest Access      | checkbox      | requires "Allow guest access" to also be checked; forces guest access for all connections                  |
|                              |               |                                                                                                            |
+------------------------------+---------------+------------------------------------------------------------------------------------------------------------+
| Hosts Allow                  | string        | only available in "Advanced Mode"; comma, space, or tab delimited list of allowed hostnames or IP          |
|                              |               | addresses; see NOTE below                                                                                  |
|                              |               |                                                                                                            |
+------------------------------+---------------+------------------------------------------------------------------------------------------------------------+
| Hosts Deny                   | string        | only available in "Advanced Mode";  comma, space, or tab delimited list of denied hostnames or IP          |
|                              |               | addresses; allowed hosts take precedence so can use *ALL* in this field and specify allowed hosts in       |
|                              |               | *Hosts Allow*; see NOTE below                                                                              |
|                              |               |                                                                                                            |
+------------------------------+---------------+------------------------------------------------------------------------------------------------------------+
| Auxiliary Parameters         | string        | only available in "Advanced Mode"; add additional [share]                                                  |
|                              |               | `smb.conf <http://www.sloop.net/smb.conf.html>`_                                                           |
|                              |               | parameters not covered by other option fields                                                              |
|                              |               |                                                                                                            |
+------------------------------+---------------+------------------------------------------------------------------------------------------------------------+

.. note:: hostname lookups add some time to accessing the CIFS share. If you only use IP addresses, uncheck the "Hostnames lookups" box in `Services -->
   CIFS`.

Configuring Anonymous Access
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To share a volume without requiring users to input a password, configure anonymous CIFS sharing. This type of share can be configured as follows:

#.  **Create a guest user account to be used for anonymous access** in `Account --> Users --> Add User` with the following attributes:

*   Username: *guest*

*   Home Directory: browse to the volume to be shared

*   check the "Disable logins" box

#.  **Associate the guest account with the volume** in `Storage --> Volumes`. Expand the volume's name then click "Change Permissions". Select *guest*
    as the "Owner(user)" and "Owner(group)" and check that the permissions are appropriate for the share. If non-Windows systems will be accessing the CIFS
    share, leave the type of permissions as Unix. Only change the type of permissions to Windows if the share is **only** accessed by Windows systems.

#.  **Create a CIFS share** in `Sharing --> Windows (CIFS) Shares --> Add Windows (CIFS) Share` with the following attributes:

*   Name: *freenas*

*   Path: browse to the volume to be shared

*   check the boxes "Allow Guest Access" and "Only Allow Guest Access"

*   Hosts Allow: add the addresses which are allowed to connect to the share; acceptable formats are the network or subnet address with CIDR mask (e.g.
    *192.168.2.0/24* or
    *192.168.2.32/27*) or specific host IP addresses, one address per line

#.  **Configure the CIFS service** in `Services --> CIFS` with the following attributes:

*   Guest Account: *guest*

*   check the boxes boxes "Allow Empty Password" and "Enable Home Directories"

*   Home Directories: browse to the volume to be shared

#.  **Start the CIFS service** in `Services --> Control Services`. Click the click the red "OFF" button next to CIFS. After a second or so, it will change to
    a blue ON, indicating that the service has been enabled.

#.  **Test the share.**

To test the share from a Windows system, open Explorer, click on Network and you should see an icon named *FREENAS*. Since anonymous access has been
configured, you should not be prompted for a username or password in order to see the share. An example is seen in Figure 9.3b.

**Figure 9.3b: Accessing the CIFS Share from a Windows Computer**

|100002010000031D000002804075756D_png|

.. |100002010000031D000002804075756D_png| image:: images/windows.png
    :width: 6.4673in
    :height: 4.4256in

If you click on the *FREENAS* icon, you can view the contents of the CIFS share.

To prevent Windows Explorer from hanging when accessing the share, map the share as a network drive. To do this, right-click the share and select "Map network
drive..." as seen in Figure 9.3c.

**Figure 9.3c: Mapping the Share as a Network Drive**

|100002010000031E0000027D2C5F8621_png|

.. |100002010000031E0000027D2C5F8621_png| image:: images/map1.png
    :width: 6.2945in
    :height: 3.6819in

Choose a drive letter from the drop-down menu and click the Finish button as shown in Figure 9.3d.

**Figure 9.3d: Selecting the Network Drive Letter**

|1000000000000319000002766C465264_jpg|

.. |1000000000000319000002766C465264_jpg| image:: images/map2.jpg
    :width: 6.9252in
    :height: 5.5016in

Configuring Local User Access
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you would like each user to authenticate before accessing the CIFS share, configure the share as follows:

#.  **If you are not using Active Directory or LDAP, create a user account for each user** in `Account --> Users --> Add User` with the following attributes:

*   Username and Password: matches the username and password on the client system

*   Home Directory: browse to the volume to be shared

*   Repeat this process to create a user account for every user that will need access to the CIFS share

#.  If you are not using Active Directory or LDAP, create a group in `Account --> Groups --> Add Group`. Once the group is created, click its Members button
    and add the user accounts that you created in step 1.

#.  **Give the group permission to the volume** in `Storage --> View Volumes`. When setting the permissions:

*   set "Owner(user)" to *nobody*

*   set the "Owner(group)" to the one you created in Step 2

*   Mode: check the write checkbox for the "Group" as it is unchecked by default

#.  **Create a CIFS share** in `Sharing --> CIFS Shares --> Add CIFS Share` with the following attributes:

*   Name: input the name of the share

*   Path: browse to the volume to be shared

*   keep the "Browsable to Network Clients" box checked

.. note:: be careful about unchecking the "Browsable to Network Clients" box. When this box is checked (the default), other users will see the names of every
   share that exists using Windows Explorer, but they will receive a permissions denied error message if they try to access someone else's share. If this box
   is unchecked, even the owner of the share won't see it or be able to create a drive mapping for the share in Windows Explorer. However, they can still
   access the share from the command line. Unchecking this option provides limited security and is not a substitute for proper permissions and password
   control.

#.  **Configure the CIFS service in Services --> CIFS**. if you are not using Active Directory or LDAP, set "Workgroup" to the name being used on the Windows
    network; unless it has been changed, the default Windows workgroup name is *WORKGROUP*

#.  **Start the CIFS service** in `Services --> Control Services`. Click the click the red OFF button next to CIFS. After a second or so, it will change to a
    blue ON, indicating that the service has been enabled.

#.  **Test the share.**

To test the share from a Windows system, open Explorer and click on Network. For this configuration example, a system named *FREENAS* should appear with a
share named *backups*. If you click on
*backups*, a Windows Security pop-up screen should prompt for the user's username and password. Once authenticated, the user can copy data to and from the
CIFS share.

.. note:: since the share is group writable, any authenticated user can change the data in the share. If you wish to setup shares where a group of users have access to some folders but only individuals have access to other folders (where all these folders reside on the same volume), create these directories and set their permissions using
`Shell <#1.9.2.Shell|outline>`_
. Instructions for doing so can be found at the forum post
`Set Permission to allow users to share a common folder & have private personal folder <http://forums.freenas.org/showthread.php?1122-Set-Permission-to-allow-users-to-share-a-common-folder-amp-have-private-personal-folder>`_
.

Configuring Shadow Copies
^^^^^^^^^^^^^^^^^^^^^^^^^

`Shadow Copies <http://en.wikipedia.org/wiki/Shadow_copy>`_
, also known as the Volume Shadow Copy Service (VSS) or Previous Versions, is a Microsoft service for creating volume snapshots. Shadow copies allow you to
easily restore previous versions of files from within Windows Explorer. Shadow Copy support is built into Vista and Windows 7. Windows XP or 2000 users need
to install the
`Shadow Copy client <http://www.microsoft.com/download/en/details.aspx?displaylang=en&id=16220>`_.

When you create a periodic snapshot task on a ZFS volume that is configured as a CIFS share in TrueNAS®, it is automatically configured to support shadow
copies.


Prerequisites
"""""""""""""

Before using shadow copies with TrueNAS®, be aware of the following caveats:

*   if the Windows system is not fully patched to the latest service pack, Shadow Copies may not work. If you are unable to see any previous versions of files
    to restore, use Windows Update to make sure that the system is fully up-to-date.

*   shadow copy support only works for ZFS pools or datasets. This means that the CIFS share must be configured on a volume or dataset, not on a directory.

*   since directories can not be shadow copied at this time, if you configure "Enable home directories" on the CIFS service, any data stored in the user's
    home directory will not be shadow copied.

*   shadow copies will not work with a manual snapshot, you must create a periodic snapshot task for the pool or dataset being shared by CIFS or a recursive
    task for a parent dataset. If multiple snapshot tasks are created for the same pool/dataset being shared by CIFS, shadow copies will only work on the last
    executed task at the time the CIFS service started.

*   the periodic snapshot task should be created and at least one snapshot should exist **before** creating the CIFS share. If you created the CIFS share
    first, restart the CIFS service in `Services --> Control Services`.

*   appropriate permissions must be configured on the volume/dataset being shared by CIFS.

*   users can not delete shadow copies on the Windows system due to the way Samba works. Instead, the administrator can remove snapshots from the TrueNAS®
    administrative GUI. The only way to disable shadow copies completely is to remove the periodic snapshot task and delete all snapshots associated with the
    CIFS share.

Configuration Example
"""""""""""""""""""""

In this example, a Windows 7 computer has two users: *user1* and
*user2*. To configure TrueNAS® to provide shadow copy support:


#.  For the ZFS volume named :file:`/mnt/data`, create two ZFS datasets in `Storage --> Volumes --> /mnt/data --> Create ZFS Dataset`. The first dataset is
    named :file:`/mnt/data/user1` and the second dataset is named :file:`/mnt/data/user2`.

#.  If you are not using Active Directory or LDAP, create two users, *user1* and
    *user2* in `Account --> Users --> Add User`. Each user has the following attributes:

*   Username and Password: matches that user's username and password on the Windows system

*   Home Directory: browse to the dataset created for that user

#.  Set the permissions on :file:`/mnt/data/user1` so that the "Owner(user)" and "Owner(group)" is *user1*. Set the permissions on :file:`/mnt/data/user2` so
    that the "Owner(user)" and "Owner(group)" is *user2*. For each dataset's permissions, tighten the "Mode" so that "Other" can not read or execute the
    information on the dataset.

#.  Create two periodic snapshot tasks in `Storage --> Periodic Snapshot Tasks --> Add Periodic Snapshot`, one for each dataset. Alternatively, you can create
    one periodic snapshot task for the entire :file:`data` volume. 
    **Before continuing to the next step,** confirm that at least one snapshot for each dataset is displayed in the "ZFS Snapshots" tab. When creating your
    snapshots, keep in mind how often your users need to access modified files and during which days and time of day they are likely to make changes.

#.  Create two CIFS shares in `Sharing --> Windows (CIFS) Shares --> Add Windows (CIFS) Share`. The first CIFS share is named *user1* and has a "Path" of
    :file:`/mnt/data/user1`; the second CIFS share is named *user2* and has a "Path" of :file:`/mnt/data/user2`. When creating the first share, click the "No"
    button when the pop-up button asks if the CIFS service should be started. When the last share is created, click the "Yes" button when the pop-up button
    prompts to start the CIFS service. Verify that the CIFS service is set to "ON" in `Services --> Control Services`.

#.  From a Windows system, login as *user1* and open `Windows Explorer --> Network --> FREENAS`. Two shares should appear, named
    *user1* and
    *user2*. Due to the permissions on the datasets,
    *user1* should receive an error if they click on the
    *user2* share. Due to the permissions on the datasets,
    *user1* should be able to create, add, and delete files and folders from the
    *user1* share.

Figure 9.3e provides an example of using shadow copies while logged in as *user1*. In this example, the user right-clicked
*modified file* and selected "Restore previous versions" from the menu. This particular file has three versions: the current version, plus two previous
versions stored on the TrueNAS® system. The user can choose to open one of the previous versions, copy a previous version to the current folder, or restore
one of the previous versions, which will overwrite the existing file on the Windows system.

**Figure 9.3e: Viewing Previous Versions within Explorer**

|10000201000002FE0000028C18A1102B_png|

.. |10000201000002FE0000028C18A1102B_png| image:: images/explorer.png
    :width: 6.9252in
    :height: 5.8945in