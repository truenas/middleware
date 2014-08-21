:orphan:

System
======

The System section of the administrative GUI contains the following entries:

* `Information`_: provides general FreeNAS® system information such as hostname, operating system version, platform, and uptime

* `General`_: used to general settings such as HTTPS access, the language, and the timezone

* `Advanced`_: used to configure advanced settings such as the serial console, swap, console messages, and other advanced fields

* `Email`_: used to configure the email address to receive notifications

* `System Dataset`_: used to configure the location of the system dataset

* `Tunables`_: provides a front-end for tuning in real-time and to load additional kernel modules at boot time

Each of these is described in more detail in this section.

Information
-----------

:menuselection:`System --> Information` displays general information about the FreeNAS® system. An example is seen in Figure 5.1a.

The information includes the hostname, the build version, type of CPU (platform), the amount of memory, the current system time, the system's uptime, and the
current load average.

To change the system's hostname, click its "Edit" button, type in the new hostname, and click "OK". The hostname must include the domain name. If the network
does not use a domain name add *.local* to the end of the hostname.

**Figure 5.1a: System Information Tab**

|Figure51a_png|

General
-------

:menuselection:`System --> General` is shown in Figure 5.2a.

**Figure 5.2a: General Screen**

|Figure52a_png|

Table 5.2a summarizes the settings that can be configured using the General tab:

**Table 5.2a: General Configuration Settings**

+----------------------+----------------+--------------------------------------------------------------------------------------------------------------------------------+
| Setting              | Value          | Description                                                                                                                    |
|                      |                |                                                                                                                                |
+======================+================+================================================================================================================================+
| Protocol             | drop-down menu | protocol to use when connecting to the administrative GUI from a browser; if you change the default of *HTTP* to               |
|                      |                | *HTTPS*, an unsigned certificate and RSA key will be generated and you will be logged out in order to accept the               |
|                      |                | certificate                                                                                                                    |
|                      |                |                                                                                                                                |
+----------------------+----------------+--------------------------------------------------------------------------------------------------------------------------------+
| WebGUI IPv4 Address  | drop-down menu | choose from a list of recent IP addresses to limit the one to use when accessing the administrative GUI; the                   |
|                      |                | built-in HTTP server will automatically bind to the wildcard address of *0.0.0.0* (any address) and will issue an              | 
|                      |                | alert if the specified address becomes unavailable                                                                             |
|                      |                |                                                                                                                                |
+----------------------+----------------+--------------------------------------------------------------------------------------------------------------------------------+
| WebGUI IPv6 Address  | drop-down menu | choose from a list of recent IPv6 addresses to limit the one to use when accessing the administrative GUI; the                 |
|                      |                | built-in HTTP server will automatically bind to any address and will issue an alert                                            |
|                      |                | if the specified address becomes unavailable                                                                                   |
|                      |                |                                                                                                                                |
+----------------------+----------------+--------------------------------------------------------------------------------------------------------------------------------+
| WebGUI HTTP Port     | integer        | allows you to configure a non-standard port for accessing the administrative GUI over HTTP; changing this setting              |
|                      |                | may require you to                                                                                                             |
|                      |                | `change a firefox configuration setting <http://www.redbrick.dcu.ie/%7Ed_fens/articles/Firefox:_This_Address_is_Restricted>`_  |
|                      |                |                                                                                                                                |
+----------------------+----------------+--------------------------------------------------------------------------------------------------------------------------------+
| WebGUI HTTPS Port    | integer        | allows you to configure a non-standard port for accessing the administrative GUI over HTTPS                                    |
|                      |                |                                                                                                                                |
+----------------------+----------------+--------------------------------------------------------------------------------------------------------------------------------+
| WebGUI -> HTTPS Port | checkbox       |                                                                                                                                |
|                      |                |                                                                                                                                |
+----------------------+----------------+--------------------------------------------------------------------------------------------------------------------------------+
| Language             | drop-down menu | select the localization from the drop-down menu and reload the browser; you can view the status of localization at             |
|                      |                | `pootle.freenas.org <http://pootle.freenas.org/>`_                                                                             |
|                      |                |                                                                                                                                |
+----------------------+----------------+--------------------------------------------------------------------------------------------------------------------------------+
| Console Keyboard Map | drop-down menu | select the keyboard layout                                                                                                     |
|                      |                |                                                                                                                                |
+----------------------+----------------+--------------------------------------------------------------------------------------------------------------------------------+
| Timezone             | drop-down menu | select the timezone from the drop-down menu                                                                                    |
|                      |                |                                                                                                                                |
+----------------------+----------------+--------------------------------------------------------------------------------------------------------------------------------+
| Syslog server        | string         | IP address or hostname of remote syslog server to send logs to; once set, log entries will be written to                       |
|                      |                | both the console and the remote server                                                                                         |
|                      |                |                                                                                                                                |
+----------------------+----------------+--------------------------------------------------------------------------------------------------------------------------------+


