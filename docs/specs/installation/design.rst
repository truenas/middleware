:Author: Garrett Cooper
:Date: $Date: 2012-01-13 09:18:22 -0800 (Fri, 13 Jan 2012) $
:Revision: $Rev: 9519 $
:Copyright: BSD Licensed to FreeNAS project (c/o iXsystems, Inc.)

.. contents:: :depth: 2

============
Introduction
============

This document discusses the design and goals for FreeNAS installation
and upgrade system.

Finally, the document will briefly discuss the roadmap items dealing
with installation format and the proposed installation mechanism.

=====
Goals
=====

The installation and updater system is at the core of the FreeNAS
project. It is the first component that the end-user interacts with
when trying to install the FreeNAS distribution and the mechanism
which delivers the distribution to users when updating the system.

=========
Workflows
=========

The included section will first describe the two available workflows
for installing FreeNAS:

   - Interactive installation (.iso) images.
   - Non-interactive installation (.img) images.

Then the document will describe the three available workflows for
upgrading FreeNAS:

   - Interactive installation (.iso) images.
   - GUI Upgrades (GUI_Upgrade) images.
   - Service Packs (Service_Pack) images.

Interactive Installation
========================

Interactive installation is provided via CD ISO images. ISO images
help users choose media to install to and then given the installation
media install the full installation image to the media.

Another purpose that the CD ISO images serve is to assist in upgrading
existing installs by preserving files beforehand and restoring them
after installing the full installation image to the media. This serves
helpful for cases when GUI upgrades have been impossible.

Non-interactive Installation
============================

Non-interactive installation is provided via the .img images
(previously named the Full_Install images). Non-interactive
installation images are dumped to media (typically SATA DOMs, USB,
etc) via programs that can write directly to the media, like dd,
rawrite.exe, etc. No additional intervention is required.

GUI Upgrades
============

GUI upgrades are the most common, but also an expensive -- in terms of
download size -- means of upgrading one's system, as they're effectively
wholesale partitions that are dd'ed out to media for installation via
nanobsd's provided /root/update* scripts (which have been modified to
save/restore FreeNAS specific files). Nevertheless, GUI upgrades are
almost always present and more convenient than CD upgrades, and more
complete than service packs. Plus they offer the ability to switch
between partitions, which service packs do not do.

Service Packs
=============

Service packs provide smaller quantized updates (than the other
available options) that are applied to live systems which are built from
file differences between two full disk images. They have the lowest cost,
but also the largest associated risk if done improperly, as files are
modified on the fly instead of being handled more atomically; the author
thinks that this design needs to be revisited as this is an incredibly
risky way to update a FreeNAS box, and the potential to mess up a FreeNAS
install is higher with this method.

=====================
Helper Infrastructure
=====================

The following section will go over some of the major players in the
install/upgrade infrastructure in an effort to map out what all of the
players do and how they fit into the big installation/upgrade picture.

install.sh
==========

install.sh is the primary driver for the interactive install media
which directs the user through necessary prompts to help determine what
media to install to, whether or not the system should be upgraded, etc.
It also contains a chunk of logic (duplicated to some degree with
/root/update*) for saving data across upgrades, because of the nature
of CD ISO payloads.

It also drives pc-sysinstall to some degree to do its bidding as far as
writing the contents of the full installation image out to the media is
concerned.

It plays a part in the CD media logic.

install_worker
==============

install_worker is a driver of sorts for "stackable" scripts in three
categories:

    - pre-install (validation)
    - install (work)
    - post-install (finishing work)

It was born out of necessity to deal with validating hardware and
software configurations before allowing upgrades to avoid unnecessary
support overhead and PEBKAC issues. The intended purpose for the
script/infrastructure was to do more, such that operations could be
chained together to ensure that things that involved a particular
action (say, saving a driver or not saving a driver) could be simply
tested and added to the scripts which needed to be pulled in.

The other intent was to remove some of the duplication that the author
saw in various installation/update scripts.

It plays a part in all install/upgrade paths apart from the full disk
image.

ix-update
=========

ix-update is the rc.d script which drives the second reboot portion
of the installation process. It's main purpose is to help drive the
southdb migration script via ``manage.py``.

pc-sysinstall
=============

pc-sysinstall is the flexible installer from PCBSD which plays a minor
role in the interactive installer by splatting the contents of the full
installation image on to disk. The author believes that its current
use is not its full capabilities and ultimately it should either be
kept or ditched, as it's not really providing much value in its current
capacity (could be replaced with a couple lines of shell code), but it
could be really beneficial if used more extensively and properly.

It plays a part in the CD media logic.

/root/update
==============

/root/update and friends (/root/updatep1 and /root/updatep2) are
scripts that come prepackaged with nanobsd that have been modified
slightly to meet FreeNAS's needs. All that the scripts really do is
dump a partition image out to disk, copy over files from the current
running system to the other new partition (albeit, blindly today
because -- for example -- kernel modules might not be compatible
across upgrades), and set the active bit to the new partition if
successful.

It plays a part in the GUI upgrade logic.

==============
Longterm Goals
==============

Longterm goals for the FreeNAS project's build system are as follows:

  #. install-v03 branch work

install-v03 Branch Work
=======================

Some of the work the author originally started in branches/install-v03
was to add several missing enhancements and move towards a more
intelligent mechanism for saving/restoring files during upgrades, and
for installing on media.

Some of the goals of the work were the following:

   #. Move away from BSD slices to GPT partitions to avoid the
      complexity associated with trying to setup and manage
      "extended partitions" so additional partitions could be created
      and managed for things like swap, configuration files, or other
      non-FreeNAS specific data.
   #. Convert Full_Install images to tarballs. This would allow
      pc-sysinstall to generate the necessary partition tables and
      labels, then splat the contents of the tarballs on to the install
      media, and verify the install via mtree files to ensure that the
      installation was done successfully and nothing was corrupted.
   #. Add in flexible gmirror/graid support so the install media could
      be redundant to avoid having failures in the install media take
      down the entire system. CF/USB media is great, but SATA DOMs and
      other faster media are generally faster and more reliable.


