.. index:: Tasks
.. _Tasks:

Tasks
=====

The Tasks section of the administrative GUI can be used to configure the following repetitive tasks:

* :ref:`Cron Jobs`: allows you to schedule a command or script to automatically execute at a specified time

* :ref:`Init/Shutdown Scripts`: used to configure a command or script to automatically execute during system startup or shutdown

* :ref:`Rsync Tasks`: allows you to schedule data synchronization to another system

* :ref:`S.M.A.R.T. Tests`: allows you to schedule how often disk tests occur

Each of these tasks is described in more detail in this section.

.. index:: Cron Jobs
.. _Cron Jobs:

Cron Jobs
---------

`cron(8) <http://www.freebsd.org/cgi/man.cgi?query=cron>`_
is a daemon that runs a command or script on a regular schedule as a specified user. Typically, the user who wishes to schedule a task manually creates a
`crontab(5) <http://www.freebsd.org/cgi/man.cgi?query=crontab&sektion=5>`_
using syntax that can be perplexing to new Unix users. The FreeNAS® GUI makes it easy to schedule when you would like the task to occur.

.. note:: due to a limitation in FreeBSD, users with account names that contain spaces or exceed 17 characters are unable to create cron jobs.

Figure 6.1a shows the screen that opens when you click :menuselection:`Tasks --> Cron Jobs --> Add Cron Job`.

**Figure 6.1a: Creating a Cron Job**

|cron.png|

.. |cron.png| image:: images/cron.png
    :width: 9.3in
    :height: 4.4in

Table 6.1a summarizes the configurable options when creating a cron job.

**Table 6.1a: Cron Job Options**

+-------------------+-----------------------------+---------------------------------------------------------------------------------------------------------+
| **Setting**       | **Value**                   | **Description**                                                                                         |
|                   |                             |                                                                                                         |
+===================+=============================+=========================================================================================================+
| User              | drop-down menu              | make sure the selected user has permission to run the specified command or script                       |
|                   |                             |                                                                                                         |
+-------------------+-----------------------------+---------------------------------------------------------------------------------------------------------+
| Command           | string                      | the **full path** to the command or script to be run; if it is a script, test it at the command line    |
|                   |                             | first to make sure that it works as expected                                                            |
|                   |                             |                                                                                                         |
+-------------------+-----------------------------+---------------------------------------------------------------------------------------------------------+
| Short description | string                      | optional                                                                                                |
|                   |                             |                                                                                                         |
+-------------------+-----------------------------+---------------------------------------------------------------------------------------------------------+
| Minute            | slider or minute selections | if use the slider, cron job occurs every N minutes; if use minute selections, cron job occurs at the    |
|                   |                             | highlighted minutes                                                                                     |
|                   |                             |                                                                                                         |
+-------------------+-----------------------------+---------------------------------------------------------------------------------------------------------+
| Hour              | slider or hour selections   | if use the slider, cron job occurs every N hours; if use hour selections, cron job occurs at the        |
|                   |                             | highlighted hours                                                                                       |
|                   |                             |                                                                                                         |
+-------------------+-----------------------------+---------------------------------------------------------------------------------------------------------+
| Day of month      | slider or month selections  | if use the slider, cron job occurs every N days; if use day selections, cron job occurs on the          |
|                   |                             | highlighted days each month                                                                             |
|                   |                             |                                                                                                         |
+-------------------+-----------------------------+---------------------------------------------------------------------------------------------------------+
| Month             | checkboxes                  | cron job occurs on the selected months                                                                  |
|                   |                             |                                                                                                         |
+-------------------+-----------------------------+---------------------------------------------------------------------------------------------------------+
| Day of week       | checkboxes                  | cron job occurs on the selected days                                                                    |
|                   |                             |                                                                                                         |
+-------------------+-----------------------------+---------------------------------------------------------------------------------------------------------+
| Redirect Stdout   | checkbox                    | disables emailing standard output to the *root* user account                                            |
|                   |                             |                                                                                                         |
+-------------------+-----------------------------+---------------------------------------------------------------------------------------------------------+
| Redirect Stderr   | checkbox                    | disables emailing errors to the *root* user account                                                     |
|                   |                             |                                                                                                         |
+-------------------+-----------------------------+---------------------------------------------------------------------------------------------------------+
| Enabled           | checkbox                    | uncheck if you would like to disable the cron job without deleting it                                   |
|                   |                             |                                                                                                         |
+-------------------+-----------------------------+---------------------------------------------------------------------------------------------------------+