If you make any changes, click the "Save" button.

This screen also contains the following buttons:

**Factory Restore:** resets the configuration database to the default base version. However, it does not delete user SSH keys or any other data stored in a
user's home directory. Since any configuration changes stored in the configuration database will be erased, this option is handy if you mess up your system or
wish to return a test system to the original configuration.

**Save Config:** used to create a backup copy of the current configuration database in the format *hostname-version-architecture*.
**Always save the configuration after making changes and verify that you have a saved configuration before performing an upgrade.** This
`forum post <http://forums.freenas.org/showthread.php?10735-How-to-automate-FreeNAS-configuration-database-backup>`_
contains a script to backup the configuration which could be customized and added as a cron job. This
`forum post <http://forums.freenas.org/showthread.php?12333-Backup-config-only-if-changed>`_
contains an alternate script which only saves a copy of the configuration when it changes. And this
`forum post <http://forums.freenas.org/threads/backup-config-file-every-night-automatically.8237>`_
contains a script for backing up the configuration from another system.

**Upload Config:** allows you to browse to location of saved configuration file in order to restore that configuration.

**NTP Servers:** The network time protocol (NTP) is used to synchronize the time on the computers in a network. Accurate time is necessary for the successful
operation of time sensitive applications such as Active Directory. By default, FreeNAS® is pre-configured to use three public NTP servers. If your network is
using Active Directory, ensure that the FreeNAS® system and the Active Directory Domain Controller have been configured to use the same NTP servers. To
add a NTP server to match the settings used by your network's domain controller, click :menuselection:`NTP Servers --> Add NTP Server` to open the screen
shown in Figure 5.2b. Table 5.2b summarizes the options when adding an NTP server.
`ntp.conf(5) <http://www.freebsd.org/cgi/man.cgi?query=ntp.conf>`_
explains these options in more detail.

**Set SSL Certificate:** If you change the "Protocol" value to "HTTPS" or "HTTP+HTTPS", an unsigned RSA certificate and key are auto-generated. To view these,
click "Set SSL Certificate" and review its "SSL Certificate" field. If you already have a signed certificate that you wish to use for SSL/TLS connections,
replace the values in the "SSL certificate" field with a copy/paste of your own key and certificate. Table 5.2c summarizes the settings that can be configured using the SSL tab. This
`howto <http://www.akadia.com/services/ssh_test_certificate.html>`_
shows how to manually generate your own certificate using OpenSSL and provides some examples for the values shown in Table 5.2c.

**Figure 5.2b: Add a NTP Server**

|100000000000011C0000016E12EDFEE5_jpg|

.. |100000000000011C0000016E12EDFEE5_jpg| image:: images/100000000000011C0000016E12EDFEE5.jpg
    :width: 3.4217in
    :height: 3.389in

**Table 5.2b: NTP Servers Configuration Options**

