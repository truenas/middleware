.. index:: Plugin
.. _Plugins:

Plugins
=======

If the TrueNAS® system has been licensed for jails, the "Plugins" and "Jails" icons will be added to the graphical administrative interface. These icons allow the administrator to extend
the built-in TrueNAS® services by providing a mechanism for installing additional software. This mechanism is based on `FreeBSD jails <https://en.wikipedia.org/wiki/Freebsd_jail>`_ and
`PC-BSD 9.x PBIs <http://wiki.pcbsd.org/index.php/AppCafe%C2%AE/9.2>`_. 

A jails-licensed TrueNAS® system provides two methods for software installation. The Plugins method, described in this section, is meant for users
who prefer to browse for, install, and configure available software using the GUI. This method is easy to use, but is limited in the amount of software
that is available. Each application will automatically be installed into its own jail, meaning that this method is not suitable for users who wish to run
multiple applications within the same jail.

The Jails method provides much more control over software installation but assumes that the user is comfortable working from the command line can and has a
good understanding of networking basics and software installation on FreeBSD-based systems.

It is recommended that users skim through both the :ref:`Plugins` and :ref:`Jails` sections in order to become familiar with the features and limitations of
each and to choose the method that best meets their software needs.

.. _Installing Plugins:

Installing Plugins
------------------

A plugin is a self-contained application installer which has been designed to integrate into the TrueNAS® GUI. A plugin offers several advantages:

* the TrueNAS® GUI provides a browser for viewing the list of available plugins

* the TrueNAS® GUI provides buttons for installing, starting, managing, and deleting plugins

* if the plugin has configuration options, a screen will be added to the TrueNAS® GUI so that these options can be configured from the GUI

To install a plugin, click "Plugins". As seen in :numref:`Figure %s: Viewing the List of Available Plugins <plugins1>`, the list of available plugins will be displayed.

.. _plugins1:

.. figure:: images/plugins1.png

.. note:: if the list of available plugins is not displayed, open :ref:`Shell` and verify that the TrueNAS® system can :command:`ping` an address on the
   Internet. If it cannot, you may have to add a default gateway address and/or DNS server address in :menuselection:`Network --> Global Configuration`.

Highlight the plugin you would like to install, click its "Install" button, then click "OK". In the example shown in :numref:`Figure %s: Installing a Plugin <plugins2>`, SABnzbd is selected
for installation.

.. _plugins2:

.. figure:: images/plugins2.png

The installation will take a few minutes as the system will first download and configure a jail to contain the installed software. It will then install the
plugin and add it to the "Installed" tab as shown in :numref:`Figure %s: Viewing Installed PBIs <plugins3>`.

.. warning:: be patient and wait for the installation to finish. Navigating away from the installation before it is finished will cause problems with the
   installation.

.. _plugins3:

.. figure:: images/plugins3.png

As seen in the example shown in :numref:`Figure %s: Viewing Installed PBIs <plugins3>`, entries for the installed PBI will appear in the following locations:

* the "Installed" tab of "Plugins"

* the "Plugins" section of the tree

* the "Jails" section of the tree

The entry in the "Installed" tab of Plugins will display the plugin name and version, the name of the PBI that was installed, the name of the jail that was
created, whether the application status is "ON" or "OFF", and a button to delete the application and its associated jail. If a newer version of the
application is available as a plugin, a button to update the application will also appear.

.. note:: the "Service status" of a plugin must be turned to "ON" before the installed application is available. Before starting the service, check to see if
   it has a configuration menu by clicking its entry in the "Plugins" section of the tree. If the application is configurable, this will open a graphical
   screen that contains the available configuration options. Plugins which are not configurable will instead display a message with a hyperlink for accessing
   the software. However, that hyperlink will **not work** until the plugin is started.

You should always review a plugin's configuration options before attempting to start it. some plugins have options that need to be set before their service
will successfully start. If you have never configured that application before, check the application's website to see what documentation is available. A link
to the website for each available plugin can be found in :ref:`Available Plugins`.

If the application requires access to the data stored on the TrueNAS® system, click the entry for the associated jail in the "Jails" section of the tree and
add a storage as described in :ref:`Add Storage`.

If you need to access the shell of the jail containing the application to complete or test your configuration, click the entry for the associated jail in the
"Jails" section of the tree. You can then click its "shell" icon as described in :ref:`Managing Jails`.

