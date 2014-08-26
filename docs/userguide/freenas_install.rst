:orphan:

.. _Installing and Upgrading FreeNAS®:

Installing and Upgrading FreeNAS®
==================================

Before installing, it is important to remember that the FreeNAS® operating system must be installed on a separate device from the drive(s) that will hold the
storage data. In other words, if you only have one disk drive you will be able to use the FreeNAS® graphical interface but won't be able to store any data,
which after all, is the whole point of a NAS system. If you are a home user who is experimenting with FreeNAS®, you can install FreeNAS® on an inexpensive
USB thumb drive and use the computer's disk(s) for storage.

This section describes the following:

* :ref:`Getting FreeNAS®`

* :ref:`Virtualization`

* :ref:`Installing from CDROM`

* :ref:`Burning a USB Stick`

* :ref:`Initial Setup`

* :ref:`Troubleshooting`

* :ref:`Initial Setup`

* :ref:`Upgrading`

.. _Getting FreeNAS®:

Getting FreeNAS®
-----------------

FreeNAS® 9.3 can be downloaded from
`http://download.freenas.org/ <http://download.freenas.org/>`_.

The download page contains the following types of files. Download one file that meets your needs:

* **CD Installer:** this is a bootable installer that can be written to CDROM. This is described in more detail in Installing from CDROM.

* **Disk Image:** this is a compressed image of the operating system that needs to be written to a USB or compact flash device. Burning an IMG File
  describes how to write the image.

* **GUI Upgrade:** this is a compressed firmware upgrade image. If your intent is to upgrade FreeNAS®, download this file and see the section on
  :ref:`Upgrading`.

Each file has an associated SHA256 hash which should be used to verify the integrity of the downloaded file before writing it to the installation media. The
command you use to verify the checksum varies by operating system:

* on a BSD system use the command :command:`sha256 name_of_file`

* on a Linux system use the command :command:`sha256sum name_of_file`

* on a Mac system use the command :command:`shasum -a 256 name_of_file`

* on a Windows system or Mac system, you can install a utility such as
  `HashCalc <http://www.slavasoft.com/hashcalc/>`_
  or
  `HashTab <http://implbits.com/HashTab.aspx>`_

.. _Virtualization:

Virtualization
--------------

FreeNAS can be run inside a virtual environment for development, experimentation, and educational purposes. Please note that running FreeNAS in production as
a virtual machine is
`not recommended <http://forums.freenas.org/showthread.php?12484-Please-do-not-run-FreeNAS-in-production-as-a-Virtual-Machine%21>`_.
If you decide to use FreeNAS® within a virtual environment,
`read this post first <http://forums.freenas.org/showthread.php?12714-quot-Absolutely-must-virtualize-FreeNAS%21-quot-a-guide-to-not-completely-losing-your-data>`_
as it contains useful guidelines for minimizing the risk of losing your data.

In order to install or run FreeNAS® within a virtual environment, you will need to create a virtual machine that meets the following minimum requirements:

* **at least** 2048 MB base memory size (UFS) or 4096 MB (ZFS)

* a virtual disk **at least 2 GB in size** to hold the operating system and swap

* at least one more virtual disk **at least 4 GB in size** to be used as data storage

* a bridged adapter

This section demonstrates how to create and access a virtual machine within the VirtualBox and VMware ESXi environments.

.. _VirtualBox:

VirtualBox
~~~~~~~~~~

`VirtualBox <http://www.virtualbox.org/>`_
is an open source virtualization program originally created by Sun Microsystems. VirtualBox runs on Windows, BSD, Linux, Macintosh, and OpenSolaris. It can be
configured to use a downloaded FreeNAS® :file:`.iso` or :file:`.img.xz` file, and makes a good testing environment for practicing configurations or learning
how to use the features provided by FreeNAS®.

To create the virtual machine, start VirtualBox and click the "New" button, seen in Figure 2.2a, to start the new virtual machine wizard.

**Figure 2.2a: Initial VirtualBox Screen**

|virtualbox1.png|

.. |virtualbox1.png| image:: images/virtualbox1.png
    :width: 6.9252in
    :height: 3.6335in


Click the "Next" button to see the screen in Figure 2.2b. Enter a name for the virtual machine, click the "Operating System" drop-down menu and select BSD,
and select "FreeBSD (64-bit)" from the "Version" dropdown.

**Figure 2.2b: Type in a Name and Select the Operating System for the New Virtual Machine**

|virtualbox2.png|

.. |virtualbox2.png| image:: images/virtualbox2.png
    :width: 5.4626in
    :height: 3.6665in

