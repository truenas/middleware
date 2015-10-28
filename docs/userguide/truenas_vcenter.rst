.. index:: vCenter
.. _vCenter:

vCenter
=======

To configure the vCenter plugin, click "vCenter". This will open the screen shown in Figure 14a.

**Figure 14a: Configuring the vCenter Plugin**

.. image:: images/vcenter1.png

Table 14a summarizes the configurable options.

**Table 14a: vCenter Plugin Options**

+-------------------------------+----------------+---------------------------------------------------------------------------------------------------------------------------------------+
| **Setting**                   | **Value**      | **Description**                                                                                                                       |
|                               |                |                                                                                                                                       |
+===============================+================+=======================================================================================================================================+
| TrueNAS Management IP Address | drop-down menu | select the                                                                                                                            |
|                               |                |                                                                                                                                       |
+-------------------------------+----------------+---------------------------------------------------------------------------------------------------------------------------------------+
| vCenter Hostname/IP Address   | string         | input the IP address or resolveable hostname of the vCenter Server                                                                    |
|                               |                |                                                                                                                                       |
+-------------------------------+----------------+---------------------------------------------------------------------------------------------------------------------------------------+
| vCenter Port                  | integer        | input the port number the vCenter Server is listening on                                                                              |
|                               |                |                                                                                                                                       |
+-------------------------------+----------------+---------------------------------------------------------------------------------------------------------------------------------------+
| vCenter Username              | string         | input the username for the vCenter Server                                                                                             |
|                               |                |                                                                                                                                       |
+-------------------------------+----------------+---------------------------------------------------------------------------------------------------------------------------------------+
| vCenter Password              | string         | input the password associated with *vCenter Username*                                                                                 |
|                               |                |                                                                                                                                       |
+-------------------------------+----------------+---------------------------------------------------------------------------------------------------------------------------------------+

In addition, the following buttons are available:

**Install:**

**Uninstall:**

**Upgrade:**

**Repair:**

To configure the vCenter plugin to use a secure connection, click :menuselection:`vCenter --> vCenter Auxiliary Settings` in the left tree. In the screen shown in Figure 14b, check the
"Enable vCenter Plugin over https" box.

**Figure 14b: Securing the vCenter Plugin Connection**

.. image:: images/vcenter2.png