Created cron jobs will be listed in "View Cron Jobs". If you highlight the entry for a cron job, buttons will be displayed to "Edit", "Delete", or "Run Now".

.. _Init/Shutdown Scripts:

Init/Shutdown Scripts
---------------------

FreeNAS® provides the ability to schedule commands or scripts to run at system startup or shutdown.

Figure 6.2a shows the screen that opens when you click :menuselection:`Tasks --> Init/Shutdown Scripts --> Add Init/Shutdown Script`. Table 6.2a summarizes
the available options.

When scheduling a command, make sure that the command is in your path or give the full path to the command. One way to test the path is to type
:command:`which command_name`. If the command is not found, it is not in your path.

When scheduling a script, make sure that the script is executable and has been fully tested to ensure that it achieves the desired results.

**Figure 6.2a: Add an Init/Shutdown Script**

|init.png|

.. |init.png| image:: images/init.png
    :width: 4.6in
    :height: 2.6in

**Table 6.2a: Options When Adding an Init/Shutdown Script**

+-------------+----------------+-----------------------------------------------------------------------------------+
| **Setting** | **Value**      | **Description**                                                                   |
|             |                |                                                                                   |
|             |                |                                                                                   |
+=============+================+===================================================================================+
| Type        | drop-down menu | select from *Command* (for an executable) or                                      |
|             |                | *Script* (for an executable script)                                               |
|             |                |                                                                                   |
+-------------+----------------+-----------------------------------------------------------------------------------+
| Command     | string         | if *Command* is selected, input the command plus any desired options; if          |
|             |                | *Script* is selected, browse to the location of the script                        |
|             |                |                                                                                   |
+-------------+----------------+-----------------------------------------------------------------------------------+
| When        | drop-down menu | select when the command/script will run; choices are *Pre Init*                   |
|             |                | (very early in boot process before filesystems are mounted), *Post Init*          |
|             |                | (towards end of boot process before FreeNAS services are started), or *Shutdown*  |
|             |                |                                                                                   |
+-------------+----------------+-----------------------------------------------------------------------------------+

.. index:: Rsync Tasks
.. _Rsync Tasks:

Rsync Tasks
-----------

`Rsync <http://www.samba.org/ftp/rsync/rsync.html>`_
is a utility that automatically copies specified data from one system to another over a network. Once the initial data is copied, rsync reduces the amount of
data sent over the network by sending only the differences between the source and destination files. Rsync can be used for backups, mirroring data on multiple
systems, or for copying files between systems.

To configure rsync, you need to configure both ends of the connection:

* **the rsync server:** this system pulls (receives) the data. This system is referred to as *PULL* in the configuration examples.

* **the rsync client:** this system pushes (sends) the data. This system is referred to as *PUSH* in the configuration examples.

FreeNAS® can be configured as either an rsync client or an rsync server. The opposite end of the connection can be another FreeNAS® system or any other
system running rsync. In FreeNAS® terminology, an rysnc task defines which data is synchronized between the two systems. If you are synchronizing data
between two FreeNAS® systems, create the rsync task on the rsync client.

FreeNAS® supports two modes of rsync operation:

* **rsync module mode:** exports a directory tree, and its configured settings, as a symbolic name over an unencrypted connection. This mode requires that
  at least one module be defined on the rsync server. It can be defined in the FreeNAS® GUI under :menuselection:`Services --> Rsync --> Rsync Modules`. In
  other operating systems, the module is defined in
  `rsyncd.conf(5) <http://www.samba.org/ftp/rsync/rsyncd.conf.html>`_.

* **rsync over SSH:** synchronizes over an encrypted connection. Requires the configuration of SSH user and host public keys.

This section summarizes the options when creating an Rsync Task. It then provides a configuration example between two FreeNAS® systems for each mode of rsync
operation.

.. note:: if there is a firewall between the two systems or if the other system has a built-in firewall, make sure that TCP port 873 is allowed.

