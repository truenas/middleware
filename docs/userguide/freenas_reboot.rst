.. index:: Reboot
.. _Reboot:

Reboot
======

If you click the "Reboot" entry in the tree, you will receive the warning message shown in Figure 18a and your browser color will change to red to indicate
that you have selected an option that will negatively impact users of the FreeNAS® system.

**Figure 18a: Reboot Warning Message**

|reboot.png|

.. |reboot.png| image:: images/reboot.png

If a scrub or resilver is in progress when a reboot is requested, an additional warning will ask you to make sure that you wish to proceed. In this case, it
is recommended to "Cancel" the reboot request and to periodically run :command:`zpool status` from Shell until it is verified that the scrub or resilver
process is complete. Once complete, the reboot request can be re-issued.

Click the "Cancel" button if you wish to cancel the reboot request. Otherwise, click the "Reboot" button to reboot the system. Rebooting the system will
disconnect all clients, including the web administration GUI. The URL in your web browser will change to add */system/reboot/* to the end of the IP address.
Wait a few minutes for the system to boot, then use your browser's "back" button to return to the FreeNAS® system's IP address. If all went well, you should
receive the GUI login screen. If the login screen does not appear, you will need physical access to the FreeNAS® system's monitor and keyboard so that you
can determine what problem is preventing the system from resuming normal operation.
