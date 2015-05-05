:orphan:

Accessing TrueNAS®
------------------

When you boot into TrueNAS®, the Console Setup, shown in Figure 3a, will appear at the end of the boot process. If you have access to the the TrueNAS®
system's keyboard and monitor, this Console Setup menu can be used to administer the system should the administrative GUI become inaccessible.

.. note:: you can access the Console Setup menu from within the TrueNAS® GUI by typing :command:`/etc/netcli` from `Shell`. You can disable the Console
   Setup menu by unchecking the "Enable Console Menu" in `System --> Settings --> Advanced`.

**Figure 3a: TrueNAS® Console Setup Menu**

|console.png|

This menu provides the following options:

**1) Configure Network Interfaces:** provides a configuration wizard to configure the system's network interfaces.

**2) Configure Link Aggregation:** allows you to either create a new link aggregation_ or to delete an existing link aggregation.

**3) Configure VLAN Interface:** used to create or delete a VLAN interface.

**4) Configure Default Route:** used to set the IPv4 or IPv6 default gateway. When prompted, input the IP address of the default gateway.

**5) Configure Static Routes:** will prompt for the destination network and the gateway IP address. Re-enter this option for each route you need to add.

**6) Configure DNS:** will prompt for the name of the DNS domain then the IP address of the first DNS server. To input multiple DNS servers, press enter to
input the next one. When finished, press enter twice to leave this option.

**7) Reset WebGUI login credentials:** if you are unable to login to the graphical administrative interface, select this option. The next time the graphical
interface is accessed, it will prompt to set the *root* password.

**8) Reset to factory defaults:** if you wish to delete
**all** of the configuration changes made in the administrative GUI, select this option. Once the configuration is reset, the system will reboot. You will
need to go to Storage --> Volumes --> Auto Import Volume to re-import your volume.

**9) Shell:** enters a shell in order to run FreeBSD commands. To leave the shell, type :command:`exit`.

**10) Reboot:** reboots the system.

**11) Shutdown:** halts the system.

During boot, TrueNAS® will automatically try to connect to a DHCP server from all live interfaces. If it successfully receives an IP address, it will display
the IP address which can be used to access the graphical console. In the example seen in Figure 3a, the TrueNAS® system is accessible from
*http://192.168.1.78*.

If your TrueNAS® server is not connected to a network with a DHCP server, you can use the network configuration wizard to manually configure the interface as
seen in Example 3a. In this example, the TrueNAS® system has one network interface (*em0*).

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
 Example 2 IP and Netmask separate: IP: 192.168.1.1
 Netmask: 255.255.255.0, or /24 or 24
 IPv4 Address: 192.168.1.108/24
 Saving interface configuration: Ok
 Configure IPv6? (y/n) n
 Restarting network: ok
 You may try the following URLs to access the web user interface:
 `http://192.168.1.108 <http://192.168.1.108/>`_

Activating the License and Logging In
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once the system has an IP address, input that address into a graphical web browser from a computer capable of accessing the network containing the TrueNAS®
system.

The first time you connect, you will be presented with the EULA shown in `Appendix A`_. Click the "I agree" button to proceed to the license activation screen
shown in Figure 3.1a.

**Figure 3.1a: License Activation Screen**

|1000000000000351000001FE0607567B_png|

.. |1000000000000351000001FE0607567B_png| image:: images/activate.png
    :width: 6.9252in
    :height: 4.1252in

Click the hyperlink "TrueNAS® Request File" and email the automatically generated file to activate@ixsystems.com. Once you receive the license file, use the
Browse button to locate the file and press Activate to apply the license. A message will indicate that the system is rebooting. After a moment or so, refresh
your browser.

Next, you should be prompted to create a password for the *root* user, as seen in Figure 3.1b.

**Figure 3.1b: Set the Root Password**

|10000000000001E000000191AA80FB08_png|

.. |10000000000001E000000191AA80FB08_png| image:: images/root.png
    :width: 4.0335in
    :height: 3.3417in

Setting a password is mandatory and the password can not be blank. Since this password provides access to the administrative GUI, it should be a hard-to-guess
password. Once the password has been input and confirmed, you should see the administrative GUI as shown in the example in Figure 3.1c.

**Figure 3.1c: TrueNAS® Graphical Configuration Menu**

|100000000000062E00000213491B6158_png|

.. |100000000000062E00000213491B6158_png| image:: images/gui.png
    :width: 6.9252in
    :height: 2.3047in

The rest of this Guide describes all of the configuration screens available within the TrueNAS® graphical administrative interface. The screens are listed in
the order that they appear within the tree, or the left frame of the graphical interface.
**iXsystems recommends that you contact your support technician for initial setup and configuration assistance.**
Once your system has been configured and you are familiar with the configuration workflow, the rest of this document can be used as a reference guide to the
features built into the TrueNAS® appliance.

.. note:: it is important to use the graphical interface (or the console setup menu) for all non-ZFS configuration changes. TrueNAS® uses a configuration
   database to store its settings. If you make changes at the command line, they will not be written to the configuration database. This means that these
   changes will not persist after a reboot and will be overwritten by the values in the configuration database during an upgrade.