Click "Next" to see the screen in Figure 2.2c. The base memory size must be changed to **at least 2048 MB**.
**If your system has enough memory, select at least 4096 MB so that you can use ZFS**. When finished, click "Next" to see the screen in Figure 2.2d.

**Figure 2.2c: Select the Amount of Memory Reserved for the Virtual Machine**

|virtualbox3.png|

.. |virtualbox3.png| image:: images/virtualbox3.png
    :width: 5.4626in
    :height: 3.6665in

**Figure 2.2d: Select Whether to Use an Existing or Create a New Virtual Hard Drive**

|virtualbox4.png|

.. |virtualbox4.png| image:: images/virtualbox4.png
    :width: 5.4626in
    :height: 3.6665in

Click "Create" to launch the "Create Virtual Hard Drive Wizard" shown in Figure 2.2e.

**Figure 2.2e: Create New Virtual Hard Drive Wizard**

|virtualbox5.png|

.. |virtualbox5.png| image:: images/virtualbox5.png
    :width: 6.361in
    :height: 4.1417in

Select one of the following types:

* **VDI:** select this option if you downloaded the ISO.

* **VMDK:** select this option if you converted the :file:`.img` file to VMDK format using the instructions in Running FreeNAS® from a USB Image.

Once you make a selection, click the "Next" button to see the screen in Figure 2.2f.

**Figure 2.2f: Select the Storage Type for the Virtual Disk**

|virtualbox6.png|

.. |virtualbox6.png| image:: images/virtualbox6.png
    :width: 6.361in
    :height: 4.1417in

You can now choose whether you want "Dynamically allocated" or "Fixed-size" storage. The first option uses disk space as needed until it reaches the
maximum size that you will set in the next screen. The second option creates a disk the same size as that specified amount of disk space, whether it is used
or not. Choose the first option if you are worried about disk space; otherwise, choose the second option as it allows VirtualBox to run slightly faster. Once
you select "Next", you will see the screen in Figure 2.2g.

**Figure 2.2g: Select the File Name and Size of the Virtual Disk**

|virtualbox7.png|

.. |virtualbox7.png| image:: images/virtualbox7.png
    :width: 5.9783in
    :height: 4.6035in

This screen is used to set the size (or upper limit) of the virtual machine. **Increase the default size to 2 or 4 GB**. Use the folder icon to browse to a
directory on disk with sufficient space to hold the virtual machine.

Once you make your selection and press "Next", you will see a summary of your choices. Use the "Back" button to return to a previous screen if you need to
change any values. Otherwise, click "Finish" to finish using the wizard. The virtual machine will be listed in the left frame, as seen in the example in
Figure 2.2h.

**Figure 2.2h: The New Virtual Machine**

|virtualbox8.png|

.. |virtualbox8.png| image:: images/virtualbox8.png
    :width: 6.361in
    :height: 4.8083in

Next, create the virtual disk(s) to be used for storage. Click the "Storage" hyperlink in the right frame to access the storage screen seen in Figure
2.2i.

**Figure 2.2i: The Storage Settings of the Virtual Machine**

|virtualbox9.png|

.. |virtualbox9.png| image:: images/virtualbox9.png
    :width: 6.9252in
    :height: 4.3807in

Click the "Add Attachment" button, select "Add Hard Disk" from the pop-up menu, then click the "Create New Disk" button. This will launch the Create New 
Virtual Hard Drive Wizard (seen in Figures 2.2e and 2.2f). Since this disk will be used for storage, create a size appropriate to your needs, making sure that
it is **at least 4 GB** in size. If you wish to practice RAID configurations, create as many virtual disks as you need. You will be able to create 2 disks on
the IDE controller. If you need additional disks, click the "Add Controller" button to create another controller to attach disks to.

Next, create the device for the installation media. If you will be installing from an ISO, highlight the word "Empty", then click the "CD" icon as seen in
Figure 2.2j.

**Figure 2.2j: Configuring the ISO Installation Media**

|virtualbox10.png|

.. |virtualbox10.png| image:: images/virtualbox10.png
    :width: 6.9252in
    :height: 3.6602in

Click "Choose a virtual CD/DVD disk file..." to browse to the location of the :file:`.iso` file. Alternately, if you have burned the :file:`.iso` to disk,
select the detected "Host Drive".

Depending upon the extensions available in your CPU, you may or may not be able to use the ISO. If you receive the error "your CPU does not support long
mode" when you try to boot the ISO, your CPU either does not have the required extension or AMD-V/VT-x is disabled in the system BIOS.

.. note:: if you receive a kernel panic when booting into the ISO, stop the virtual machine. Then, go to System and check the box "Enable IO APIC".