+-------------+-----------+-----------------------------------------------------------------------------------------------------------------------+
| **Setting** | **Value** | **Description**                                                                                                       |
|             |           |                                                                                                                       |
|             |           |                                                                                                                       |
+=============+===========+=======================================================================================================================+
| Address     | string    | name of NTP server                                                                                                    |
|             |           |                                                                                                                       |
+-------------+-----------+-----------------------------------------------------------------------------------------------------------------------+
| Burst       | checkbox  | recommended when "Max. Poll" is greater than *10*; only use on your own servers i.e.                                  |
|             |           | **do not** use with a public NTP server                                                                               |
|             |           |                                                                                                                       |
+-------------+-----------+-----------------------------------------------------------------------------------------------------------------------+
| IBurst      | checkbox  | speeds the initial synchronization (seconds instead of minutes)                                                       |
|             |           |                                                                                                                       |
+-------------+-----------+-----------------------------------------------------------------------------------------------------------------------+
| Prefer      | checkbox  | should only be used for NTP servers that are known to be highly accurate, such as those with time monitoring hardware |
|             |           |                                                                                                                       |
+-------------+-----------+-----------------------------------------------------------------------------------------------------------------------+
| Min. Poll   | integer   | power of 2 in seconds; can not be lower than                                                                          |
|             |           | *4* or higher than "Max. Poll"                                                                                        |
|             |           |                                                                                                                       |
+-------------+-----------+-----------------------------------------------------------------------------------------------------------------------+
| Max. Poll   | integer   | power of 2 in seconds; can not be higher than                                                                         |
|             |           | *17* or lower than "Min. Poll"                                                                                        |
|             |           |                                                                                                                       |
+-------------+-----------+-----------------------------------------------------------------------------------------------------------------------+
| Force       | checkbox  | forces the addition of the NTP server, even if it is currently unreachable                                            |
|             |           |                                                                                                                       |
+-------------+-----------+-----------------------------------------------------------------------------------------------------------------------+

**Table 5.2c: SSL Certificate Configuration Settings**

+---------------------+------------+------------------------------------------------------------------------------------------------------------------+
| **Setting**         | **Value**  | **Description**                                                                                                  |
|                     |            |                                                                                                                  |
+=====================+============+==================================================================================================================+
| Organization        | string     | optional                                                                                                         |
|                     |            |                                                                                                                  |
+---------------------+------------+------------------------------------------------------------------------------------------------------------------+
| Organizational Unit | string     | optional                                                                                                         |
|                     |            |                                                                                                                  |
+---------------------+------------+------------------------------------------------------------------------------------------------------------------+
| Email Address       | string     | optional                                                                                                         |
|                     |            |                                                                                                                  |
+---------------------+------------+------------------------------------------------------------------------------------------------------------------+
| Locality            | string     | optional                                                                                                         |
|                     |            |                                                                                                                  |
+---------------------+------------+------------------------------------------------------------------------------------------------------------------+
| State               | string     | optional                                                                                                         |
|                     |            |                                                                                                                  |
+---------------------+------------+------------------------------------------------------------------------------------------------------------------+
| Country             | string     | optional                                                                                                         |
|                     |            |                                                                                                                  |
+---------------------+------------+------------------------------------------------------------------------------------------------------------------+
| Common Name         | string     | optional                                                                                                         |
|                     |            |                                                                                                                  |
+---------------------+------------+------------------------------------------------------------------------------------------------------------------+
| Passphrase          | string     | if the certificate was created with a passphrase, input and confirm it; the value will appear as dots in the GUI |
|                     |            |                                                                                                                  |
+---------------------+------------+------------------------------------------------------------------------------------------------------------------+
| SSL Certificate     | string     | paste the private key and certificate into the box; the validity of the certificate and key will be checked and  |
|                     |            | the system will fallback to HTTP if either appears to be invalid                                                 |
|                     |            |                                                                                                                  |
+---------------------+------------+------------------------------------------------------------------------------------------------------------------+


Advanced
--------

:menuselection:`System --> Advanced`, shown in Figure 5.3a, allows you to set some miscellaneous settings on the FreeNAS® system. The configurable settings
are summarized in Table 5.3a.

**Figure 5.3a: Advanced Screen**

|Figure53a_png|

**Table 5.3a: Advanced Configuration Settings**

