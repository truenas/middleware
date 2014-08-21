:orphan:

Contributing to FreeNAS®
=========================

As an open source community, FreeNAS® relies on the input and expertise of its users to help improve FreeNAS®. When you take some time to assist the
community, your contributions benefit everyone who uses FreeNAS®.

This section describes some areas of participation to get you started. It is by no means an exhaustive list. If you have an idea that you think would benefit
the FreeNAS® community, bring it up on one of the resources mentioned in FreeNAS® Support Resources.

This section demonstrates how you can:

* `Report a Bug`_

* `Localize`_

* `Beta Test`_

Report a Bug
------------

If you encounter a traceback error when using FreeNAS® or suspect that you have found a software or documentation bug, go to
`https://bugs.freenas.org/projects/freenas <https://bugs.freenas.org/projects/freenas>`_
to see if your issue has already been reported. You do not need to register in order to search for existing issues. However, you will need to register if you
wish to comment on an existing issue or create a new support issue.

Before creating a new issue, take the time to research your bug or feature request first. This is to prevent duplicating an existing issue and to ensure that
your report contains the information that the developers need in order to implement the fix or the feature.

As part of your research, perform the following steps:

* Determine if you are running the latest release of FreeNAS®. FreeNAS® developers tend to fix bugs rapidly and new features are being implemented as
  FreeNAS® matures. If you are not running the latest version, it is quite likely that the bug has already been fixed or the missing feature has been
  implemented. If this is the case, your best course of action is to backup your data and configuration and perform an upgrade to the latest version.

* If you are running the latest version, use the search feature to see if a similar issue already exists. If one does, do not create a new issue. Instead,
  add a comment to the existing issue if you have additional information to add.

If a similar issue does not already exist, keep the following points in mind as you create a new issue:

#.  You will need to register for an account, confirm you registration email address, and be logged in before you can create a new issue.

#.  In the Tracker drop-down menu, select *Bug* if you are reporting a bug or
    *Feature* if you are making a feature request.

#.  In the "Subject" field, include descriptive keywords that describe the issue. This is useful for other users who search for a similar problem.

#.  In the "Description" section, describe the problem, how to recreate it, and include the text of any error messages. If you are requesting a feature,
    describe the benefit provided by the feature and, if applicable, provide examples of other products that use that feature or the URL of the homepage for
    the software.

#.  If you would like to include a screenshot or log of your configuration or error, use the "Browse" button next to the "Files" field to upload the file.

#.  Leave all of the other fields at their default values as these are used by developers as they take action on the issue.

#.  Press the "Preview" link to read through your ticket before submitting it. Make sure it includes all of the information that someone else would need to
    understand your problem or request. Once you are satisfied with your ticket, click the "Create Ticket" button to submit it.

An email will automatically be sent to the address you used when registering whenever a comment or action occurs on your issue.

Localize
---------

FreeNAS® uses
`Pootle <http://en.wikipedia.org/wiki/Pootle>`_, an open source application, for managing the localization of the menu screens used by the FreeNAS® graphical
administrative interface. Pootle makes it easy to find out the localization status of your native language and to translate the text for any menus that have
not been localized yet. By providing a web editor and commenting system, Pootle allows translators to spend their time making and reviewing translations
rather than learning how to use a translation submission tool.

To see the status of a localization, open
`pootle.freenas.org <http://pootle.freenas.org/>`_
in your browser, as seen in Figure 24.2a:

**Figure 24.2a: FreeNAS® Localization System**

|10000000000003E0000002624E582DF2_png|

.. |10000000000003E0000002624E582DF2_png| image:: images/10000000000003E0000002624E582DF2.png
    :width: 6.9252in
    :height: 3.272in

The localizations FreeNAS® users have requested are listed alphabetically on the left. If your language is missing and you would like to help in its
translation, send an email to the
`translations mailing list <http://lists.freenas.org/mailman/listinfo/freenas-translations>`_
so it can be added.

The green bar in the Overall Completion column indicates the percentage of FreeNAS® menus that have been localized. If a language is not at 100%, it means
that the menus that currently are not translated will appear in English instead of in that language.

If you wish to help localize your language, you should first join the
`translations mailing list <http://lists.freenas.org/mailman/listinfo/freenas-translations>`_
and introduce yourself and which language(s) you can assist with. This will allow you to meet other volunteers as well as keep abreast of any notices or
updates that may effect the translations. You will also need to click on the "Register" link in order to create a Pootle login account.

The first time you log into the FreeNAS® Pootle interface, you will be prompted to select your language so that you can access that language's translation
whenever you login. Alternately, you can click the "Home" link to see the status of all of the languages. To work on a translation, click the link for the
language, click the FreeNAS® link for the project, click the link for "LC_MESSAGES", and click the link for "django.po". Every text line available in the GUI
menu screens has been assigned a string number. If you click the number, an editor will open where you can translate the text. In the example shown in Figure
24.2b, a user has selected string number 46 in the German translation; the other strings in the screenshot have already been translated:

**Figure 24.2b: Using the Pootle Interface to Edit a Translation String**

|100000000000047B00000232CA1DFA0A_png|

.. |100000000000047B00000232CA1DFA0A_png| image:: images/100000000000047B00000232CA1DFA0A.png
    :width: 6.9252in
    :height: 3.3929in

Simply type in the translated text and click the "Submit" button to save your change.

Beta Test
---------

Prior to any release, there is a beta period where testing snapshots will be announced on the FreeNAS® website and social media sites. This beta period is
meant to provide users an opportunity to test the upcoming release and to provide feedback on bugs and errors so that they can be fixed prior to release.
Feedback can be sent to the
`Freenas-testing mailing list <http://lists.freenas.org/mailman/listinfo/freenas-testing>`_
or a bug report can be submitted.

Rolling a Custom Snapshot
~~~~~~~~~~~~~~~~~~~~~~~~~

Users who wish to create their own custom ISO for testing purposes can download and compile the latest FreeNAS® source from the github repository.

In order to build your own testing snapshot, you will need to install the amd64 version of
`FreeBSD 9.3 <http://www.freebsd.org/releases/9.3R/announce.html>`_
in a virtual environment or on a test system. If you are using a virtual environment, a 64-bit system with at least 4 GB of RAM is recommended. Installation
intructions can be found
`here <http://www.freebsd.org/doc/en_US.ISO8859-1/books/handbook/bsdinstall.html>`_.

After booting into the newly installed FreeBSD system, become the superuser (type :command:`su` and enter the *root* user's password) and run the following
commands. First, install the software you'll need and refresh your path so it is aware of the new binaries::

 pkg_add -r git-subversion
 pkg_add -r cdrtools
 pkg_add -r python27
 pkg_add -r pbi-manager
 rehash

Change to the directory where you would like to store the FreeNAS® source, download the source, then change to the directory containing the downloaded
source::

 cd /path/to/your-build-filesystem
 git clone git://github.com/freenas/freenas.git
 cd freenas

You are now ready to build the image using the instructions in this
`README <https://github.com/freenas/freenas>`_.
