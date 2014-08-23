:orphan:

.. _Plugins:

Plugins
=======

FreeNAS® 8.2.0 introduced the ability to extend the built-in NAS services by providing a mechanism for installing additional software. This mechanism was
known as the Plugins architecture and is based on
`FreeBSD jails <http://en.wikipedia.org/wiki/Freebsd_jail>`_
and
`PC-BSD PBIs <http://wiki.pcbsd.org/index.php/AppCafe®/9.2>`_. This allowed users to install and configure additional applications once they had created and
configured a plugins jail.

FreeNAS® 9.x simplifies this procedure by providing two methods for software installation. The Plugins method, described in this section, is meant for users
who prefer to browse for, install, and configure available software using the GUI. This method is very easy to use, but is limited in the amount of software
that is available. Each application will automatically be installed into its own jail, meaning that this method may not be suitable for users who wish to run
multiple applications within the same jail.

The Jails method provides much more control over software installation but assumes that the user is comfortable working from the command line can and has a
good understanding of networking basics and software installation on FreeBSD-based systems.

It is recommended that users skim through both the :ref:`Plugins` and :ref:`Jails` sections in order to become familiar with the features and limitations of
each and to choose the method that best meets their software needs.

Due to ABI (application binary interface) changes, FreeNAS® 8.x PBIs can not be installed on a 9.x system.

.. _Installing Plugins:

Installing Plugins
------------------

A FreeNAS® PBI is a self-contained application installer which has been designed to integrate into the FreeNAS® GUI. A FreeNAS® PBI offers several
advantages:

* the FreeNAS® GUI provides a browser for viewing the list of available FreeNAS® PBIs.

* the FreeNAS® GUI provides buttons for installing, starting, upgrading, and deleting FreeNAS® PBIs.

* if the FreeNAS® PBIs has configuration options, a screen will be added to the FreeNAS® GUI so that these options can be configured from the GUI.

* FreeNAS® PBIs can be installed using either the Plugins or the Jails method.

To install a FreeNAS® PBI using the plugins method, click "Plugins". As seen in Figure 12.1a, the list of available FreeNAS® PBIs will be displayed.

**Figure 12.1a: Using Plugins to Install a PBI**

|Figure121a_png|

.. note:: if the list of available PBIs is not displayed, open Shell and verify that the FreeNAS® system can :command:`ping` an address on the Internet. If
   it cannot, you may have to add a default gateway address and/or DNS server address in :menuselection:`Network --> Global Configuration`.

Highlight the entry of the PBI you would like to install, then click its "Install" button. In the example shown in Figure 12.1b, the transmission PBI is
selected for installation.

**Figure 12.1b: Selecting a PBI to Install**

|Figure121b_png|

Click "OK" to start the installation. It will take a few minutes as the system will first download and configure a jail to contain the installed software. It
will then install the PBI and add it to the "Installed" tab as shown in Figure 12.1c. Be patient as it may take a few minutes for the installation to finish.

**Figure 12.1c: Viewing Installed PBIs**

|Figure121c_png|

As seen in the example shown in Figure 12.1c, entries for the installed PBI will appear in the following locations:

* the "Installed" tab of "Plugins"

* the Plugins section of the tree

* the Jails section of the tree

The entry in the "Installed" tab of Plugins will display the plugin name and version, the name of the PBI that was installed, the name of the jail that was
created, whether the application status is ON or OFF, and a button to delete the application and its associated jail. If a newer version of the application is
available, a button to update the application will also appear.

The "Service status" of a PBI must be turned to "ON" before the installed application is available. Before starting the service, check to see if it has any
configuration options by clicking its entry in the "Plugins" section of the tree. If the application is configurable, this will open a graphical screen that
contains its available configuration options. The options that are available will vary by PBI. PBIs which are not configurable will instead display a message
with a hyperlink for accessing the software. That hyperlink will not work until the PBI is started.

You should always review a PBI's configuration options before attempting to start it as some PBIs have options that need to be set before their service will
successfully start. If you have never configured this application before, check the application's website to see what documentation is available. A link to
the website for each available PBI can be found in Available FreeNAS® PBIs.

If the application requires access to the data stored on the FreeNAS® system, click the entry for the associated jail in the "Jails" section of the tree and
add a storage as described in Adding Storage.

If you need to access the shell of the jail containing the application to complete or test your configuration, click the entry for the associated jail in the
"Jails" section of the tree. You can then click its "shell" icon as described in :ref:`Managing Jails`.