+-----------------------------------------+----------------------------------+------------------------------------------------------------------------------+
| Setting                                 | Value                            | Description                                                                  |
|                                         |                                  |                                                                              |
+=========================================+==================================+==============================================================================+
| Enable Console Menu                     | checkbox                         | unchecking this box removes the console menu shown in Figure 2.6a            |
|                                         |                                  |                                                                              |
+-----------------------------------------+----------------------------------+------------------------------------------------------------------------------+
| Use Serial Console                      | checkbox                         | do **not** check this box if your serial port is disabled                    |
|                                         |                                  |                                                                              |
+-----------------------------------------+----------------------------------+------------------------------------------------------------------------------+
| Serial Port Address                     | string                           | serial port address written in hex                                           |
|                                         |                                  |                                                                              |
+-----------------------------------------+----------------------------------+------------------------------------------------------------------------------+
| Serial Port Speed                       | drop-down menu                   | select the speed used by the serial port                                     |
|                                         |                                  |                                                                              |
+-----------------------------------------+----------------------------------+------------------------------------------------------------------------------+
| Enable screen saver                     | checkbox                         | enables/disables the console screen saver                                    |
|                                         |                                  |                                                                              |
+-----------------------------------------+----------------------------------+------------------------------------------------------------------------------+
| Enable powerd (Power Saving Daemon)     | checkbox                         | `powerd(8) <http://www.freebsd.org/cgi/man.cgi?query=powerd>`_               |
|                                         |                                  | monitors the system state and sets the CPU frequency accordingly             |
|                                         |                                  |                                                                              |
+-----------------------------------------+----------------------------------+------------------------------------------------------------------------------+
| Swap size                               | non-zero integer representing GB | by default, all data disks are created with this amount of swap; this        |
|                                         |                                  | setting does not affect log or cache devices as they are created without     |
|                                         |                                  | swap                                                                         |
|                                         |                                  |                                                                              |
+-----------------------------------------+----------------------------------+------------------------------------------------------------------------------+
| Show console messages in the footer     | checkbox                         | will display console messages in real time at bottom of browser; click the   |
|                                         |                                  | console to bring up a scrollable screen; check the "Stop refresh" box in the |
|                                         |                                  | scrollable screen to pause updating and uncheck the box to continue to watch |
|                                         |                                  | the messages as they occur                                                   |
|                                         |                                  |                                                                              |
+-----------------------------------------+----------------------------------+------------------------------------------------------------------------------+
| Show tracebacks in case of fatal errors | checkbox                         | provides a pop-up of diagnostic information when a fatal error occurs        |
|                                         |                                  |                                                                              |
+-----------------------------------------+----------------------------------+------------------------------------------------------------------------------+
| Show advanced fields by default         | checkbox                         | several GUI menus provide an "Advanced Mode" button to access additional     |
|                                         |                                  | features; enabling this shows these features by default                      |
|                                         |                                  |                                                                              |
+-----------------------------------------+----------------------------------+------------------------------------------------------------------------------+
| Enable autotune                         | checkbox                         | enables the autotune script which attempts to optimize the system depending  |
|                                         |                                  | upon the hardware which is installed                                         |
|                                         |                                  |                                                                              |
+-----------------------------------------+----------------------------------+------------------------------------------------------------------------------+
| Enable debug kernel                     | checkbox                         | if checked, next boot will boot into a debug version of the kernel           |
|                                         |                                  |                                                                              |
+-----------------------------------------+----------------------------------+------------------------------------------------------------------------------+
| Enable automatic upload of kernel       | checkbox                         | if checked, kernel crash dumps are automatically sent to the                 |
| crash dumps                             |                                  | development team for diagnosis                                               |
|                                         |                                  |                                                                              |
+-----------------------------------------+----------------------------------+------------------------------------------------------------------------------+
| MOTD banner                             | string                           | input the message to be seen when a user logs in via SSH                     |
|                                         |                                  |                                                                              |
+-----------------------------------------+----------------------------------+------------------------------------------------------------------------------+


If you make any changes, click the "Save" button.

This tab also contains the following buttons:

**Save Debug:** used to generate a text file of diagnostic information. t will prompt for the location to save the ASCII text file.

**Firmware Update:** used to Upgrade FreeNAS®.

**Performance Test:** runs a series of performance tests and prompts to saves the results as a tarball. Since running the tests can affect performance, a
warning is provided and the tests should be run at a time that will least impact users.

Autotune
~~~~~~~~

FreeNAS® provides an autotune script which attempts to optimize the system depending upon the hardware which is installed. For example, if a ZFS volume
exists on a system with limited RAM, the autotune script will automatically adjust some ZFS sysctl values in an attempt to minimize ZFS memory starvation
issues. It should only be used as a temporary measure on a system that hangs until the underlying hardware issue is addressed by adding more RAM. Autotune
will always slow the system down as it caps the ARC.

The "Enable autotune" checkbox in :menuselection:`System --> Advanced` is unchecked by default; check it if you would like the autotuner to run
at boot time. If you would like the script to run immediately, reboot the system.

