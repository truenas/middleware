.. index:: Shutdown
.. _Shutdown:

Shutdown
========

If you click the "Shutdown" entry in the tree, you will receive the warning message shown in Figure 19a and your browser color will change to red to indicate
that you have selected an option that will negatively impact users of the FreeNAS® system.

**Figure 19a: Shutdown Warning Message**

|shutdown.png|

.. |shutdown.png| image:: images/shutdown.png
    :width: 6.0in
    :height: 1.9in

If a scrub or resilver is in progress when a shutdown is requested, an additional warning will ask you to make sure that you wish to proceed. In this case, it
is recommended to "Cancel" the shutdown request and to periodically run :command:`zpool status` from :ref:`Shell` until it is verified that the scrub or
resilver process is complete. Once complete, the shutdown request can be re-issued.

Click the "Cancel" button if you wish to cancel the shutdown request. Otherwise, click the "Shutdown" button to halt the system. Shutting down the system will
disconnect all clients, including the web administration GUI, and will power off the FreeNAS® system. You will need physical access to the FreeNAS® system
in order to turn it back on.

