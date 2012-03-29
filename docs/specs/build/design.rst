:Author: Garrett Cooper
:Date: $Date: 2012-01-13 09:18:22 -0800 (Fri, 13 Jan 2012) $
:Revision: $Rev: 9519 $
:Copyright: BSD Licensed to FreeNAS project (c/o iXsystems, Inc.)

.. contents:: :depth: 2

============
Introduction
============

This document discusses the design and goals for FreeNAS build system.
The document will note the technologies in use and the components in the
system.

=====
Goals
=====

The goals of the FreeNAS build system are the following items:

  #. Builds must be repeatable.
  #. Builds must be environment and system agnostic.
  #. Builds must fail when needed.
  #. Build failures must provide enough information for developers and
     release engineers to root-cause the source of failure.

==============
Basic Workflow
==============

The basic workflow of the end to end build process for custom
OS distributions that the author has worked with, is typically as
follows:

  #. Pull sources
     i. Pull distribution sources
  #. Bootstrap the base OS and third-party sources
  #. Patch base OS and third-party sources
  #. Build distribution
     i. Build and install base OS
     #. Build and install third party packages
     #. Overlay Install with project specific files
     #. Create bootable images

The following sections will describe how things are done from the
FreeNAS build system in more gross detail.

Pull Sources
============

The official method for pulling sources for FreeNAS are from the
`SourceForge SVN repository <https://sourceforge.net/scm/?type=svn&group_id=151951>`.
There are alternate ways (e.g. git) to pull the sources for FreeNAS as
described in the README, but they're not official [yet] as they aren't
documented and would interrupt existing processes with the legacy
portion of the FreeNAS project.

Bootstrap OS and Third-Party Sources
====================================

The ``do_build.sh`` script handles the bootstrapping process and invokes
the build process via nanobsd. The high level process is as follows:

   #. Prerequisite steps
   #. Pull src and ports from svn and ports, respectively
   #. Patch the src and ports trees pulled
   #. Invoke nanobsd

Appropriate flags are passed to ``nanobsd.sh`` to avoid rebuilding
FreeBSD from scratch to optimize iterative builds; which flags are
passed is determined by inspecting sentinel files provided by nanobsd.
One can provide appropriate flags to tailor the behavior to manually
build the system or pull and patch the system, as well as provide them
directly to nanobsd.

Building
==================

Building the FreeNAS distribution via nanobsd is split into several
pieces:

  * Defining project agnostic infrastructure (nanobsd/common)
  * Pulling in project/target customizations (nanobsd/os-base)
  * Building and installing the base OS
  * Building and installing third-party packages
  * Adding in infrastructure required by project (gui, middleware, etc)
  * Build install images and media

Building the plugins-base component is split into the following pieces:

  * Defining project agnostic infrastructure (nanobsd/common)
  * Pulling in plugins base customizations (nanobsd/plugins-base)
  * Building and installing the base OS
  * Building and installing third-party packages
  * Building the plugins base PBI

Project Agnostic Infrastructure
-------------------------------

The nanobsd/common file defines common infrastructure for driving the
nanobsd build infrastructure available in FreeBSD. It should contain
components, macros, etc which can be used in several dissimilar projects
(e.g. BSD Router project, FreeNAS, pfSense, etc) and make targets;
ultimately the components in nanobsd/common are candidates for
inclusion in the base nanobsd build infrastructure or in the
`Avatar <https://gitorious.org/avatar-bsd/avatar-bsd>`_ project.

Examples of what are contained in this file are generic glue that
handles chrooting, package building, installation, etc.

Project Customizations
----------------------

build/nano_env defines [mostly] project specific knobs for how the
project should be built (in reality the project generic bits should
be moved into a different layer, e.g. avatar_env, etc so it can be
used with multiple projects). Because of the way that nanobsd is
written (many values are hardcoded in nanobsd.sh and overridden by
the callers), nano_env is naively sourced multiple times during the
course of the entire build: once from build/do_build.sh, once from
nanobsd/freenas_common, and subsequently from standalone scripts,
such as build/create_iso.sh, etc. In reality this sourceable script
should be split into two scripts to drive the the lowest common
denominator in a manner similar to bsd.port.pre.mk and
bsd.port.post.mk, etc so pieces like SVNVERSION don't need to be
determined more than once.

nano_env should contain components which define:

  #. How kernel should be built.
  #. How world should be built.
  #. The name of the project.
  #. Other ``common`` pieces that are relevant to multiple dissimilar
     projects, e.g. support website, project specific tools that can be
     built on demand, etc.

nanobsd/os-base defines how the FreeNAS ``base OS distro`` will be built
and differentiates the project (in this case FreeNAS) from other
nanobsd based projects (BSD Router project, pfSense, etc).

Building and Installing the Base OS
-----------------------------------

The base OS is built via nanobsd's build_world and build_kernel
functions. It is then installed via the install_world, install_etc,
setup_nanobsd_etc, and install_kernel.

Building and installing third-party packages
--------------------------------------------

Third-party packages are either built if needed and installed via the
add_port function defined in nanobsd/common . The package is built if it
does not already exist. The package name is determined via the
``make package`` command.