If autotuner finds any settings that need adjusting, the changed values will appear in :menuselection:`System --> Sysctls` (for :file:`sysctl.conf` values)
and in :menuselection:`System --> Tunables` (for :file:`loader.conf` values). If you do not like the changes, you can modify the values that are displayed in
the GUI and your changes will override the values that were created by the autotune script. However, if you delete a sysctl or tunable that was created by
autotune, it will be recreated at next boot. This is because autotune only creates values that do not already exist.

If you are trying to increase the performance of your FreeNAS® system and suspect that the current hardware may be limiting performance, try enabling
autotune.

If you wish to read the script to see which checks are performed, the script is located in :file:`/usr/local/bin/autotune`.

Email
-----

:menuselection:`System --> Email`, shown in Figure 5.4a, is used to configure the email settings on the FreeNAS® system. Table 5.4a summarizes the settings
that can be configured using the Email tab.

.. note:: it is important to configure the system so that it can successfully send emails. An automatic script send a nightly email to the *root* user account
   containing important information such as the health of the disks. Alert events are also emailed to the *root* user account.

**Figure 5.4a: Email Screen**

|Figure54a_png|


**Table 5.4a: Email Configuration Settings**

+----------------------+----------------------+-------------------------------------------------------------------------------------------------+
| **Setting**          | **Value**            | **Description**                                                                                 |
|                      |                      |                                                                                                 |
+======================+======================+=================================================================================================+
| From email           | string               | the **from** email address to be used when sending email notifications                          |
|                      |                      |                                                                                                 |
+----------------------+----------------------+-------------------------------------------------------------------------------------------------+
| Outgoing mail server | string or IP address | hostname or IP address of SMTP server                                                           |
|                      |                      |                                                                                                 |
+----------------------+----------------------+-------------------------------------------------------------------------------------------------+
| Port to connect to   | integer              | SMTP port number, typically *25*,                                                               |
|                      |                      | *465* (secure SMTP), or                                                                         |
|                      |                      | *587* (submission)                                                                              |
|                      |                      |                                                                                                 |
+----------------------+----------------------+-------------------------------------------------------------------------------------------------+
| TLS/SSL              | drop-down menu       | encryption type; choices are *Plain*,                                                           |
|                      |                      | *SSL*, or                                                                                       |
|                      |                      | *TLS*                                                                                           |
|                      |                      |                                                                                                 |
|                      |                      |                                                                                                 |
+----------------------+----------------------+-------------------------------------------------------------------------------------------------+
| Use                  | checkbox             | enables/disables                                                                                |
| SMTP                 |                      | `SMTP AUTH <http://en.wikipedia.org/wiki/SMTP_Authentication>`_                                 |
| Authentication       |                      | using PLAIN SASL                                                                                |
|                      |                      |                                                                                                 |
+----------------------+----------------------+-------------------------------------------------------------------------------------------------+
| Username             | string               | used to authenticate with SMTP server                                                           |
|                      |                      |                                                                                                 |
+----------------------+----------------------+-------------------------------------------------------------------------------------------------+
| Password             | string               | used to authenticate with SMTP server                                                           |
|                      |                      |                                                                                                 |
+----------------------+----------------------+-------------------------------------------------------------------------------------------------+
| Send Test Mail       | button               | click to check that configured email settings are working; this will fail if you do not set the |
|                      |                      | **to** email address by clicking the "Change E-mail" button for the                             |
|                      |                      | *root* account in "View Users"                                                                  |
|                      |                      |                                                                                                 |
+----------------------+----------------------+-------------------------------------------------------------------------------------------------+

System Dataset
--------------

:menuselection:`System --> System Dataset`, shown in Figure 5.5a, is used to select the pool which will contain the persistent system dataset. The system
dataset stores debugging core files and Samba4 metadata such as the user/group cache and share level permissions. If the FreeNAS® system is configured to be
a Domain Controller, all of the domain controller state is stored there as well, including domain controller users and groups.

**Figure 5.5a: System Dataset Screen**

|Figure55a_png|

The system dataset can optionally be configured to also store the system log and the Reporting information. If there are lots of log entries or reporting
information, moving these to the system dataset will prevent :file:`/var/` from filling up as :file:`/var/` has limited space. 

Use the drop-down menu to select the ZFS volume (pool) to contain the system dataset.

To also store the system log on the system dataset, check the "Syslog" box.

To also store the reporting information, check the "Reporting Database" box.

If you change the pool storing the system dataset at a later time, FreeNAS® will automatically migrate the existing data in the system dataset to the new
location. 

