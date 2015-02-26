.. centered:: Copyright iXsystems 2011-2015

.. centered:: TrueNAS® and the TrueNAS® logo are registered trademarks of iXsystems.

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

* Chapter 3: Initial Setup: this chapter describes how to install the TrueNAS® Storage Appliance, how to configure the out-of-band management port, and
  introduces the console and how to access the graphical administrative interface.

* Chapters 4-14: these chapters cover the configuration options which are available in the TrueNAS® graphical administrative interface. The chapter order
  reflects the order that the configuration options appear within the administrative interface's tree structure. Chapter 4 describes how to create users and
  groups. Chapter 5 describes the tasks that can be accomplished using the System Configuration section of the administrative interface. Chapter 6 describes
  how to schedule regular administrative tasks. Chapter 7 demonstrates the various network configuration options. Chapter 8 deals with managing storage.
  Chapter 9 describes integration with various directory services. Chapter 10 provides examples for creating AFP, CIFS, NFS, WebDAV, and iSCSI shares. Chapter
  11 describes how to configure, start, and stop the built-in services. Chapter 12 provides an overview of the Reporting mechanism. Chapter 13 introduces the
  configuration wizard, and chapter 14 covers the remaining configuration options.

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