To configure the network adapter, go to :menuselection:`Settings --> Network`. In the "Attached to" drop-down menu select "Bridged Adapter", then select the
name of the physical interface from the "Name" drop-down menu. In the example shown in Figure 2.2k, the Intel Pro/1000 Ethernet card is attached to the
network and has a device name of *re0*.

Once your configuration is complete, click the "Start" arrow. If you configured the ISO, install FreeNAS® as described in Installing from CDROM. Once
FreeNAS® is installed, press "F12" to access the boot menu in order to select the primary hard disk as the boot option. You can permanently boot from disk by
removing the CD/DVD device in "Storage" or by unchecking CD/DVD-ROM in the "Boot Order" section of "System".

If you configured the VMDK, the virtual machine will boot directly into FreeNAS®.

**Figure 2.2k: Configuring a Bridged Adapter in VirtualBox**

|virtualbox11.png|

.. |virtualbox11.png| image:: images/virtualbox11.png
    :width: 6.8634in
    :height: 5.1138in

.. _Using the VMDK:

Using the VMDK
^^^^^^^^^^^^^^

Once you have a :file:`.vmdk` file, create a new virtual machine while the USB stick is inserted. When you get to Figure 2.2e, select "Use existing hard disk"
and browse to your :file:`.vmdk` file. Click "Next", then "Create". This will create the virtual machine and bring you to Figure 2.2h. You can then create
your storage disks and bridged adapter as usual. When finished, start the virtual machine and it will boot directly into FreeNAS®.

.. _VMware ESXi:

VMware ESXi
~~~~~~~~~~~

If you are considering using ESXi, read
`this post <http://forums.freenas.org/threads/sync-writes-or-why-is-my-esxi-nfs-so-slow-and-why-is-iscsi-faster.12506/>`_
for an explanation of why iSCSI will be faster than NFS.

ESXi is is a bare-metal hypervisor architecture created by VMware Inc. Commercial and free versions of the VMware vSphere Hypervisor operating system (ESXi)
are available from the
`VMware website <http://www.vmware.com/products/vsphere/esxi-and-esx/>`_. Once the operating system is installed on supported hardware, use a web browser to
connect to its IP address. The welcome screen will provide a link to download the VMware vSphere client which is used to create and manage virtual machines.

Once the VMware vSphere client is installed, use it to connect to the ESXi server. To create a new virtual machine, click :menuselection:`File --> New -->
Virtual Machine`. The New Virtual Machine Wizard will launch as seen in Figure 2.2l.

Click "Next" and input a name for the virtual machine. Click "Next" and highlight a datastore. An example is shown in Figure 2.2m. Click "Next". In the screen
shown in Figure 2.2n, click "Other" then select a FreeBSD architecture that matches the FreeNAS® architecture.

**Figure 2.2l: New Virtual Machine Wizard**

|esxi1.png|

.. |esxi1.png| image:: images/esxi1.png
    :width: 6.9252in
    :height: 4.1in

**Figure 2.2m: Select a Datastore**

|esxi2.png|

.. |esxi2.png| image:: images/esxi2.png
    :width: 6.9252in
    :height: 4.1in

**Figure 2.2n: Select the Operating System**

|esxi3.png|

.. |esxi3.png| image:: images/esxi3.png
    :width: 6.9252in
    :height: 4.1in

Click "Next" and create a virtual disk file of **2 GB** to hold the FreeNAS® operating system, as shown in Figure 2.2o.

Click "Next" then "Finish". Your virtual machine will be listed in the left frame. Right-click the virtual machine and select "Edit Settings" to access the
screen shown in Figure 2.2p.

Increase the "Memory Configuration" to **at least 2048 MB**.

Under "CPUs", make sure that only 1 virtual processor is listed, otherwise you will be unable to start any FreeNAS® services.

To create a storage disk, click :menuselection:`Hard disk 1 --> Add`. In the "Device Type" menu, highlight "Hard Disk" and click "Next". Select "Create a new
virtual disk" and click "Next". In the screen shown in Figure 2.2q, select the size of the disk. If you would like the size to be dynamically allocated as
needed, check the box "Allocate and commit space on demand (Thin Provisioning)". Click "Next", then "Next", then "Finish" to create the disk. Repeat to create
the amount of storage disks needed to meet your requirements.

**Figure 2.2o: Create a Disk for the Operating System**

|esxi4.png|

.. |esxi4.png| image:: images/esxi4.png
    :width: 6.7957in
    :height: 3.8472in

**Figure 2.2p: Virtual Machine's Settings**

|esxi5.png|

.. |esxi5.png| image:: images/esxi5.png
    :width: 6.7346in
    :height: 4.3146in

**Figure 2.2q: Creating a Storage Disk**

|esxi6.png|