Figure 6.3a shows the screen that appears when you click :menuselection:`Tasks --> Rsync Tasks --> Add Rsync Task`. Table 6.3a summarizes the options that
can be configured when creating an rsync task.

**Figure 6.3a: Adding an Rsync Task**

|rsync1a.png|

.. |rsync1a.png| image:: images/rsync1a.png
    :width: 11.1in
    :height: 4.4in

**Table 6.3a: Rsync Configuration Options**

+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| **Setting**                      | **Value**                   | **Description**                                                                           |
|                                  |                             |                                                                                           |
|                                  |                             |                                                                                           |
+==================================+=============================+===========================================================================================+
| Path                             | browse button               | browse to the path that you wish to copy; note that a path length greater than 255        |
|                                  |                             | characters will fail                                                                      |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| User                             | drop-down menu              | specified user must have permission to write to the specified directory on the remote     |
|                                  |                             | system; due to a limitation in FreeBSD, the user name can not contain spaces or exceed 17 |
|                                  |                             | characters                                                                                |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Remote Host                      | string                      | IP address or hostname of the remote system that will store the copy                      |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Remote SSH Port                  | integer                     | only available in  *Rsync over SSH* mode; allows you to specify an alternate SSH port     |
|                                  |                             | other than the default of *22*                                                            |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Rsync mode                       | drop-down menu              | choices are *Rsync module* or                                                             |
|                                  |                             | *Rsync over SSH*                                                                          |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Remote Module Name               | string                      | only appears when using *Rsync module* mode, at least one module must be defined in       |
|                                  |                             | `rsyncd.conf(5) <http://www.samba.org/ftp/rsync/rsyncd.conf.html>`_                       |
|                                  |                             | of rsync server or in the "Rsync Modules" of another                                      |
|                                  |                             | system                                                                                    |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Remote Path                      | string                      | only appears when using *Rsync over SSH* mode, input the **existing** path on the remote  |
|                                  |                             | host to sync with (e.g. */mnt/volume*); note that maximum path length is 255 characters   |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Validate Remote Path             | checkbox                    | if the "Remote Path" does not yet exist, check this box to have it automatically created  |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Direction                        | drop-down menu              | choices are *Push* or                                                                     |
|                                  |                             | *Pull*; default is to push to a remote host                                               |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Short Description                | string                      | optional                                                                                  |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Minute                           | slider or minute selections | if use the slider, sync occurs every N minutes; if use minute selections, sync occurs at  |
|                                  |                             | the highlighted minutes                                                                   |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Hour                             | slider or hour selections   | if use the slider, sync occurs every N hours; if use hour selections, sync occurs at the  |
|                                  |                             | highlighted hours                                                                         |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Day of month                     | slider or day selections    | if use the slider, sync occurs every N days; if use day selections, sync occurs on the    |
|                                  |                             | highlighted days                                                                          |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Month                            | checkboxes                  | task occurs on the selected months                                                        |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Day of week                      | checkboxes                  | task occurs on the selected days of the week                                              |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Recursive                        | checkbox                    | if checked, copy will include all subdirectories of the specified volume                  |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Times                            | checkbox                    | preserve modification times of files                                                      |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Compress                         | checkbox                    | recommended on slow connections as reduces size of data to be transmitted                 |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Archive                          | checkbox                    | equivalent to :command:`-rlptgoD` (recursive, copy symlinks as symlinks, preserve         |
|                                  |                             | permissions, preserve modification times, preserve group, preserve owner (super-user      |
|                                  |                             | only), and preserve device files (super-user only) and special files)                     |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Delete                           | checkbox                    | delete files in destination directory that don't exist in sending directory               |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Quiet                            | checkbox                    | suppresses informational messages from the remote server                                  |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Preserve permissions             | checkbox                    | preserves original file permissions; useful if User is set to *root*                      |
|                                  |                             |                                                                                           |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Preserve extended attributes     | checkbox                    | both systems must support                                                                 |
|                                  |                             | `extended attributes <http://en.wikipedia.org/wiki/Xattr>`_                               |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Delay Updates                    | checkbox                    | when checked, the temporary file from each updated file is saved to a holding directory   |
|                                  |                             | until the end of the transfer, when all transferred files are renamed into place          |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Extra options                    | string                      | `rsync(1) <http://rsync.samba.org/ftp/rsync/rsync.html>`_                                 |
|                                  |                             | options not covered by the GUI; note that if the "*" character is used, it must be        |
|                                  |                             | escaped between single quotes (e.g. '\*.txt')                                             |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+
| Enabled                          | checkbox                    | uncheck if you would like to disable the rsync task without deleting it                   |
|                                  |                             |                                                                                           |
+----------------------------------+-----------------------------+-------------------------------------------------------------------------------------------+