Tunables
--------

This section of the administrative GUI can be used to either set a FreeBSD sysctl or loader value. A
`sysctl(8) <http://www.freebsd.org/cgi/man.cgi?query=sysctl>`_
makes changes to the FreeBSD kernel running on a FreeNAS® system and can be used to tune the system. Over five hundred system variables can be set using
sysctl(8). Each variable is known as a MIB as it is comprised of a dotted set of components. Since these MIBs are specific to the kernel feature that is being
tuned, descriptions can be found in many FreeBSD man pages (e.g.
`sysctl(3) <http://www.freebsd.org/cgi/man.cgi?query=sysctl&sektion=3>`_,
`tcp(4) <http://www.freebsd.org/cgi/man.cgi?query=tcp>`_
and
`tuning(7) <http://www.freebsd.org/cgi/man.cgi?query=tuning>`_
) and in many sections of the
`FreeBSD Handbook <http://www.freebsd.org/handbook>`_. 

.. warning:: changing the value of a sysctl MIB is an advanced feature that immediately affects the kernel of the FreeNAS® system.
   **Do not change a MIB on a production system unless you understand the ramifications of that change.** A badly configured MIB could cause the system to
   become unbootable, unreachable via the network, or can cause the system to panic under load. Certain changes may break assumptions made by the FreeNAS®
   software. This means that you should always test the impact of any changes on a test system first.

A loader is only loaded when a FreeBSD-based system boots, as
`loader.conf(5) <http://www.freebsd.org/cgi/man.cgi?query=loader.conf>`_
is read to determine if any parameters should be passed to the kernel or if any additional kernel modules (such as drivers) should be loaded. Since loader
values are specific to the kernel parameter or driver to be loaded, descriptions can be found in the man page for the specified driver and in many sections of
the
`FreeBSD Handbook <http://www.freebsd.org/handbook>`_. A typical usage would be to load a FreeBSD hardware driver that does not automatically load after a
FreeNAS® installation. The default FreeNAS® image does not load every possible hardware driver. This is a necessary evil as some drivers conflict with one
another or cause stability issues, some are rarely used, and some drivers just don't belong on a standard NAS system. If you need a driver that is not
automatically loaded, you need to add a loader.

.. warning:: adding a loader is an advanced feature that could adversely effect the ability of the FreeNAS® system to successfully boot. It is
   **very important** that you do not have a typo when adding a loader as this could halt the boot process. Fixing this problem requires physical access to
   the FreeNAS® system and knowledge of how to use the boot loader prompt as described in Recovering From Incorrect Tunables. This means that you should
   always test the impact of any changes on a test system first.

To add a loader or sysctl, go to :menuselection:`System --> Tunables --> Add Tunable`, as seen in Figure 5.6a.

**Figure 5.6a: Adding a Tunable**

|Figure56a_png|

Table 5.6a summarizes the options when adding a tunable.

**Table 5.6a: Adding a Tunable**

+-------------+-------------------+---------------------------------------------------------------------------+
| **Setting** | **Value**         | **Description**                                                           |
|             |                   |                                                                           |
|             |                   |                                                                           |
+=============+===================+===========================================================================+
| Variable    | string            | typically the name of the driver to load, as indicated by its man page    |
|             |                   |                                                                           |
+-------------+-------------------+---------------------------------------------------------------------------+
| Value       | integer or string | value to associate with variable; typically this is set to *YES*          |
|             |                   | to enable the driver specified by the variable                            |
|             |                   |                                                                           |
+-------------+-------------------+---------------------------------------------------------------------------+
| Type        | drop-down menu    | choices are *Loader* or                                                   |
|             |                   | *Sysctl*                                                                  |
|             |                   |                                                                           |
+-------------+-------------------+---------------------------------------------------------------------------+
| Comment     | string            | optional, but a useful reminder for the reason behind adding this tunable |
|             |                   |                                                                           |
+-------------+-------------------+---------------------------------------------------------------------------+
| Enabled     | checkbox          | uncheck if you would like to disable the tunable without deleting it      |
|             |                   |                                                                           |
+-------------+-------------------+---------------------------------------------------------------------------+

.. note:: as soon as you add or edit a *Sysctl*, the running kernel will change that variable to the value you specify. As long as the sysctl exists, that
   value will persist across reboots and upgrades.  However, when you add a *Loader*, the changes you make will not take effect until the system is rebooted
   as loaders are only read when the kernel is loaded at boot time. As long as the loader exists, your changes will persist at each boot and across upgrades.

