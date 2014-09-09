:orphan:

.. _Booting Into FreeNAS®:

Booting Into FreeNAS®
----------------------

When you boot into FreeNAS®, the Console Setup, shown in Figure 3a, will appear at the end of the boot process. If you have access to the the FreeNAS®
system's keyboard and monitor, this Console Setup menu can be used to administer the system should the administrative GUI become inaccessible.

.. note:: you can access the Console Setup menu from within the FreeNAS® GUI by typing
   :command:`/etc/netcli` from Shell. You can disable the Console Setup menu by unchecking the "Enable Console Menu" in :menuselection:`System --> Advanced`.

**Figure 3a: FreeNAS® Console Setup Menu**

|console1.png|

.. |console1.png| image:: images/console1.png
    :width: 5.8in
    :height: 2.8in

This menu provides the following options:

**1) Configure Network Interfaces:** provides a configuration wizard to configure the system's network interfaces.

**2) Configure Link Aggregation:** allows you to either create a new link aggregation or to delete an existing link aggregation.

**3) Configure VLAN Interface:** used to create or delete a VLAN interface.

**4) Configure Default Route:** used to set the IPv4 or IPv6 default gateway. When prompted, input the IP address of the default gateway.

**5) Configure Static Routes:** will prompt for the destination network and the gateway IP address. Re-enter this option for each route you need to add.

**6) Configure DNS:** will prompt for the name of the DNS domain then the IP address of the first DNS server. To input multiple DNS servers, press
:kbd:`Enter` to input the next one. When finished, press :kbd:`Enter` twice to leave this option.

**7) Reset Root Password:** if you are unable to login to the graphical administrative interface, select this option and follow the prompts to set the *root*
password.

**8) Reset to factory defaults:** if you wish to delete
**all** of the configuration changes made in the administrative GUI, select this option. Once the configuration is reset, the system will reboot. You will
need to go to :menuselection:`Storage --> Volumes --> Auto Import Volume` to re-import your volume.

**9) Shell:** enters a shell in order to run FreeBSD commands. To leave the shell, type :command:`exit`.

**10) Reboot:** reboots the system.

**11) Shutdown:** halts the system.

During boot, FreeNAS® will automatically try to connect to a DHCP server from all live interfaces. If it successfully receives an IP address, it will display
the IP address which can be used to access the graphical console. In the example seen in Figure 2.5b, the FreeNAS® system is accessible from
*http://192.168.1.97*.

If your FreeNAS® server is not connected to a network with a DHCP server, you can use the network configuration wizard to manually configure the interface as
seen in Example 3a. In this example, the FreeNAS® system has one network interface (*em0*).

**Example 3a: Manually Setting an IP Address from the Console Menu**
::

 Enter an option from 1-11: 1
 1) em0
 Select an interface (q to quit): 1
 Delete existing config? (y/n) n
 Configure interface for DHCP? (y/n) n
 Configure IPv4? (y/n) y
 Interface name: (press enter as can be blank)
 Several input formats are supported
 Example 1 CIDR Notation: 192.168.1.1/24
 Example 2 IP and Netmask separate:
 IP: 192.168.1.1
 Netmask: 255.255.255.0, or /24 or 24
 IPv4 Address: 192.168.1.108/24
 Saving interface configuration: Ok
 Configure IPv6? (y/n) n
 Restarting network: ok
 You may try the following URLs to access the web user interface:
 `http://192.168.1.108 <http://192.168.1.108/>`_

Once the system has an IP address, input that address into a graphical web browser from a computer capable of accessing the network containing the FreeNAS®
system. You should be prompted to input the password for the root user, as seen in Figure 3b.

**Figure 3b: Input the Root Password**

|Figure26b_png|

Enter the password created during the installation. You should then see the administrative GUI as shown in the example in Figure 3c.

**Figure 3c: FreeNAS® Graphical Configuration Menu**

|Figure26c_png|

If you are unable to access the IP address from a browser, check the following:

* Are proxy settings enabled in the browser configuration? If so, disable the settings and try connecting again.

* If the page does not load, make sure that you can :command:`ping` the FreeNAS® system's IP address. If the address is in a private IP address range, you
  will only be able to access the system from within the private network.

* If the user interface loads but is unresponsive or seems to be missing menu items, try using a different web browser. IE9 has known issues and will not
  display the graphical administrative interface correctly if compatibility mode is turned on. If you can't access the GUI using Internet Explorer, use
  `Firefox <http://www.mozilla.com/en-US/firefox/all.html>`_
  instead.

* If you receive "An error occurred!" messages when attempting to configure an item in the GUI, make sure that the browser is set to allow cookies from
  the FreeNAS® system.

This
`blog post <http://fortysomethinggeek.blogspot.com/2012/10/ipad-iphone-connect-with-freenas-or-any.html>`_
describes some applications which can be used to access the FreeNAS® system from an iPad or iPhone.

.. _Initial Configuration Wizard:

Initial Configuration Wizard
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Beginning with FreeNAS® 9.3, a configuration wizard automatically starts the first time the FreeNAS® GUI is accessed. This wizard walks you through the
steps needed to quickly configure FreeNAS® to start serving data over a network. This section describes these configuration steps. If you wish to use the
wizard again after the initial configuration, click the "Wizard" icon.

Figure 3.1a shows the initial wizard configuration screen that appears if the storage disks have not yet been formatted.

**Figure 3.1a: Initial Configuration Wizard**

|wizard1.png|

