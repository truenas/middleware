:orphan:

|tn_cover.jpg|

.. centered:: Published XX, 2015

.. centered:: Copyright iXsystems 2011-2015

.. centered:: TrueNAS® and the TrueNAS® logo are registered trademarks of iXsystems.

.. centered:: Cover art by Jenny Rosenberg


.. |tn_cover.jpg| image:: images/tn_cover.jpg
    :width: 8.5in
    :height: 11.0in

FreeNAS® and the FreeNAS® logo are registered trademarks of iXsystems.

3ware® and LSI® are trademarks or registered trademarks of LSI Corporation.

Active Directory® is a registered trademark or trademark of Microsoft Corporation in the United States and/or other countries.

Apple, Mac and Mac OS are trademarks of Apple Inc., registered in the U.S. and other countries.

Chelsio® is a registered trademark of Chelsio Communications.

Cisco® is a registered trademark or trademark of Cisco Systems, Inc. and/or its affiliates in the United States and certain other countries.

FreeBSD and the FreeBSD logo are registered trademarks of the FreeBSD Foundation.

Fusion-io is a trademark or registered trademark of Fusion-io, Inc.

Intel, the Intel logo, Pentium Inside, and Pentium are trademarks of Intel Corporation in the U.S. and/or other countries.

Linux® is a registered trademark of Linus Torvalds.

Marvell® is a registered trademark of Marvell or its affiliates.

UNIX® is a registered trademark of The Open Group.

VMWare® is a registered trademark of VMWare, Inc.

Wikipedia® is a registered trademark of the Wikimedia Foundation, Inc., a non-profit organization.

Windows® is a registered trademark of Microsoft Corporation in the United States and other countries.

.. sectnum::

Introduction
------------

Welcome to the TrueNAS® Administrator Guide. This Guide provides information about configuring and managing the TrueNAS® Unified Storage Appliance. Your
iXsystems support engineer will assist with the appliance's initial setup and configuration. Once you are familiar with the configuration workflow, this
document can be used as a reference guide to the many features provided by TrueNAS®.

How This Guide is Organized
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The information in the TrueNAS® Administrator Guide has been organized as follows:

* Chapter 1: Introduction: describes the organization of the guide and the typographic conventions.

* Chapter 2: ZFS Primer: many of the features in the TrueNAS® Storage Appliance rely on the ZFS file system. An overview is provided to familiarize the
  administrator with the terminology and features provided by ZFS.

* Chapter 3: Accessing TrueNAS®: this chapter introduces the console, shows how to access the graphical administrative interface, and introduces the
  initial configuration wizard.

* Chapters 4-13: these chapters cover the configuration options which are available in the TrueNAS® graphical administrative interface. The chapter order
  reflects the order that the configuration options appear within the administrative interface's tree structure. Chapter 5 describes how to create users and
  groups. Chapter 6 describes the tasks that can be accomplished using the System Configuration section of the administrative interface. Chapter 7
  demonstrates the various network configuration options. Chapter 8 deals with storage: how to manage storage volumes, snapshots, and replication. Chapter 9
  provides examples for creating AFP, CIFS, and NFS shares. Chapter 10 describes how to configure and start/stop the built-in services. Chapter 11 provides an
  overview of the Reporting mechanism. Chapter 12 covers the remaining configuration options that appear below the interface's tree structure or which appear
  as icons in the upper right portion of the interface.

* Chapter 14: Upgrading TrueNAS®: this chapter demonstrates how to upgrade the TrueNAS® operating system to a newer version.

* Chapter 15: Using the FreeNAS® API: this chapter demonstrates how to use the FreeNAS® API to remotely control a TrueNAS® system.

**Typographic Conventions**

The TrueNAS® Administrator Guide uses the following typographic conventions:

* Names of graphical elements such as buttons, icons, fields, columns, and boxes are enclosed within quotes. For example: click the "Performance Test" button.

* Menu selections are italicized and separated by arrows. For example: :menuselection:`System --> Information`.

* Commands that are mentioned within text are highlighted in :command:`bold text`. Command examples and command output are contained in green code blocks.

* Volume, dataset, and file names are enclosed in a blue box :file:`/like/this`.

* Keystrokes are formatted in a blue box. For example: press :kbd:`Enter`.

* **bold text:** used to emphasize an important point.

* *italic text:* used to represent device names or text that is input into a GUI field.
