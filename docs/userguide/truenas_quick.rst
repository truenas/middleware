:orphan:

Accessing TrueNAS®
------------------

When you boot into TrueNAS®, the Console Setup, shown in Figure 3a, will appear at the end of the boot process. If you have access to the TrueNAS®
system's keyboard and monitor, this Console Setup menu can be used to administer the system should the administrative GUI become inaccessible.

.. note:: you can access the Console Setup menu from within the TrueNAS® GUI by typing :command:`/etc/netcli` from `Shell`. You can disable the Console
   Setup menu by unchecking the "Enable Console Menu" in `System --> Settings --> Advanced`.

**Figure 3a: TrueNAS® Console Setup Menu**

|console1a.png|

.. |console1a.png| image:: images/console1a.png
    :width: 5.4in
    :height: 3.2in

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
need to go to :menuselection:`Storage --> Volumes --> Import Volume` to re-import your volume.

**9) Shell:** enters a shell in order to run FreeBSD commands. To leave the shell, type :command:`exit`.

**10) System Update:** if any system updates are available, they will automatically be downloaded and applied. The functionality is the same as described in
:ref:`Updating Between Releases`, except that the updates will be applied immediately for the currently selected train and access to the GUI is not required.

**11) Create backup:** used to backup the TrueNAS® configuration and ZFS layout, and, optionally, the data, to a remote system over an encrypted connection.
The only requirement for the remote system is that it has sufficient space to hold the backup and it is running an SSH server on port 22. The remote system
does not have to be formatted with ZFS as the backup will be saved as a binary file. When this option is selected, it will prompt for the hostname or IP
address of the remote system, the name of a user account on the remote system, the password for that user account, the full path to a directory on the remote
system to save the backup, whether or not to also backup all of the data, whether or not to compress the data, and a confirmation to save the values, where
"y" will start the backup, "n" will repeat the configuration, and "q" will quit the backup wizard. If you leave the password empty, key-based authentication
will be used instead. This requires that the public key of the *root* user is stored in :file:`~root/.ssh/authorized_keys` on the remote system and that key
should **not** be protected by a passphrase. Refer to :ref:`Rsync over SSH Mode` for instructions on how to generate a key pair.

**12) Restore from a backup:** if a backup has already been created using "11) Create backup" or :menuselection:`System --> Advanced --> Backup`, it can be
restored using this option. Once selected, it will prompt for the hostname or IP address of the remote system holding the backup, the username that was used,
the password (leave empty if key-based authentication was used), the full path of the remote directory storing the backup, and a confirmation that the values
are correct, where "y" will start the restore, "n" will repeat the configuration, and "q" will quit the restore wizard. The restore will indicate if it could
log into the remote system, find the backup, and indicate whether or not the backup contains data. It will then prompt to restore TrueNAS® from that backup.
Note that if you press "y" to perform the restore, the system will be returned to the database configuration, ZFS layout, and optionally the data, at the
point when the backup was created. The system will reboot once the restore is complete.

.. warning:: the backup and restore options are meant for disaster recovery. If you restore a system, it will be returned to the point in time that the backup
             was created. If you select the option to save the data, any data created after the backup was made will be lost. If you do **not** select the
             option to save the data, the system will be recreated with the same ZFS layout, but with **no** data.

**13) Reboot:** reboots the system.

**14) Shutdown:** halts the system.

During boot, TrueNAS® will automatically try to connect to a DHCP server from all live interfaces. If it successfully receives an IP address, it will display
the IP address which can be used to access the graphical console. In the example seen in Figure 3a, the TrueNAS® system is accessible from
*http://10.2.1.115*.

If your TrueNAS® server is not connected to a network with a DHCP server, you can use the network configuration wizard to manually configure the interface as
seen in Example 3a. In this example, the TrueNAS® system has one network interface (*em0*).

**Example 3a: Manually Setting an IP Address from the Console Menu**

::

 Enter an option from 1-14: 1
 1) em0
 Select an interface (q to quit): 1
 Delete existing config? (y/n) n
 Configure interface for DHCP? (y/n) n
 Configure IPv4? (y/n) y
 Interface name: (press enter as can be blank)
 Several input formats are supported
 Example 1 CIDR Notation: 192.168.1.1/24
 Example 2 IP and Netmask separate: IP: 192.168.1.1
 Netmask: 255.255.255.0, or /24 or 24
 IPv4 Address: 192.168.1.108/24
 Saving interface configuration: Ok
 Configure IPv6? (y/n) n
 Restarting network: ok
 You may try the following URLs to access the web user interface:
 http://192.168.1.108

Once the system has an IP address, input that address into a graphical web browser from a computer capable of accessing the network containing the TrueNAS®
system. You should be prompted to input the password for the *root* user, as seen in Figure 3b.

**Figure 3b: Input the Root Password**

|tn_login.png|

.. |tn_login.png| image:: images/tn_login.png
    :width: 5.6in
    :height: 2.6in

Enter the default password of *abcd1234*. You should then see the administrative GUI as shown in the example in Figure 3c.

.. note:: you can change the default *root* password to a more secure value by going to `Account --> Users --> View Users`. Highlight the entry for
          *root*, click the "Modify User" button, enter the new password in the "Password" and "Password confirmation" fields, and click "OK" to save the new
          password to use on subsequent logins.

**Figure 3c: TrueNAS® Graphical Configuration Menu**

|tn_initial.png|

.. |tn_initial.png| image:: images/tn_initial.png
    :width: 12.0in
    :height: 4.5in

If you are unable to access the IP address from a browser, check the following:

* Are proxy settings enabled in the browser configuration? If so, disable the settings and try connecting again.

* If the page does not load, make sure that you can :command:`ping` the TrueNAS® system's IP address. If the address is in a private IP address range, you
  will only be able to access the system from within the private network.

* If the user interface loads but is unresponsive or seems to be missing menu items, try using a different web browser. IE9 has known issues and will not
  display the graphical administrative interface correctly if compatibility mode is turned on. If you can't access the GUI using Internet Explorer, use
  `Firefox <http://www.mozilla.com/en-US/firefox/all.html>`_
  instead.

* If you receive "An error occurred!" messages when attempting to configure an item in the GUI, make sure that the browser is set to allow cookies from
  the TrueNAS® system.

This
`blog post <http://fortysomethinggeek.blogspot.com/2012/10/ipad-iphone-connect-with-freenas-or-any.html>`_
describes some applications which can be used to access the TrueNAS® system from an iPad or iPhone.

.. index:: Initial Configuration Wizard, Configuration Wizard, Wizard
.. _Initial Configuration Wizard:

The rest of this Guide describes all of the configuration screens available within the TrueNAS® graphical administrative interface. The screens are listed in
the order that they appear within the tree, or the left frame of the graphical interface.
**iXsystems recommends that you contact your support technician for initial setup and configuration assistance.**
Once your system has been configured and you are familiar with the configuration workflow, the rest of this document can be used as a reference guide to the
features built into the TrueNAS® appliance.

.. note:: it is important to use the graphical interface (or the console setup menu) for all non-ZFS configuration changes. TrueNAS® uses a configuration
   database to store its settings. If you make changes at the command line, they will not be written to the configuration database. This means that these
   changes will not persist after a reboot and will be overwritten by the values in the configuration database during an upgrade.