Overlay Install with Project Files
----------------------------------

The image 'overlay' process and initial 'install' state creation
process is handled by customize_cmd macros defined in nanobsd/os-base
and -- finally -- freenas_custom in nanobsd/os-base (this is where the
initial configuration database is generated).

Create Install Images and Media
-------------------------------

Full disk install media is initially created via the
create_${ARCH}_diskimage function. The full install media and GUI
upgrade images are compressed and the ISO image is created in
last_orders (nanobsd/os-base).

==============
Longterm Goals
==============

Longterm goals for the FreeNAS project's build system are as follows:

  #. Decrease iterative build times.
  #. Integrate plugins building into the build system.
  #. Make create_*_image/create_iso.sh use makefs.
  #. Cross-build the entire system.
  #. Convert pre-built FreeNAS workspaces into SDKs.

Decrease Iterative Build Times
==============================

All image building was pushed into last_orders in an effort to
streamline building all images, but this increases iterative image
builds by approximately 10 minutes per image on fast machines. This
slows down development and hacking.

A simple interface needs to be devised for specifying which images
need to be built, logic needs to be added to do_build.sh to invoke
nanobsd properly (-i or no -i), and tuning of the images needs to
be added to the os-base file.

The work wasn't performed prior to this writing because the ideas
devised seemed hacky and nasty.

Integrate Plugins Building
==========================

Plugins building is all done ad hoc today outside of the build system,
which introduces non-determinism into building plugins. Some of the
preliminary work for making plugins deterministic was started in
r10559 by being able to specify absolute paths to abitrary nanobsd
customization scripts, but the following layout was considered better
than the current layout (it just wasn't implemented to avoid churn
before 8.2.0)::


  build/...
     .../conf/...
         # 'nanobsd/common' today.
         .../nanobsd-common
         # All plugins specific nanobsd goo will go here.
         .../plugins-common
     .../nanobsd/...
         .../nanobsd.sh

  # 'nanobsd' today
  os-base/...
     # 'obj.amd64' before.
     .../amd64/...
     .../dist/...
         # 'nanobsd/Files' today.
     .../nanobsd/...
         # 'nanobsd/os-base' today
         .../build
         .../FREENAS.i386
         .../FREENAS.amd64
     .../src/...
         .../installer/...

  plugins-base/...
     .../amd64/...
     .../nanobsd/...
         # 'nanobsd/plugins-base' today
         .../build
     .../dist/...
         .../etc/...
             .../rc.conf

The intent behind this structuring is to make the way that files are
laid out in the sourcebase (and ultimately outside of it) more sane as
the current model (examples/..., nanobsd/...) doesn't make sense and
ultimately won't scale longterm as the number of components (plugins,
etc) that are integrated into FreeNAS grows.

Cross-build the entire system
=============================

Let's face it, CR and fake_target_host are nasty hacks, and won't work
when compiling on incompatible architectures (amd64 on mips, powerpc on
arm, etc).

First off, the ports system needs to be enhanced to deal with ``canadian
cross`` setups, in particular set the needed bits for autoconf to
cross-compile, and accept both TARGET and HOST environment variables
(CC, CPP, CFLAGS, CPPFLAGS, etc).

Ports can be fixed to properly cross-build outside the ports tree. This
is a huge task, but doable. All build dependencies that are required
for build time must be built potentially twice -- once for the host
system and another for the target system. The packages for the host
will need to be installed to a predefined location and suffixed in
$PATH appropriately.

Make create_*_image/create_iso.sh use makefs
============================================

makefs is the wave of the future and making create_iso.sh and
nanobsd.sh use makefs will reduce some of the dd+mdconfig+cdrtools
dancing that the above scripts use.

The only warning the author has about using makefs is watch out for
ISO-9660 compliance bugs with certain versions of makefs.

Convert FreeNAS Workspaces into SDKs
====================================

One of the skunkworks projects the author performed one weekend was to
determine how difficult it would be to take the workspace, uproot it,
and move it to an alternate location.

After some hacking, the project proved to be largely successful with the
following caveats:

   #. There was some hardcoding in MKOBJDIRPREFIX; hence
      tools/fix-mkobjdirprefix-pathing.sh was born. This fixed some of
      the hardcoding.
   #. Even after the hardcoding was fixed, some headers had hardcoded
      references that couldn't be unwound easily (gcc is largely to
      blame). The author ran ``make buildworld -DNO_CLEAN`` and this
      fixed the dangling references.

Ultimately it would be nice if the above items were resolved in a more
properly designed manner and integrated into FreeBSD proper, but this
might be a more difficult task to achieve.

The end-goal is to create an SDK that others can use to develop plugins
and components with without having to build the entire system from
scratch; this would be ideal for cases where the FreeNAS project
distributes custom VM images for development purposes, but that's just
one example. Other examples are having a pre-built base to speed up
compilation when the only things changing are the python/middleware
goo, e.g. not third-party packages or the underlying base system.

It would be really nice if FreeNAS workspaces could be distributed and
developed on in a manner similar to Android and iOS apps.