Input a name for the ZFS pool that conforms to these
`naming conventions <http://docs.oracle.com/cd/E23824_01/html/821-1448/gbcpt.html>`_. It is recommended to choose a name that will stick out in the logs (e.g.
**not** :file:`data` or :file:`freenas`.

Next, decide if the pool should provide disk redundancy, and if so, which type. The following types are available:

* **Automatic:**

* **RAID 10:**

* **RAIDZ2:**

* **RAIDZ1:**

* **Stripe:**

Once you have made your selection, click "Next" to continue.

If the disks have already been formatted with UFS or ZFS, the initial wizard screen will instead prompt to import the volume, as seen in Figure 3.1b.

**Figure 3.1b: Volume Import Screen**

|wizard2.png|

Select the existing volume from the drop-down menu and click "Next" to continue.

.. note:: you can exit the wizard at any time by clicking the "Exit" button. However, exiting the wizard will not save any selections. You can always restart
   the wizard again by clicking the "Wizard" icon. Alternately, you can use the FreeNAS® GUI to configure the system, as described in the rest of this Guide.

The next screen in the wizard is shown in Figure 3.1c.

**Figure 3.1c: Directory Service Selection**

|wizard3.png|

If the FreeNAS® system is on a network that does not contain an Active Directory, LDAP, NIS, or NT4 server, click "Next" to skip to the next screen.

However, if the FreeNAS® system is on a network containing an Active Directory, LDAP, NIS, or NT4 server and you wish to import the users and groups from
that server, select the type of directory service in the "Directory Service" drop-down menu. The rest of the fields in this screen will vary, depending upon
which directory service is selected. Tables 3.1a to 3.1d summarize the available configuration options for each directory service.

.. note:: additional configuration options are available. The wizard can be used to set the initial values required to connect to that directory service. You
   can then review the other available options in :ref:`Directory Service` to determine if additional configuration is required.

**Table 3.1a: Active Directory Options**

+--------------------------+---------------+-------------------------------------------------------------------------------------------------------+
| **Setting**              | **Value**     | **Description**                                                                                       |
|                          |               |                                                                                                       |
+==========================+===============+=======================================================================================================+
| Domain Name              | string        | name of Active Directory domain (e.g. *example.com*) or child domain (e.g.                            |
|                          |               | *sales.example.com*)                                                                                  |
|                          |               |                                                                                                       |
+--------------------------+---------------+-------------------------------------------------------------------------------------------------------+
| Domain Account Name      | string        | name of the Active Directory administrator account                                                    |
|                          |               |                                                                                                       |
+--------------------------+---------------+-------------------------------------------------------------------------------------------------------+
| Domain Account Password  | string        | password for the Active Directory administrator account                                               |
|                          |               |                                                                                                       |
+--------------------------+---------------+-------------------------------------------------------------------------------------------------------+

**Table 3.1b: LDAP Options**

+-------------------------+----------------+-------------------------------------------------------------------------------------------------------+
| **Setting**             | **Value**      | **Description**                                                                                       |
|                         |                |                                                                                                       |
+=========================+================+=======================================================================================================+
| Hostname                | string         | hostname or IP address of LDAP server                                                                 |
|                         |                |                                                                                                       |
+-------------------------+----------------+-------------------------------------------------------------------------------------------------------+
| Base DN                 | string         | top level of the LDAP directory tree to be used when searching for resources (e.g.                    |
|                         |                | *dc=test,dc=org*)                                                                                     |
|                         |                |                                                                                                       |
+-------------------------+----------------+-------------------------------------------------------------------------------------------------------+
| Bind DN                 | string         | name of administrative account on LDAP server (e.g. *cn=Manager,dc=test,dc=org*)                      |
|                         |                |                                                                                                       |
+-------------------------+----------------+-------------------------------------------------------------------------------------------------------+
| Base password           | string         | password for                                                                                          |
|                         |                |                                                                                                       |
+-------------------------+----------------+-------------------------------------------------------------------------------------------------------+


**Table 3.1c: NIS Options**

+-------------------------+----------------+-------------------------------------------------------------------------------------------------------+
| **Setting**             | **Value**      | **Description**                                                                                       |
|                         |                |                                                                                                       |
+=========================+================+=======================================================================================================+
| NIS domain              | string         | name of NIS domain                                                                                    |
|                         |                |                                                                                                       |
+-------------------------+----------------+-------------------------------------------------------------------------------------------------------+
| NIS servers             | string         | comma delimited list of hostnames or IP addresses                                                     |
|                         |                |                                                                                                       |
+-------------------------+----------------+-------------------------------------------------------------------------------------------------------+
| Secure mode             | checkbox       | if checked,                                                                                           |
|                         |                | `ypbind(8) <http://www.freebsd.org/cgi/man.cgi?query=ypbind>`_                                        |
|                         |                | will refuse to bind to any NIS server that is not running as root on a TCP port number over 1024      |
|                         |                |                                                                                                       |
+-------------------------+----------------+-------------------------------------------------------------------------------------------------------+
| Manycast                | checkbox       | if checked, ypbind will bind to the server that responds the fastest; this is useful when no local    |
|                         |                | NIS server is available on the same subnet                                                            |
|                         |                |                                                                                                       |
+-------------------------+----------------+-------------------------------------------------------------------------------------------------------+


**Table 3.1d: NT4 Options**

+-------------------------+----------------+-------------------------------------------------------------------------------------------------------+
| **Setting**             | **Value**      | **Description**                                                                                       |
|                         |                |                                                                                                       |
+=========================+================+=======================================================================================================+
| Domain Controller       | string         | hostname of domain controller                                                                         |
|                         |                |                                                                                                       |
+-------------------------+----------------+-------------------------------------------------------------------------------------------------------+
| NetBIOS Name            | string         | hostname of FreeNAS system                                                                            |
|                         |                |                                                                                                       |
+-------------------------+----------------+-------------------------------------------------------------------------------------------------------+
| Workgroup Name          | string         | name of Windows server's workgroup                                                                    |
|                         |                |                                                                                                       |
+-------------------------+----------------+-------------------------------------------------------------------------------------------------------+
| Administrator Name      | string         | name of the domain administrator account                                                              |
|                         |                |                                                                                                       |
+-------------------------+----------------+-------------------------------------------------------------------------------------------------------+
| Administrator Password  | string         | input and confirm the password for the domain administrator account                                   |
|                         |                |                                                                                                       |
+-------------------------+----------------+-------------------------------------------------------------------------------------------------------+

The next configuration screen, shown in Figure 3.1d, can be used to create the network shares.

**Figure 3.1d: Share Creation**

|wizard4.png|

FreeNAS® supports several types of shares for providing storage data to the clients in a network. To create a share, input a name, then select the "Purpose"
of the share:

* **Windows (CIFS):** this type of share can be accessed by any operating system using a CIFS client. Check the box for "Allow Guest" if users should not be
  prompted for a password in order to access the share.

* **Mac OS X (AFP):** this type of share can be accessed by Mac OS X users. Check the box for "Time Machine" if Mac users will be using the FreeNAS® system
  as a backup device.

* **Generic Unix (UFS):** this type of share can be accessed by any operating system using a NFS client.

* **Block Storage (iSCSI):** this type of share can be accessed by any operating system using iSCSI initiator software. Input the size of the block storage to
  create in the format *20GiB* (for 20 GB).

After selecting the "Purpose", click the "Ownership" button to see the screen shown in Figure 3.1e.

**Figure 3.1e: Share Permissions**

|wizard5.png|

The default permissions for the share will be displayed. To create a user and/or group to customize the permissions, check the appropriate box.


#. Set the Email Address: FreeNAS® provides an Alert icon in the upper right corner to provide a visual indication of events that warrant administrative
   attention. The alert system automatically emails the *root* user account whenever an alert is issued.

   To set the email address for the *root* account, go to :menuselection:`Account --> Users --> View Users`. Click the "Change E-mail" button associated with
   the *root* user account and input the email address of the person to receive the administrative emails.

#. Enable Console Logging: To view system messages within the graphical administrative interface, go to :menuselection:`System --> Advanced`. Check the box
   "Show console messages in the footer" and click "Save". The output of :command:`tail -f /var/log/messages` will now be displayed at the bottom of the
   screen. If you click the console messages area, it will pop-up as a window, allowing you to scroll through the output and to copy its contents.

#. Configure Permissions: Setting permissions is an important aspect of configuring access to storage data. The graphical administrative interface is meant to
   set the **initial** permissions in order to make a volume or dataset accessible as a share. Once a share is available, the client operating system should
   be used to fine-tune the permissions of the files and directories that are created by the client.

   Determine which users should have access to which data. This will help you to determine if multiple
   shares should be created to meet the permissions needs of your environment.

#. Start Service(s): Once you have configured your share or service, you will need to start its associated service(s) in order to implement the configuration.
   By default, all services are off until you start them. The status of services is managed using :menuselection:`Services --> Control Services`. To start a
   service, click its red "OFF" button. After a second or so, it will change to a blue ON, indicating that the service has been enabled. Watch the console
   messages as the service starts to determine if there are any error messages.

#. Test Configuration: If the service successfully starts, try to make a connection to the service from a client system. For example, use Windows Explorer to
   try to connect to a CIFS share, use an FTP client such as Filezilla to try to connect to an FTP share, or use Finder on a Mac OS X system to try to connect
   to an AFP share. If the service starts correctly and you can make a connection but receive permissions errors, check that the user has permissions to the
   volume/dataset being accessed.

#. Backup Configuration: Once you have tested your configuration, be sure to back it up. Go to :menuselection:`System --> General` and click the "Save Config"
   button. Your browser will provide an option to save a copy of the configuration database. You should
   **backup your configuration whenever you make configuration changes and always before upgrading FreeNAS®**.

The rest of this Guide,

.. note:: it is important to use the GUI (or the Console Setup menu) for all configuration changes. FreeNAS® uses a configuration database to store its
   settings. While it is possible to use the command line to modify your configuration, changes made at the command line are not written to the configuration
   database. This means that any changes made at the command line will not persist after a reboot and will be overwritten by the values in the configuration
   database during an upgrade.