.. |esxi6.png| image:: images/esxi6.png
    :width: 6.7925in
    :height: 5.3339in

.. _Installing from CDROM:

Installing from CDROM
---------------------

If you prefer to install FreeNAS® using a menu-driven installer, download either the :file:`.iso` file and burn it to a CDROM.

.. note:: the installer on the CDROM will recognize if a previous version of FreeNAS® is already installed, meaning the CDROM can also be used to upgrade
   FreeNAS®. However, the installer can not perform an upgrade from a FreeNAS® .7 system.

Insert the CDROM into the system and boot from it. Once the media has finished booting, you will be presented with the console setup menu seen in Figure 2.3a.

.. note:: if the installer does not boot, check that the CD drive is listed first in the boot order in the BIOS. Some motherboards may require you to connect
   the CDROM to SATA0 (the first connector) in order to boot from CDROM. If it stalls during boot, check the SHA256 hash of your ISO against that listed in
   the Release Notes; if the hash does not match, re-download the file. If the hash is correct, try burning the CD again at a lower speed.

**Figure 2.3a: FreeNAS® Console Setup**

|Figure23a_png|

Press :kbd:`Enter` to select the default option of "1 Install/Upgrade to hard drive/flash device, etc.". The next menu, seen in Figure 2.3b, will list all
available drives, including any inserted USB thumb drives which will begin with *da*. In this example, the user is installing into VirtualBox and has created
a 4 GB virtual disk to hold the operating system.

.. note:: at this time, the installer does not check the size of the install media before attempting an installation. A 2 GB device is required, but the
   install will appear to complete successfully on smaller devices, only to fail at boot. If using a USB thumb drive, an 4 GB drive is recommended as many 2
   GB thumb drives have a smaller capacity which will result in a seemingly successful installation that fails to boot.

Use your arrow keys to highlight the USB, compact flash device, or virtual disk to install into, then tab to "OK" and press :kbd:`Enter`. FreeNAS® will issue
the warning seen in Figure 2.3c, reminding you not to install onto a storage drive.

Press :kbd:`Enter` and FreeNAS® will extract the image from the ISO and transfer it to the device. Once the installation is complete, you should see a
message similar to Figure 2.3d.

Press :kbd:`Enter` to return to the first menu, seen in Figure 2.3a. Highlight "3 Reboot System" and press :kbd:`Enter`. Remove the CDROM. If you installed
onto a USB thumb drive, leave the thumb drive inserted. Make sure that the device you installed to is listed as the first boot entry in the BIOS so that the
system will boot from it. FreeNAS® should now be able to boot into the Console setup menu described in `Initial Setup`_.

**Figure 2.3b: Selecting Which Drive to Install Into**

|cdrom2.png|

.. |cdrom2.png| image:: images/cdrom2.png
    :width: 5.8228in
    :height: 3.0335in


**Figure 2.3c: FreeNAS® Installation Warning**

|cdrom3.png|

.. |cdrom3.png| image:: images/cdrom3.png
    :width: 6.9252in
    :height: 2.5709in

**Figure 2.3d: FreeNAS® Installation Complete**

|cdrom4.png|

.. |cdrom4.png| image:: images/cdrom4.png
    :width: 6.911in
    :height: 1.9783in

.. _Burning a USB Stick:

Burning a USB Stick
-------------------

If your system does not have a CDROM drive to install from, you can instead write the operating system directly to a compact flash card or USB thumbdrive.
Download the :file:`img.xz` file, uncompress the file, and write it to a compact flash card or USB thumbdrive that is 2 GB or larger. You then boot into that
device to load the FreeNAS® operating system. This section demonstrates how to write the image using several different operating systems. The Unetbootin tool
is not supported at this time.

.. warning:: The :command:`dd` command demonstrated in this section is very powerful and can destroy any existing data on the specified device. Be
   **very sure** that you know the device name to write to and that you do not typo the device name when using :command:`dd`! If you are uncomfortable writing
   the image yourself, download the :file:`.iso` file instead and use the instructions in Installing from CDROM.

Once you have written the image to the device, make sure the boot order in the BIOS is set to boot from that device and boot the system. It should boot into
the Console setup menu described in Initial Setup. If it does not, try the suggestions in :ref:`Troubleshooting`.

.. _On FreeBSD or Linux:

On FreeBSD or Linux
~~~~~~~~~~~~~~~~~~~

On a FreeBSD or Linux system, the :command:`xzcat` and :command:`dd` commands can be used to uncompress and write the :file:`.xz` image to an inserted USB
thumb drive or compact flash device. Example 2.4a demonstrates writing the image to the first USB device (*/dev/da0*) on a FreeBSD system. Substitute the
filename of your :file:`.xz` file and the device name representing the device to write to on your system.