If the rysnc server requires password authentication, input *--password-file=/PATHTO/FILENAME* in the "Extra options" box, replacing
*/PATHTO/FILENAME* with the appropriate path to the file containing the value of the password.

Created rsync tasks will be listed in "View Rsync Tasks". If you highlight the entry for an rsync task, buttons will be displayed to "Edit", "Delete", or "Run
Now".

.. _Rsync Module Mode:

Rsync Module Mode
~~~~~~~~~~~~~~~~~

This configuration example will configure rsync module mode between the two following FreeNAS® systems:

* *192.168.2.2* has existing data in :file:`/mnt/local/images`. It will be the rsync client, meaning that an rsync task needs to be defined. It will be
  referred to as *PUSH.*

* *192.168.2.6* has an existing volume named :file:`/mnt/remote`. It will be the rsync server, meaning that it will receive the contents of
  :file:`/mnt/local/images`. An rsync module needs to be defined on this system and the rsyncd service needs to be started. It will be referred to as *PULL.*

On *PUSH*, an rsync task is defined in :menuselection:`Tasks --> Rsync Tasks --> Add Rsync Task`. In this example:

* the "Path" points to :file:`/usr/local/images`, the directory to be copied

* the "Remote Host" points to *192.168.2.6*, the IP address of the rsync server

* the "Rsync Mode" is *Rsync module*

* the "Remote Module Name" is *backups*; this will need to be defined on the rsync server

* the "Direction" is *Push*

* the rsync is scheduled to occur every 15 minutes

* the "User" is set to *root* so it has permission to write anywhere

* the "Preserve Permissions" checkbox is checked so that the original permissions are not overwritten by the *root* user

On *PULL*, an rsync module is defined in :menuselection:`Services --> Rsync Modules --> Add Rsync Module`. In this example:

* the "Module Name" is *backups*; this needs to match the setting on the rsync client

* the "Path" is :file:`/mnt/remote`; a directory called :file:`images` will be created to hold the contents of :file:`/usr/local/images`

* the "User" is set to *root* so it has permission to write anywhere

* "Hosts allow" is set to *192.168.2.2*, the IP address of the rsync client

Descriptions of the configurable options can be found in `Rsync Modules`.

To finish the configuration, start the rsync service on *PULL* in :menuselection:`Services --> Control Services`. If the rsync is successful, the contents of
:file:`/mnt/local/images/` will be mirrored to :file:`/mnt/remote/images/`.

.. _Rsync over SSH Mode:

Rsync over SSH Mode
~~~~~~~~~~~~~~~~~~~

SSH replication mode does not require the creation of an rsync module or for the rsync service to be running on the rsync server. It does require SSH to be
configured before creating the rsync task:

* a public/private key pair for the rsync user account (typically *root*) must be generated on
  *PUSH* and the public key copied to the same user account on
  *PULL*

* to mitigate the risk of man-in-the-middle attacks, the public host key of *PULL* must be copied to
  *PUSH*

* the SSH service must be running on *PULL*

To create the public/private key pair for the rsync user account, open Shell on *PUSH*. The following example generates an RSA type public/private key pair
for the *root* user. When creating the key pair, do not enter the passphrase as the key is meant to be used for an automated task.::

 ssh-keygen -t rsa
 Generating public/private rsa key pair.
 Enter file in which to save the key (/root/.ssh/id_rsa):
 Created directory '/root/.ssh'.
 Enter passphrase (empty for no passphrase):
 Enter same passphrase again:
 Your identification has been saved in /root/.ssh/id_rsa.
 Your public key has been saved in /root/.ssh/id_rsa.pub.
 The key fingerprint is:
 f5:b0:06:d1:33:e4:95:cf:04:aa:bb:6e:a4:b7:2b:df root@freenas.local
 The key's randomart image is:
 +--[ RSA 2048]----+
 |        .o. oo   |
 |         o+o. .  |
 |       . =o +    |
 |        + +   o  |
 |       S o .     |
 |       .o        |
 |      o.         |
 |    o oo         |
 |     **oE        |
 |-----------------|
 |                 |
 |-----------------|