Any sysctls or loaders that you add will be listed alphabetically in :menuselection:`System --> Tunables --> View Tunables`. To change the value of an
existing tunable, click its "Edit" button. To remove a tunable, click its "Delete" button.

Some sysctls are read-only will require a reboot to enable the setting change. You can verify if a sysctl is read-only by first attempting to change it from
Shell. For example, to change the value of *net.inet.tcp.delay_ack* to *1* , use the command :command:`sysctl net.inet.tcp.delay_ack=1`. If the sysctl value
is read-only, an error message will indicate that the setting is read-only. If you do not get an error, the setting is now applied. However, for the setting
to be persistent across reboots, the sysctl must be added in :menuselection:`System --> Tunables`.

At this time, the GUI does not display the sysctl MIBs that are pre-set in the installation image. 9.3 ships with the following MIBs set::

 kern.metadelay=3
 kern.dirdelay=4
 kern.filedelay=5
 kern.coredump=0
 net.inet.tcp.delayed_ack=0


**Do not add or edit the default MIBS as sysctls** as doing so will overwrite the default values which may render the system unusable.

At this time, the GUI does not display the loaders that are pre-set in the installation image. 9.3 ships with the following loaders set::

 autoboot_delay="2"
 loader_logo="freenas"
 loader_menu_title="Welcome to FreeNAS"
 loader_brand="freenas-brand"
 loader_version=" "
 debug.debugger_on_panic=1
 debug.ddb.textdump.pending=1
 hw.hptrr.attach_generic=0
 kern.ipc.nmbclusters="262144"
 vfs.mountroot.timeout="30"
 hint.isp.0.role=2
 hint.isp.1.role=2
 hint.isp.2.role=2
 hint.isp.3.role=2
 module_path="/boot/kernel;/boot/modules;/usr/local/modules"
 net.inet6.ip6.auto_linklocal="0"

**Do not add or edit the default tunables** as doing so will overwrite the default values which may render the system unusable.

The ZFS version used in 9.2.2 deprecates the following loaders::

 vfs.zfs.write_limit_override
 vfs.zfs.write_limit_inflated
 vfs.zfs.write_limit_max
 vfs.zfs.write_limit_min
 vfs.zfs.write_limit_shift
 vfs.zfs.no_write_throttle

If you upgrade from an earlier version of FreeNAS® where these tunables are set, they will automatically be deleted for you. You should not try to add these
loaders back.

Recovering From Incorrect Tunables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If a tunable is preventing the system from booting, you will need physical access to the FreeNAS® system. Watch the boot messages and press the
:kbd:`3` key or the :kbd:`Esc` key to select "3. Escape to loader prompt" when you see the FreeNAS® boot menu shown in Figure 5.6b.

**Figure 5.6b: FreeNAS® Boot Menu**

|10000000000002D10000018F743DB34E_png|

.. |10000000000002D10000018F743DB34E_png| image:: images/10000000000002D10000018F743DB34E.png
    :width: 6.0583in
    :height: 3.3252in

The boot loader prompt provides a minimal set of commands described in
`loader(8) <http://www.freebsd.org/cgi/man.cgi?query=loader>`_. Once at the prompt, use the :command:`unset` command to disable a problematic value, the
:command:`set` command to modify the problematic value, or the :command:`unload` command to prevent the problematic driver from loading.

Example 5.6a demonstrates several examples using these commands at the boot loader prompt. The first command disables the current value associated with the
*kern.ipc.nmbclusters* MIB and will fail with a "no such file or directory" error message if a current tunable does not exist to set this value. The second
command disables ACPI. The third command instructs the system not to load the fuse driver. When finished, type :command:`boot` to continue the boot process.

**Example 5.6a: Sample Commands at the Boot Loader Prompt**
::

 Type '?' for a list of commands, 'help' for more detailed help.
 OK
 
 unset kern.ipc.nmbclusters
 OK

 set hint.acpi.0.disabled=1
 OK

 unload fuse
 OK

 boot

Any changes made at the boot loader prompt only effect the current boot. This means that you need to edit or remove the problematic tunable in
:menuselection:`System --> Tunables --> View Tunables` to make your change permanent and to prevent future boot errors.