**Example 2.4a: Writing the Image to a USB Thumb Drive**
::
 xzcat FreeNAS-9.3-RELEASE-x64.img.xz | dd of=/dev/da0 bs=64k
 0+244141 records in
 0+244141 records out
 2000000000 bytes transferred in 596.039857 secs (3355480 bytes/sec)

When using the :command:`dd` command:

* **of=** refers to the output file; in our case, the device name of the flash card or removable USB drive. You may have to increment the number in the name
  if it is not the first USB device. On Linux, use */dev/sdX,* where *X* refers to the letter of the USB device.

* **bs=** refers to the block size

.. _On OS X:

On OS X
~~~~~~~

On an OS X system, you can download and install
`Keka <http://www.kekaosx.com/en/>`_
to uncompress the image. In FINDER, navigate to the location where you saved the downloaded :file:`.xz` file. Right-click the :file:`.xz` file and select
"Open With Keka". After a few minutes you will have a large file with the same name, but no :file:`.xz` extension.

Insert the USB thumb drive and go to :menuselection:`Launchpad --> Utilities --> Disk Utility`. Unmount any mounted partitions on the USB thumb drive. Check
that the USB thumb drive has only one partition, otherwise you will get partition table errors on boot. If needed, use Disk Utility to setup one partition on
the USB drive; selecting "free space" when creating the partition works fine.

Next, determine the device name of the inserted USB thumb drive. From TERMINAL, navigate to your Desktop then type this command::

 diskutil list
 /dev/disk0

 #:	TYPE NAME		SIZE		IDENTIFIER
 0:	GUID_partition_scheme	*500.1 GB	disk0
 1:	EFI			209.7 MB	disk0s1
 2:	Apple_HFS Macintosh HD	499.2 GB	disk0s2
 3:	Apple_Boot Recovery HD	650.0 MB	disk0s3

 /dev/disk1
 #:	TYPE NAME		SIZE		IDENTIFIER
 0:	FDisk_partition_scheme	*8.0 GB		disk1
 1:	DOS_FAT_32 UNTITLED	8.0 GB		disk1s1

This will show you which devices are available to the system. Locate your USB stick and record the path. If you are not sure which path is the correct one for
the USB stick, remove the device, run the command again, and compare the difference. Once you are sure of the device name, navigate to the Desktop from
TERMINAL, unmount the USB stick, and use the :command:`dd` command to write the image to the USB stick. In Example 2.4b, the USB thumb drive is */dev/disk1*.
Substitute the name of your uncompressed file and the correct path to your USB thumb drive.

**Example 2.4b: Using :command:`dd` on an OS X System**
::

 diskutil unmountDisk /dev/disk1
 Unmount of all volumes on disk1 was successful

 dd if=FreeNAS-9.3-RELEASE-x64.img of=/dev/disk1 bs=64k

.. note:: if you get the error "Resource busy" when you run the :command:`dd` command, go to :menuselection:`Applications --> Utilities --> Disk Utility`,
   find your USB thumb drive, and click on its partitions to make sure all of them are unmounted. If you get the error "dd: /dev/disk1: Permission denied",
   run the :command:`dd` command by typing :command:`sudo dd if=FreeNAS-9.3-RELEASE-x64.img of=/dev/disk1 bs=64k`, which will prompt for your password.

The :command:`dd` command will take some minutes to complete. Wait until you get a prompt back and a message that displays how long it took to write the image
to the USB drive.

.. _On Windows:

On Windows
~~~~~~~~~~

Windows users will need to download a utility that can uncompress :file:`.xz` files and a utility that can create a USB bootable image from the uncompressed
:file:`.img` file.

This section will demonstrate how to use
`7-Zip <http://www.7-zip.org/>`_
and
`Win32DiskImager <https://launchpad.net/win32-image-writer>`_
to burn the image file. When downloading Win32DiskImager, download the latest version that ends in :file:`-binary.zip` and use 7-Zip to unzip its executable.

Once both utilities are installed, launch the 7-Zip File Manager and browse to the location containing your downloaded :file:`.img.xz` file, as seen in Figure
2.4a.

**Figure 2.4a: Using 7-Zip to Extract Image File**

|Figure24a_png|

Click the "Extract" button, browse to the path to extract to, and click "OK". The extracted image will end in :file:`.img` and is now ready to be written to a
USB device using Win32DiskImager.

Next, launch Win32DiskImager, shown in Figure 2.4b. Use the "browse" button to browse to the location of the :file:`.img` file. Insert a USB thumb drive and
select its drive letter from the Device drop-down menu. Click the "Write" button and the image will be written to the USB thumb drive.