Once the configuration is complete, click the red "OFF" button in the entry for the PBI. If the service successfully starts, it will change to a blue ON. If
it fails to start, click the jail's "shell" icon and type :command:`tail /var/log/messages` to see if any errors were logged.

.. _Updating Plugins:

Updating Plugins
----------------

If a newer version of a FreeNAS® PBI becomes available in the official repository, an "Update" button will be added to the entry of the PBI in the
"Installed" tab. In the example shown in Figure 12.2a, a newer version of Minidlna is available.

**Figure 12.2a: Updating an Installed PBI**

|Figure122a_png|

Click the "OK" button and the latest version of the PBI will automatically be downloaded and installed. Once the update is complete, the entry for the PBI
will be refreshed to show the new version number and the "Update" button will disappear.

.. _Uploading Plugins:

Uploading Plugins
-----------------

The "Available" tab of Plugins contains an "Upload" button. This button allows you to install PBIs that are not yet available in the official repository.
These PBIs include FreeNAS® PBIs which are still being tested as well as
`PC-BSD PBIs <http://pbibuild64.pcbsd.org/index.php?ver=9>`_. These PBIs must be manually downloaded first and should end in a :file:`.pbi` extension. When
downloading a PBI, make sure that it is 64-bit and that it was developed for 9.x. 8.x and 10.x PBIs will not work on a 9.x FreeNAS® system.

Once you have downloaded the PBI, click the "Upload" button. As seen in the example in Figure 12.3a, this will prompt you to browse to the location of the
downloaded PBI. Once the PBI is selected, click the "Upload" button to install the PBI. In this example, the user is installing the PC-BSD PBI for webmin.

**Figure 12.3a: Installing a Previously Downloaded PBI**

|Figure123a_png|

When the installation is complete, an entry for the PBI will be added to the "Installed" tab and its associated jail will be listed under "Jails". However, if
it is not a FreeNAS® PBI, it will not be added to "Plugins". In other words, if the application requires any configuration, you will have to perform it from
the command line of the jail's shell instead of the GUI.

.. _Deleting Plugins:

Deleting Plugins
----------------

When you install a PBI using the Plugins method, an associated jail is created. If you decide to delete a PBI, the associated jail is also deleted as it is no
longer required. **Before deleting a PBI,** make sure that you don't have any data or configuration in the jail that you do not want to lose. If you do, back
it up first, before deleting the PBI.

In the example shown in Figure 12.4a, the CouchPotato PBI has been installed and the user has clicked its "Delete" button. As described in the previous
sections, this PBI appears in the "Plugins" portion of the tree, its associated jail, *couchpotato_1* , appears in the "Jails" portion of the tree, and the
PBI shows as installed in the "Installed" tab of Plugins. A pop-up message asks the user if they are sure that they want to delete.
**This is the one and only warning.** If the user clicks "Yes", this PBI will be removed from the Plugins portion of the tree, its associated jail,
*couchpotato_1*, will be deleted, and the PBI will no longer show as installed in the "Installed" tab of Plugins.

**Figure 12.4a: Deleting an Installed PBI**

|Figure124a_png|

.. _Available Plugins:

Available Plugins
-----------------

Currently, the following FreeNAS® PBIs are available:

* `Bacula (storage daemon) <http://bacula.org/>`_

* `btsync <http://www.bittorrent.com/sync>`_

* `CouchPotato <https://couchpota.to/>`_

* `CrashPlan <http://www.code42.com/crashplan/>`_

* `Firefly <https://en.wikipedia.org/wiki/Firefly_Media_Server>`_

* `Headphones <https://github.com/rembo10/headphones>`_

* `HTPC Manager <http://htpc.io/>`_

* `LazyLibrarian <https://github.com/itsmegb/LazyLibrarian>`_

* `Maraschino <http://www.maraschinoproject.com/>`_

* `MiniDLNA <https://wiki.archlinux.org/index.php/MiniDLNA>`_

* `mylar <https://github.com/evilhero/mylar>`_

* `ownCloud <http://owncloud.org/>`_

* `Plex Media Server <http://www.plexapp.com/>`_

* `SABnzbd <http://sabnzbd.org/>`_

* `Sick Beard <http://sickbeard.com/>`_

* `Subsonic <http://subsonic.org/>`_

* `Transmission <http://www.transmissionbt.com/>`_

* `XDM <https://github.com/lad1337/XDM>`_

While the FreeNAS® Plugins system makes it easy to install a PBI, it is still up to you to know how to configure and use the installed application. When in
doubt, refer to the documentation for that application.
