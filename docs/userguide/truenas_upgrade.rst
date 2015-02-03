:orphan:

Upgrading TrueNAS®
-------------------

TrueNAS® provides two methods for performing an upgrade: a GUI upgrade (preferred) and an upgrade using IPMI and ISO redirection. This section describes how
to upgrade using the preferred GUI method.

Preparing for the Upgrade
^^^^^^^^^^^^^^^^^^^^^^^^^

Before upgrading the system to 9.3, perform the following steps:

#.  Download the file with the :file:`.txz` extension from
    `ftp://ftp.he.ixsystems.com/ <ftp://ftp.he.ixsystems.com/>`_, using your support username and password.

#.  Confirm the SHA256 hash for the file that you downloaded.

#.  Backup the TrueNAS® configuration in `System --> Settings --> General --> Save Config`.

#.  If any volumes are encrypted, make sure that you have set the passphrase and have copies of the encryption key and the latest recovery key as described in
    `Creating an Encrypted Volume`_.

#.  Warn users that the TrueNAS® shares will be unavailable during the upgrade; you should schedule the upgrade for a time that will least impact users.

#.  Stop all services in `Services --> Control Services`.

.. note:: when upgrading a HA unit, you
   **must** first upgrade the passive node. In Step 1 of the GUI upgrade, you
   **must** select "Memory device" for the "Place to temporarily place firmware file". Once the update on the passive node is complete, it cannot sync
   configuration changes until the active node is upgraded, so adding an NFS share to the active node is a very bad idea. Next, upgrade the active node. Once
   the active node reboots after the upgrade, the passive node will become active on the new image.

Performing the Upgrade
^^^^^^^^^^^^^^^^^^^^^^

To perform the upgrade, go to `System --> Settings --> Advanced --> Firmware Update` as shown in Figure 13.1a.

Use the drop-down menu to select an existing volume to temporarily place the firmware file during the upgrade. Alternately, of if this is the passive node of
a HA unit, select "Memory device" to allow the system to create a temporary RAM disk to be used during the upgrade. After making your selection, click the
"Apply Update" button to see the screen shown in Figure 13.1b.

**Figure 13.1a: Step 1 of Upgrade**

|100000000000017F00000171394D6770_png|

.. |100000000000017F00000171394D6770_png| image:: images/upgrade1.png
    :width: 8in
    :height: 5in

**Figure 13.1b: Step 2 of Upgrade**

|100000000000020A000001039D4BB7A7_png|

.. |100000000000020A000001039D4BB7A7_png| image:: images/upgrade2.png
    :width: 4.3862in
    :height: 2.1583in

This screen again reminds you to backup your configuration before proceeding. If you have not yet, click the "click here" link.

Browse to the location of the downloaded :file:`.txz` file, then paste its SHA256 sum.

When finished, click the "Apply Update" button to begin the upgrade progress. Behind the scenes, the following steps are occurring:

*   the SHA256 hash is confirmed and an error will display if it does not match; if you get this error, double-check that you pasted the correct checksum and
    try pasting again

*   the new image is uncompressed and written; this can take a few minutes so be patient

*   once the new image is written, you will momentarily lose your connection as the TrueNAS® system will automatically reboot into the new version of the
    operating system

*   TrueNAS® will actually reboot twice: once the new operating system loads, the upgrade process applies the new database schema and reboots again

*   assuming all went well, the TrueNAS® system will receive the same IP from the DHCP server; refresh your browser after a moment to see if you can access
    the system

Unlocking an Encrypted Volume
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If your disks are encrypted and you have created a passphrase and saved the recovery key, the volume will automatically be locked during an upgrade. This is
to prevent an unauthorized user from using an upgrade procedure to gain access to the data on the encrypted disks. After the upgrade, the locked volumes will
be unavailable until they are unlocked with the passphrase and recovery key.

To unlock the volume, go to `Storage --> Volumes --> View Volumes` and highlight the locked volume. As seen in Figure 13.1c, clicking the "Unlock" icon will
prompt for the passphrase or recovery key. You can also select which services to start when the volume is unlocked.

**Figure 13.1c: Unlocking an Encrypted Volume**

|1000000000000335000002980DC4880B_png|

.. |1000000000000335000002980DC4880B_png| image:: images/unlock.png
    :width: 6.8992in
    :height: 5.5335in

If Something Goes Wrong
^^^^^^^^^^^^^^^^^^^^^^^

If an update fails, an alert will be issued and the details will be written to :file:`/data/update.failed`.

If the TrueNAS® system does not become available after the upgrade, use IPMI or the physical console of the system to find out what went wrong. From the
console menu you can determine if it received an IP address and use option "1) Configure Network Interfaces" if it did not.

If this does not fix the problem, go into option "9) Shell" and read the system log with this command::

 more /var/log/messages

If the database upgrade failed, a file called :file:`/data/upgrade-failed` should be created with the details.

If the problem is not obvious or you are unsure how to fix it, contact your iXsystems support engineer.

TrueNAS® supports two operating systems on the operating system device: the current operating system and, if you have performed an upgrade, the previously
installed version of the operating system. This allows you to reboot into the previous version should you experience a problem with the upgraded version.

The upgrade process automatically configures the system to boot from the new operating system. If the system remains inaccessible and you wish to revert back
to the previous installation, type :command:`reboot` from the shell or select "10) Reboot" from the console menu. Watch the boot screens and press the other
boot option (typically *F2*) from the TrueNAS® console when you see the following options at the very beginning of the boot process. In this example,
*Boot: F1* refers to the default option (the newly upgraded version), so pressing
*F2* will boot into the previous version.::

 F1 FreeBSD
 F2 FreeBSD
 Boot: F1

If the upgrade completely fails, don't panic. The data is still on your disks and you still have a copy of your saved configuration. You can always:

#.  Perform a fresh installation.

#.  Import your volumes in `Storage --> Auto Import Volume`.

#.  Restore the configuration in `System --> Settings --> Upload Config`.

.. note:: you cannot restore a saved configuration which is newer than the installed version. For example, if you reboot into an older version of the
          operating system, you cannot restore a configuration that was created in a later version.

Upgrading a ZFS Pool
^^^^^^^^^^^^^^^^^^^^

The upgrade process will **not** automatically upgrade the version of existing ZFS pools. iXsystems recommends to wait a few weeks to ensure that the upgrade
went smoothly before upgrading the pools.

Before upgrading the existing ZFS pools, be aware of the following caveats:

*   the ZFS version upgrade must be performed from the command line, it can not be performed using the GUI.

*   the pool upgrade is a one-way street meaning that **if you change your mind you can not go back to an earlier ZFS version** or downgrade to an earlier
    version of TrueNAS®.

To perform the ZFS version upgrade, open `Shell`_.

First, verify that the status of all of the pools is healthy::

 zpool status -x
 all pools are healthy

.. note:: do not upgrade the pool if its status does not show as healthy.

Then, upgrade the pools::

 zpool upgrade -a

The upgrade itself should only take a seconds and is non-disruptive. This means that you do not need to stop any sharing services in order to upgrade the
pool. However, you should choose to upgrade when the pool is not being heavily used. The upgrade process will suspend I/O for a short period, but should be
nearly instantaneous on a quiet pool.