**Figure 2.4b: Using Win32DiskImager to Write the Image**

|Figure24b_png|

.. _Troubleshooting:

Troubleshooting
---------------

If the system does not boot into FreeNAS®, there are several things that you can check to resolve the situation.

First, check the system BIOS and see if there is an option to change the USB emulation from CD/DVD/floppy to hard drive. If it still will not boot, check to
see if the card/drive is UDMA compliant.

Some users have found that some brands of 2 GB USB sticks do not work as they are not really 2 GB in size, but changing to a 4 GB stick fixes the problem.

If you are writing the image to a compact flash card, make sure that it is MSDOS formatted.

If the system starts to boot but hangs with this repeated error message:

run_interrupt_driven_hooks: still waiting after 60 seconds for xpt_config

go into the system BIOS and see if there is an onboard device configuration for a 1394 Controller. If so, disable the device and try booting again.

If the burned image fails to boot and the image was burned using a Windows system, wipe the USB stick before trying a second burn using a utility such as
`Active@ KillDisk <http://how-to-erase-hard-drive.com/>`_. Otherwise, the second burn attempt will fail as Windows does not understand the partition which was
written from the image file. Be very careful that you specify the USB stick when using a wipe utility!

.. _Initial Setup:

Initial Setup
-------------

When you boot into FreeNAS®, the Console Setup, shown in Figure 2.6a, will appear at the end of the boot process. If you have access to the the FreeNAS®
system's keyboard and monitor, this Console Setup menu can be used to administer the system should the administrative GUI become inaccessible.

.. note:: you can access the Console Setup menu from within the FreeNAS® GUI by typing
   :command:`/etc/netcli` from Shell. You can disable the Console Setup menu by unchecking the "Enable Console Menu" in :menuselection:`System --> Advanced`.

**Figure 2.6a: FreeNAS® Console Setup Menu**

|console1.png|

.. |console1.png| image:: images/console1.png
    :width: 5.9154in
    :height: 3.0835in

This menu provides the following options:

**1) Configure Network Interfaces:** provides a configuration wizard to configure the system's network interfaces.

**2) Configure Link Aggregation:** allows you to either create a new link aggregation or to delete an existing link aggregation.

**3) Configure VLAN Interface:** used to create or delete a VLAN interface.

**4) Configure Default Route:** used to set the IPv4 or IPv6 default gateway. When prompted, input the IP address of the default gateway.

**5) Configure Static Routes:** will prompt for the destination network and the gateway IP address. Re-enter this option for each route you need to add.

**6) Configure DNS:** will prompt for the name of the DNS domain then the IP address of the first DNS server. To input multiple DNS servers, press
:kbd:`Enter` to input the next one. When finished, press :kbd:`Enter` twice to leave this option.

**7) Reset WebGUI login credentials:** if you are unable to login to the graphical administrative interface, select this option. The next time the graphical
interface is accessed, it will prompt to set the *root* password.

**8) Reset to factory defaults:** if you wish to delete
**all** of the configuration changes made in the administrative GUI, select this option. Once the configuration is reset, the system will reboot. You will
need to go to :menuselection:`Storage --> Volumes --> Auto Import Volume` to re-import your volume.

**9) Shell:** enters a shell in order to run FreeBSD commands. To leave the shell, type
:command:`exit`.

**10) Reboot:** reboots the system.

**11) Shutdown:** halts the system.

During boot, FreeNAS® will automatically try to connect to a DHCP server from all live interfaces. If it successfully receives an IP address, it will display
the IP address which can be used to access the graphical console. In the example seen in Figure 2.6a, the FreeNAS® system is accessible from
*http://192.168.1.70*.

If your FreeNAS® server is not connected to a network with a DHCP server, you can use the network configuration wizard to manually configure the interface as
seen in Example 2.6a. In this example, the FreeNAS® system has one network interface (*em0*).

**Example 2.6a: Manually Setting an IP Address from the Console Menu**
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

.. _Set the Root Password:

Set the Root Password
~~~~~~~~~~~~~~~~~~~~~

Once the system has an IP address, input that address into a graphical web browser from a computer capable of accessing the network containing the FreeNAS®
system. You should be prompted to create a password for the *root* user, as seen in Figure 2.6b.

**Figure 2.6b: Set the Root Password**

|Figure26b_png|

Setting a password is mandatory and the password can not be blank. Since this password provides access to the administrative GUI, it should be a hard-to-guess
password. Once the password has been input and confirmed, you should see the administrative GUI as shown in the example in Figure 2.6c.

**Figure 2.6c: FreeNAS® Graphical Configuration Menu**

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

.. _Upgrading:

Upgrading
---------