FreeNAS® supports the following types of SSH keys: DSA, and RSA. When creating the key, specify the type you wish to use or, if you are generating the key
on another operating system, select a type of key the key generation software supports.

.. note:: if a different user account is used for the rsync task, use the :command:`su -` command after mounting the filesystem but before generating the key.
   For example, if the rsync task is configured to use the *user1* user account, use this command to become that user::

      su - user1

Next, view and copy the contents of the generated public key::

 more .ssh/id_rsa.pub
 ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC1lBEXRgw1W8y8k+lXPlVR3xsmVSjtsoyIzV/PlQPo
 SrWotUQzqILq0SmUpViAAv4Ik3T8NtxXyohKmFNbBczU6tEsVGHo/2BLjvKiSHRPHc/1DX9hofcFti4h
 dcD7Y5mvU3MAEeDClt02/xoi5xS/RLxgP0R5dNrakw958Yn001sJS9VMf528fknUmasti00qmDDcp/kO
 xT+S6DFNDBy6IYQN4heqmhTPRXqPhXqcD1G+rWr/nZK4H8Ckzy+l9RaEXMRuTyQgqJB/rsRcmJX5fApd
 DmNfwrRSxLjDvUzfywnjFHlKk/+TQIT1gg1QQaj21PJD9pnDVF0AiJrWyWnR root@freenas.local


Go to *PULL* and paste (or append) the copied key into the "SSH Public Key" field of
:menuselection:`Account --> Users --> View Users --> root --> Modify User`, or the username of the specified rsync user account. The paste for the above
example is shown in Figure 6.3b. When pasting the key, ensure that it is pasted as one long line and, if necessary, remove any extra spaces representing line
breaks.

**Figure 6.3b: Pasting the User's SSH Public Key**

|rsync2.png|

.. |rsync2.png| image:: images/rsync2.png
    :width: 6.2in
    :height: 4.5in

While on *PULL*, verify that the SSH service is running in :menuselection:`Services --> Control Services` and start it if it is not.

Next, copy the host key of *PULL* using Shell on
*PUSH*. The following command copies the RSA host key of the
*PULL* server used in our previous example. Be sure to include the double bracket
*>>* to prevent overwriting any existing entries in the :file:`known_hosts` file::

 ssh-keyscan -t rsa 192.168.2.6 >> /root/.ssh/known_hosts

.. note:: if *PUSH* is a Linux system, use the following command to copy the RSA key to the Linux system:

   ::

      cat ~/.ssh/id_rsa.pub | ssh user@192.168.2.6 'cat >> .ssh/authorized_keys'

You are now ready to create the rsync task on *PUSH*. To configure rsync SSH mode using the systems in our previous example, the configuration would be as
follows:

* the "Path" points to :file:`/mnt/local/images`, the directory to be copied

* the "Remote Host" points to *192.168.2.6*, the IP address of the rsync server

* the "Rsync Mode" is *Rsync over SSH*

* the rsync is scheduled to occur every 15 minutes

* the "User" is set to *root* so it has permission to write anywhere; the public key for this user must be generated on
  *PUSH* and copied to
  *PULL*

* the "Preserve Permissions" checkbox is checked so that the original permissions are not overwritten by the *root* user

Once you save the rsync task, the rsync will automatically occur according to your schedule. In this example, the contents of :file:`/mnt/local/images/` will
automatically appear in :file:`/mnt/remote/images/` after 15 minutes. If the content does not appear, use Shell on *PULL* to read :file:`/var/log/messages`.
If the message indicates a *\n* (newline character) in the key, remove the space in your pasted key--it will be after the character that appears just before the
*\n* in the error message.

.. index:: S.M.A.R.T. Tests
.. _S.M.A.R.T. Tests:

S.M.A.R.T. Tests
----------------

`S.M.A.R.T. <http://en.wikipedia.org/wiki/S.M.A.R.T.>`_
(Self-Monitoring, Analysis and Reporting Technology) is a monitoring system for computer hard disk drives to detect and report on various indicators of
reliability. When a failure is anticipated by S.M.A.R.T., the drive should be replaced. Most modern ATA, IDE, and SCSI-3 hard drives support S.M.A.R.T.--refer
to your drive's documentation if you are unsure.

Figure 6.4a shows the configuration screen that appears when you click :menuselection:`Tasks --> S.M.A.R.T. Tests --> Add S.M.A.R.T. Test`. The tests that
you create will be listed under "View S.M.A.R.T. Tests". After creating your tests, check the configuration in :menuselection:`Services --> S.M.A.R.T.`, then
click the slider to "ON" for the S.M.A.R.T. service in :menuselection:`Services --> Control Services`. The S.M.A.R.T. service will not start if you have not
created any volumes.

.. note:: to prevent problems, do not enable the S.M.A.R.T. service if your disks are controlled by a RAID controller as it is the job of the controller to
   monitor S.M.A.R.T. and mark drives as Predictive Failure when they trip.

**Figure 6.4a: Adding a S.M.A.R.T. Test**

|smart1.png|

.. |smart1.png| image:: images/smart1.png
    :width: 6.94in
    :height: 4.9in

Table 6.4a summarizes the configurable options when creating a S.M.A.R.T. test.

**Table 6.4a: S.M.A.R.T. Test Options**

+-------------------+---------------------------+------------------------------------------------------------------------------------------------------------+
| **Setting**       | **Value**                 | **Description**                                                                                            |
|                   |                           |                                                                                                            |
|                   |                           |                                                                                                            |
+===================+===========================+============================================================================================================+
| Disks             | list                      | highlight disk(s) to monitor                                                                               |
|                   |                           |                                                                                                            |
+-------------------+---------------------------+------------------------------------------------------------------------------------------------------------+
| Type              | drop-down menu            | select type of test to run; see                                                                            |
|                   |                           | `smartctl(8) <http://smartmontools.sourceforge.net/man/smartctl.8.html>`_                                  |
|                   |                           | for a description of each type of test (note that some test types will degrade performance or take disk(s) |
|                   |                           | offline)                                                                                                   |
|                   |                           |                                                                                                            |
+-------------------+---------------------------+------------------------------------------------------------------------------------------------------------+
| Short description | string                    | optional                                                                                                   |
|                   |                           |                                                                                                            |
+-------------------+---------------------------+------------------------------------------------------------------------------------------------------------+
| Hour              | slider or hour selections | if use the slider, test occurs every N hours; if use hour selections, test occurs at the highlighted hours |
|                   |                           |                                                                                                            |
+-------------------+---------------------------+------------------------------------------------------------------------------------------------------------+
| Day of month      | slider or day selections  | if use the slider, test occurs every N days; if use day selections, test occurs on the highlighted days    |
|                   |                           |                                                                                                            |
+-------------------+---------------------------+------------------------------------------------------------------------------------------------------------+
| Month             | checkboxes                | select the months when you wish the test to occur                                                          |
|                   |                           |                                                                                                            |
+-------------------+---------------------------+------------------------------------------------------------------------------------------------------------+
| Day of week       | checkboxes                | select the days of the week when you wish the test to occur                                                |
|                   |                           |                                                                                                            |
+-------------------+---------------------------+------------------------------------------------------------------------------------------------------------+

An example configuration is to schedule a "Short Self-Test" once a week and a "Long Self-Test" once a month. These tests should not have a performance impact,
as the disks prioritize normal I/O over the tests. If a disk fails a test, even if the overall status is "Passed", start to think about replacing that disk.

You can verify which tests will run and when by typing :command:`smartd -q showtests` within :ref:`Shell`.

You can check the results of a test from :ref:`Shell` by specifying the name of the drive. For example, to see the results for disk *ada0*,
type::

 smartctl -l selftest /dev/ada0

If you enter an email address in the "Email to report" field of :menuselection:`Services --> S.M.A.R.T.`, the system will email the specified address when a
test fails. 

