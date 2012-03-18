:Author: Garrett Cooper
:Date: $Date: 2012-01-13 09:18:22 -0800 (Fri, 13 Jan 2012) $
:Revision: $Rev: 9519 $
:Copyright: BSD Licensed to FreeNAS project (c/o iXsystems, Inc.)

.. contents:: :depth: 2

============
Introduction
============

The following document describes the overall ideal process for
performing release engineering in the FreeNAS project, but also
applies to other projects such as TrueNAS.

The document is written with the knowledge of how release engineering
has worked successfully in other groups outside of iXsystems, Inc, but
has also been inspired by documentation provided by Xin Li (delphij).

============
SCM
============

The official source control method employed today is svn, but there has
been discussion of using git instead of svn. When that should be done
and the scoping involved has yet to be determined.

=============
Branch Layout
=============

This section will describe branching as it pertains to FreeNAS, but a
similar document should exist elsewhere that describes how branching
works for other iXsystems sponsored projects.

------------
branches/*
------------

Branches today contains all release train branches as well as
development branches.

Example::

    branches
        |
         ----> 8.0.4
        |
         ----> dev-8.3

The iX repo currently has things laid out as follows::

    branches
        |
         ----> stable-8
    releng
        |
         ----> 8.0.4

The author believes that this methodology (recommended by Xin) makes
more sense and ultimately the repos should mirror one another in this
way. This (the latter case) sort of follows the methodology used in the
FreeBSD project, but not exactly.

------------
tags/*
------------

This is where the tagged releases go. These should be pristine
snapshots of release train branches, e.g. branches/8.0.4 . Using
``svn copy <SRC-URL> <DEST-URL>`` helps one achieve this.

As a sidenote, the author admits that sometimes tagged branches were
modified in the 8.0.4 release cycle to reduce commits and having to
shuffle code around multiple branches with just a few modified knobs,
but in general that behavior is highly discouraged.

------------
trunk
------------

trunk should contain bleeding edge code, but it should be somewhat
baked. This should be used for cutting development branches.

============================
Nightlies and Release Builds
============================

-------------
Preconditions
-------------

   #. One must have a FreeBSD machine setup with cron enabled. Ideally,
      it should be a fast build machine.
   #. One will need to have sudo setup in order to execute the script.

SourceForge Preconditions
-------------------------

   #. One must setup passwordless SSH keys on the build host and upload
      the contents of the .pub file to SourceForge.
   #. One must have release file modification permissions on SF.

-----------------------------
The "end-to-end" build script
-----------------------------

The "end2end-build.sh" script achieves the following things:

   #. Sets up a temporary working directory.
   #. Checks out the source code from SVN.
   #. Runs do_build.sh multiple times to build all targets.
   #. Posts the images to SF. What gets posted varies, depending on
      whether or not all of the builds succeeded.
   #. Generates release notes and posts them to SF.

A similar process is employed for TrueNAS builds.

The intent of the script was to create builds deterministically and post
them to SF.

One of the other benefits is that as long as the preconditions are met

--------
Examples
--------

The following are examples of how to use the script. Please see the
comments at the top of the script for more knobs and dials that can
help you tune the script behavior further.

Nightly Builds (FreeNAS)
------------------------

The following example pulls trunk from SourceForge, runs
``do_build.sh`` for all architectures and for os-base and plugins-base,
then posts the results to SF and
``/freenas/BSD/releng/TrueNAS/nightlies/<date>``::

    /bin/sh /build/automerge/ix/sf-trunk/tools/end2end-build.sh \
        -p /freenas/BSD/releng/FreeNAS/nightlies \
        -T plugins-base


Nightly Builds (TrueNAS)
------------------------

The following example sources
``/build/automerge/ix/ix/tools/end2end-build.ixrc`` (the file contains
some customizations for the iX repo and release process),
pulls the ``ix`` branch, builds only the ``os-base`` and
``plugins-base`` components for amd64, and then posts the results to
``/freenas/BSD/releng/TrueNAS/nightlies/<date>``::

    /bin/sh /build/automerge/ix/sf-trunk/tools/end2end-build.sh \
        -A amd64 -b ix \
        -f /build/automerge/ix/ix/tools/end2end-build.ixrc \
        -p /freenas/BSD/releng/TrueNAS/nightlies \
        -T plugins-base


Release Build (FreeNAS)
-----------------------

The following example demonstrates how one can build the
8.2.0-RELEASE tag; the process that the script uses is similar to
what's described above in `Nightly Builds (FreeNAS)`_, apart from the
fact that the directory that the images are posted to on SF and in
the local directory differs, as well as the image branding (look for
``REVISION`` under ``build/nano_env`` for more details)::

    /bin/sh /build/automerge/ix/sf-trunk/tools/end2end-build.sh \
        -b tags/8.2.0-RELEASE \
        -p /freenas/BSD/releng/FreeNAS/8.2.0 \
        -r \
        -T plugins-base

------------------------------
Cleaning up Old Nightly Builds
------------------------------

One can clean up old nightlies with the clean_builds.py script. An
example for build.ixsystems.com is given below::

    /build/automerge/ix/ix/tools/clean_builds.py \
        /freenas/BSD/releng/FreeNAS/nightlies \
        /freenas/BSD/releng/TrueNAS/nightlies

Another more pertinent example can be found here::

    /build/automerge/ix/ix/tools/clean_builds.py \
        --exclude '*README*' \
        /home/frs/project/f/fr/freenas/FreeNAS-8-nightly

When in doubt use ``-n``!

================
The "AutoMerger"
================

-------------
For Consumers
-------------

This email best describes what the automerger is and how to use it
from a ``consumer`` perspective::

    Date: Mon, 27 Feb 2012 16:26:38 -0800 (PST)
    From: Garrett Cooper <XXXXXXX@ixsystems.com>
    To: XXX@ixsystems.com
    Subject: Automerger: now with branch blacklisting functionality (and more awesomeness)!

    Hi all,
        I committed some code an hour ago to allow filtering of
        particular branches to automerge.sh. So now Do-Not-Merge has
        the following semantics (from the top of the script --
        http://freenas.svn.sf.net/svnroot/freenas/trunk/tools/automerge.sh ):

        """
        This script helps manage merging for multiple target branches. If you
        have a commit that you do not wish to be automatically merged to another
        branch, please use one of the following options:

        Option 1:

        Do-Not-Merge: message

        Option 2:

        Do-Not-Merge (branches/8.2.0,branches/stable-8): message

        Option 1 is a blatant "do not merge me anywhere" tag. Its intent was
        originally to ensure that commits made to SF trunk didn't make it into the
        ix repo automatically.

        Option 2 is a bit more interesting: its intent was to make sure that a
        select set of commits made to a particular branch (say SF trunk) were
        propagated over to the ix repo, but not necessarily other branches (say
        branches/8.2.0). Multiple branches can be specified via a comma-delimited
        list. In the above example, the commit would be propagated anywhere but
        branches/8.2.0 and branches/stable-8

        Please note that 'Do-Not-Merge' must be specified at the start of any
        given line -- not elsewhere in the file.
        """

        So if one wants to avoid merging a change from trunk to the ix
        repo (or anywhere), one can specify 'Do-Not-Merge: <message>'.
        Similarly, if one doesn't want to merge to the ix repo, they
        can use 'Do-Not-Merge (freenas/ix): <message>'. Now, the case
        that we care about. If something really bleeding edge is
        committed to the branches and we don't want to merge it to any
        of the stable branches, it would be something like:
        'Do-Not-Merge (freenas/branches/stable-9,branches/8.2.0)'. As
        an FYI, this is all determined from the following bits on the
        SVN side:

        $ svn info /scratch/f/trunk | egrep '^Repository Root|URL'
        URL: http://freenas.svn.sf.net/svnroot/freenas/trunk
        Repository Root: http://freenas.svn.sf.net/svnroot/freenas

        Basically replace $URL in $RepositoryRoot", and you have your
        relative path :). Here's the info on the automerge directory
        for reference:

        [gcooper@build] ~> svn info /build/automerge/f/trunk/ | egrep '^Repository Root|URL'
        URL: https://freenas.svn.sourceforge.net/svnroot/freenas/trunk
        Repository Root: https://freenas.svn.sourceforge.net/svnroot/freenas
        [gcooper@build] ~> svn info /build/automerge/ix/ix/ | egrep '^Repository Root|URL'
        URL: https://svn.ixsystems.com/projects/freenas/ix
        Repository Root: https://svn.ixsystems.com/projects

        Hopefully that helps describe why things are done the way they
        are, and hopefully the tool will make everyone's lives easier
        and make sure that things are less error prone in the long run.

        ...

    Thanks!
    -Garrett

---------------
For Maintainers
---------------

Preconditions
-------------

You must have committed code to a repo and saved the password in
plaintext to disk (I have no idea why svn doesn't at least password
protect a bit better or use ssh pubkeys..).

Setup
-----

Setting up the automerger between two branches in the same repo or
using an SVN external repo bridge is relatively trivial. The process
from a high level is as follows:

    #. Check out your source and destination repos via svn.
    #. Get repos in synch. Commit hammers and sleuthing might be
       required.
    #. Run
       ``svnrevision <parent-branch> > <child-branch>/.old_version``.
    #. Add a cronjob similar to the following to your crontab::
        /usr/bin/lockf -k -t 600 \
           /build/automerge/f/branches/8.2.0/.old_version \
           /bin/sh /build/automerge/ix/sf-trunk/tools/automerge.sh \
           /build/automerge/f trunk branches/8.2.0

SF->iX
------

The script uses an external SVN tie-in as a bridge in the iX repo to
SF to pull in all of the code and merge stuff around.

Unfortunately the latency is extremely high between SF and iX (or
something like that) and merges failed on a regular basis. Thus, the
_do() function was born to parse out legitimate failures from latency
induced HTTPS transfer failures.

mergeinfo is also lost across the bridging operation because there
isn't a mapping for all commits in both repos, so doublecommitting
code makes the automerger (svn actually) whine about there being
conflicts because svn can't do its job and evaluate whether or not
all code has been committed before.

===============
Release Process
===============

    #. The ReleaseNotes file must be updated before the release is cut.
    #. Edit build/nano_env to rebrand the build and remove the DEBUG
       SW_FEATURE.
    #. Run svn copy with the URL of the source and destination branches
       to copy the sources from trunk to the branches directory, from
       the branches directory to the releng directory, and finally from
       the branches directory to the tags directory.
    #. Execute end2end-build.sh as shown above.
    #. After the Build is Done...
        a. QA needs to qualify the image.
        #. Once QA is done, QA needs to notify all interested parties at
           iXsystems (Dev, Marketing, Production) of the new release
           version if the build meets the release criteria originally
           defined by Dev and Marketing.
        #. Marketing needs to update websites, make announcements, etc as
           necessary.
        #. Support needs to update / close relevant tickets notifying
           end-users of the new release image.