FreeNAS® provides two methods for performing an upgrade: an ISO upgrade or an upgrade using the graphical administrative interface. Unless the Release Notes
indicate that your current version requires an ISO upgrade, you can use either upgrade method. Both methods are described in this section.

**Before performing an upgrade, always backup your configuration file and your data.**

When upgrading, **be aware of the following caveats:**

* Neither upgrade method can be used to migrate from FreeNAS 0.7x. Instead, install FreeNAS® and either auto-import supported software RAID or import
  supported filesystems. You will need to recreate your configuration as the installation process will not import 0.7 configuration settings.

.. _Initial Preparation:

Initial Preparation
~~~~~~~~~~~~~~~~~~~

Before upgrading the system, perform the following steps:

#.  `Download <http://www.freenas.org/download-releases.html>`_
    the :file:`.iso` or :file:`.txz` file that matches the system's architecture to the computer that you use to access the FreeNAS® system.

#.  Locate and confirm the SHA256 hash for the file that you downloaded in the Release Notes for the version that you are upgrading to.

#.  **Backup the FreeNAS® configuration** in :menuselection:`System --> General --> Save Config`.

#.  If any volumes are encrypted, make sure that you have set the passphrase and have copies of the encryption key and the latest recovery key.

#.  Warn users that the FreeNAS® shares will be unavailable during the upgrade; you should schedule the upgrade for a time that will least impact users.

#.  Stop all services in :menuselection:`Services --> Control Services`.

.. _Upgrading from CDROM:

Upgrading from CDROM
~~~~~~~~~~~~~~~~~~~~

Burn the downloaded :file:`.iso` file to a CDROM.

Insert the CDROM into the system and boot from it. Once the media has finished booting into the installation menu, press :kbd:`Enter` to select the default
option of "1 Install/Upgrade to hard drive/flash device, etc." As with a fresh install, the installer will present a screen showing all available drives;
select the device FreeNAS® is installed into and press :kbd:`Enter`.

The installer will recognize that an earlier version of FreeNAS® is installed on the device and will present the message shown in Figure 2.7a.

.. note:: if you select to perform a "Fresh Install", you will have to restore the backup of your configuration.

To perform an upgrade, press :kbd:`Enter` to accept the default of "Upgrade Install". Again, the installer will remind you that the operating system should be
installed on a thumb drive. Press :kbd:`Enter` to start the upgrade. Once the installer has finished unpacking the new image, you will see the menu shown in
Figure 2.7b. The database file that is preserved and migrated contains your FreeNAS® configuration settings.

Press :kbd:`Enter` and FreeNAS® will indicate that the upgrade is complete and that you should reboot, as seen in Figure 2.7c.

**Figure 2.7a: Upgrading a FreeNAS® Installation**

|upgrade1.png|

.. |upgrade1.png| image:: images/upgrade1.png
    :width: 5.9327in
    :height: 3.1917in

**Figure 2.7b: FreeNAS® will Preserve and Migrate Settings**

|upgrade2.png|

.. |upgrade2.png| image:: images/upgrade2.png
    :width: 6.9252in
    :height: 3.8134in

During the reboot there may be a conversion of the previous configuration database to the new version of the database. This happens during the "Applying
database schema changes" line in the reboot cycle. This conversion can take a long time to finish so be patient and the boot should complete normally. If
for some reason you end up with database errors but the graphical administrative interface is accessible, go to :menuselection:`Settings --> General` and use
the "Upload Config" button to upload the configuration that you saved before you started the upgrade.

**Figure 2.7c: Upgrade is Complete**

|upgrade3.png|

.. |upgrade3.png| image:: images/upgrade3.png
    :width: 6.9252in
    :height: 2.4161in

.. _Upgrading From the GUI:

Upgrading From the GUI
~~~~~~~~~~~~~~~~~~~~~~

To perform an upgrade using this method,
`download <http://www.freenas.org/download-releases.html>`_
the latest version of the :file:`.txz` file. Then, go to :menuselection:`System --> Advanced --> Firmware Update` as shown in Figure 2.7d.

Use the drop-down menu to select an existing volume to temporarily place the firmware file during the upgrade. Alternately, select "Memory device" to
allow the system to create a temporary RAM disk to be used during the upgrade. After making your selection, click the "Apply Update" button to see the screen
shown in Figure 2.7e.

This screen again reminds you to backup your configuration before proceeding. If you have not yet, click the "click here" link.

Browse to the location of the downloaded :file:`.txz` file, then paste its SHA256 sum.

When finished, click the "Apply Update" button to begin the upgrade progress. Behind the scenes, the following steps are occurring:

* the SHA256 hash is confirmed and an error will display if it does not match; if you get this error, double-check that you pasted the correct checksum and
  try pasting again

* the new image is uncompressed and written to the USB compact or flash drive; this can take a few minutes so be patient

* once the new image is written, you will momentarily lose your connection as the FreeNAS® system will automatically reboot into the new version of the
  operating system

* FreeNAS® will actually reboot twice: once the new operating system loads, the upgrade process applies the new database schema and reboots again

* assuming all went well, the FreeNAS® system will receive the same IP from the DHCP server; refresh your browser after a moment to see if you can access
  the system

**Figure 2.7d: Upgrading FreeNAS® From the GUI**

|Figure27d_png|

**Figure 2.7e: Step 2 of 2**

|Figure27e_png|

.. _Unlocking an Encrypted Volume:

Unlocking an Encrypted Volume
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If your disks are encrypted and you have created a passphrase and saved the recovery key, the volume will automatically be locked during an upgrade. This is
to prevent an unauthorized user from using an upgrade procedure to gain access to the data on the encrypted disks. After the upgrade, the locked volumes will
be unavailable until they are unlocked with the passphrase and recovery key.

To unlock the volume, go to :menuselection:`Storage --> Volumes --> View Volumes` and highlight the locked volume. As seen in Figure 2.7f, clicking the
"Unlock" icon will prompt for the passphrase or recovery key. You can also select which services to start when the volume is unlocked.

**Figure 2.7f: Unlocking an Encrypted Volume**

|Figure27f_png|

.. _If Something Goes Wrong:

If Something Goes Wrong
~~~~~~~~~~~~~~~~~~~~~~~

If the FreeNAS® system does not become available after the upgrade, you will need physical access to the system to find out what went wrong. From the console
menu you can determine if it received an IP address and use option "1) Configure Network Interfaces" if it did not.

If this does not fix the problem, go into option "9) Shell" and read the system log with this command::

 more /var/log/messages

If the database upgrade failed, a file called :file:`/data/upgrade-failed` should be created with the details.

If the problem is not obvious or you are unsure how to fix it, see FreeNAS® Support Resources.

FreeNAS® supports two operating systems on the operating system device: the current operating system and, if you have performed an upgrade, the previously
installed version of the operating system. This allows you to reboot into the previous version should you experience a problem with the upgraded version.

The upgrade process automatically configures the system to boot from the new operating system. If the system remains inaccessible and you wish to revert back
to the previous installation, type :command:`reboot` from the shell or select "10) Reboot" from the console menu. Watch the boot screens and press the other
boot option (typically "F2") from the FreeNAS® console when you see the following options at the very beginning of the boot process. In this example,
"Boot: F1" refers to the default option (the newly upgraded version), so pressing "F2" will boot into the previous version.::

 F1 FreeBSD
 F2 FreeBSD
 Boot: F1

.. note:: if a previously working FreeNAS® system hangs after a FreeNAS® upgrade, check to see if there is a BIOS/BMC firmware upgrade available as that
   may fix the issue.

If the upgrade completely fails, don't panic. The data is still on your disks and you still have a copy of your saved configuration. You can always:

#.  Perform a fresh installation.

#.  Import your volumes in :menuselection:`Storage --> Auto Import Volume`.

#.  Restore the configuration in :menuselection:`System --> General --> Upload Config`.

.. _Upgrading a ZFS Pool:

Upgrading a ZFS Pool
~~~~~~~~~~~~~~~~~~~~

Beginning with FreeNAS® 9.3, ZFS pools can be upgraded from the graphical administrative interface.

Before upgrading an existing ZFS pool, be aware of the following caveats first:

* the pool upgrade is a one-way street meaning that **if you change your mind you can not go back to an earlier ZFS version** or downgrade to an earlier
  version of FreeNAS® that does not support feature flags.

* before performing any operation that may affect the data on a storage disk, **always backup your data first and verify the integrity of the backup.**
  While it is unlikely that the pool upgrade will affect the data, it is always better to be safe than sorry.

To perform the ZFS pool upgrade, go to :menuselection:`Storage --> Volumes --> View Volumes` and highlight the volume (ZFS pool) to upgrade. Click the
"Upgrade" button as seen in Figure 2.7g.

**Figure 2.7g: Upgrading a ZFS Pool**

|Figure27g_png|

The warning message will remind you that a pool upgrade is irreversible. Click "OK" to proceed with the upgrade.

The upgrade itself should only take a seconds and is non-disruptive. This means that you do not need to stop any sharing services in order to upgrade the
pool. However, you should choose to upgrade when the pool is not being heavily used. The upgrade process will suspend I/O for a short period, but should be
nearly instantaneous on a quiet pool.