Once the configuration is complete, click the red "OFF" button for the entry for the plugin. If the service successfully starts, it will change to a blue 
"ON". If it fails to start, click the jail's "shell" icon and type :command:`tail /var/log/messages` to see if any errors were logged.

.. _Updating Plugins:

Updating Plugins
----------------

When a newer version of a plugin becomes available in the official repository, an "Update" button is added to the entry for the plugin in the "Installed" tab.
In the example shown in :numref:`Figure %s: Updating an Installed Plugin <plugins4>`, a newer version of Transmission is available.

.. _plugins4:

.. figure:: images/plugins4.png

Click the "OK" button to start the download and installation of the latest version of the plugin. Once the update is complete, the entry for the plugin will
be refreshed to show the new version number and the "Update" button will disappear.

.. _Uploading Plugins:

Uploading Plugins
-----------------

The "Available" tab of "Plugins" contains an "Upload" button. This button allows you to install plugins that are not yet available in the official repository
or which are still being tested. These plugins must be manually downloaded and should end in a :file:`.pbi` extension. When downloading a plugin, make sure
that it is 64-bit and that it was developed for 9.x. as 8.x and 10.x applications will not work on a 9.x TrueNAS® system.

Once you have downloaded the plugin, click the "Upload" button. As seen in the example in :numref:`Figure %s: Installing a Previously Downloaded *.pbi File <plugins5>`, this will prompt you
to browse to the location of the downloaded file. Once selected, click the "Upload" button to begin the installation.

.. _plugins5:

.. figure:: images/plugins5.png

When the installation is complete, an entry for the plugin will be added to the "Installed" tab and its associated jail will be listed under "Jails". However,
if it is not a TrueNAS® plugin, it will not be added to "Plugins" in the tree. In this case, if the application requires any configuration, you will have to
perform it from the command line of the jail's shell instead of from the GUI.

.. _Deleting Plugins:

Deleting Plugins
----------------

When you install a plugin, an associated jail is created. If you decide to delete a plugin, the associated jail is also deleted as it is no longer required.
**Before deleting a plugin,** make sure that you do not have any data or configuration in the jail that you need to save. If you do, back up that data first,
**before** deleting the plugin.

In the example shown in :numref:`Figure %s: Deleting an Installed Plugin <plugins6>`, Sabnzbd has been installed and the user has clicked its "Delete" button. A pop-up message asks the user
if they are sure that they want to delete. **This is the one and only warning.** If the user clicks "Yes", the plugin and the associated jail will be permanently deleted.

.. _plugins6:

.. figure:: images/plugins6.png

.. _Available Plugins:

Available Plugins
-----------------

The following plugins are available for TrueNAS®:

* `bacula-sd (storage daemon) <http://bacula.org/>`_

* `BTSync <https://www.getsync.com/>`_

* `CouchPotato <https://couchpota.to/>`_

* `crashplan <http://www.code42.com/crashplan/>`_

* `cruciblewds <http://cruciblewds.org/>`_

* `Emby <http://emby.media/>`_

* `firefly <https://en.wikipedia.org/wiki/Firefly_Media_Server>`_

* `Headphones <https://github.com/rembo10/headphones>`_

* `HTPC-Manager <http://htpc.io/>`_

* `Maraschino <http://www.maraschinoproject.com/>`_

* `MineOS <http://minecraft.codeemo.com/>`_

* `Mylar <https://github.com/evilhero/mylar>`_

* `owncloud <https://owncloud.org/>`_

* `plexmediaserver <https://plex.tv/>`_

* `s3cmd <http://s3tools.org/s3cmd>`_

* `SABnzbd <http://sabnzbd.org/>`_

* `SickBeard <http://sickbeard.com/>`_

* `SickRage <https://github.com/SiCKRAGETV/SickRage>`_

* `Sonarr <https://sonarr.tv/>`_

* `Subsonic <http://www.subsonic.org/pages/index.jsp>`_

* `Syncthing <https://syncthing.net/>`_

* `transmission <http://www.transmissionbt.com/>`_

* `XDM <https://github.com/lad1337/XDM>`_

While the TrueNAS® Plugins system makes it easy to install software, it is still up to you to know how to configure and use the installed application. When
in doubt, refer to the documentation for that application.
