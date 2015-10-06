.. _Booting Into FreeNAS®:

Booting Into FreeNAS®
----------------------

When you boot into FreeNAS®, the FreeNAS® CLI, shown in Figure 3a, will appear at the end of the boot process. If you have access to the FreeNAS®
system's keyboard and monitor, the CLI can be used to administer the system should the administrative GUI become inaccessible.

**Figure 3a: FreeNAS® CLI**

.. image:: images/cli1.png

During boot, FreeNAS® will automatically try to connect to a DHCP server from all live interfaces. If it successfully receives an IP address, it will display
the IP address which can be used to access the graphical console. In the example seen in Figure 3a, the FreeNAS® system is accessible from
*http://10.2.1.115*.

If your FreeNAS® server is not connected to a network with a DHCP server, you can use the CLI to manually configure the interface. In the example shown
in Example 3a, the administrator typed :command:`shell` to enter a FreeBSD shell and then used :command:`ifconfig` to specify the IP address and subnet mask for the
network interface (*em0*).

**Example 3a: Manually Setting an IP Address**
::

 127.0.0.1:>shell
 # ifconfig em0 10.2.1.115 netmask 255.255.255.0

Once the system has an IP address, input that address into a graphical web browser from a computer capable of accessing the network containing the FreeNAS®
system. You should be prompted to input the password for the root user, as seen in Figure 3b.

**Figure 3b: Input the Root Password**

.. image:: images/login.png

Enter the password created during the installation. You should then see the administrative GUI as shown in the example in Figure 3c.

**Figure 3c: FreeNAS® Graphical Configuration Menu**

.. image:: images/initial.png

If you are unable to access the IP address from a browser, check the following:

* Are proxy settings enabled in the browser configuration? If so, disable the settings and try connecting again.

* If the page does not load, make sure that you can :command:`ping` the FreeNAS® system's IP address. If the address is in a private IP address range, you
  will only be able to access the system from within the private network.

* If the user interface loads but is unresponsive or seems to be missing menu items, try using a different web browser. IE9 has known issues and will not
  display the graphical administrative interface correctly if compatibility mode is turned on. If you can't access the GUI using Internet Explorer, use
  `Firefox <https://www.mozilla.org/en-US/firefox/all/>`_ instead.

* If you receive "An error occurred!" messages when attempting to configure an item in the GUI, make sure that the browser is set to allow cookies from
  the FreeNAS® system.

This
`blog post <http://fortysomethinggeek.blogspot.com/2012/10/ipad-iphone-connect-with-freenas-or-any.html>`_
describes some applications which can be used to access the FreeNAS® system from an iPad or iPhone.

The rest of this Guide describes the FreeNAS® graphical interface in more detail. The layout of this Guide follows the order of the menu items in the tree
located in the left frame of the graphical interface.

.. note:: it is important to use the GUI (or the FreeNAS® CLI) for all configuration changes. FreeNAS® uses a configuration database to store its
   settings. While it is possible to use the command line to modify your configuration, changes made at the command line **are not** written to the
   configuration database. This means that any changes made at the command line will not persist after a reboot and will be overwritten by the values in the
   configuration database during an upgrade.
