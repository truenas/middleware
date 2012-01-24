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

The document will also briefly touch upon related topics, such as
packaging and installation.

Finally, the document will briefly discuss the following roadmap items
installation format and the proposed installation mechanism.

=====
Goals
=====

The goals of the FreeNAS build system are the following items:

  #. Builds must be repeatable provided the minimum requirements of the
     system are met.
  #. Builds must be environment and system agnostic.
  #. Builds must fail when needed and also provide enough information
     for developers and release engineers to root-cause the source of
     failure.

==============
Basic Workflow
==============

The basic workflow of the end to end build process for custom
OS distributions that the author has worked with, is typically as
follows:

  #. Pull sources.
     #. Pull custom distribution sources from project specific source
        control system
  #. Bootstrap the distribution
     #. Optionally bootstrap the base OS and third party sources if
        they're not included in the source base
     #. Patch base OS and third-party sources with the changes needed
        for the custom distribution
  #. Build distribution
     #. Build and install base OS
     #. Build and install third party packages
     #. Overlay Install with project specific files
     #. Create bootable images (CD ISOs, disk images, install tarballs,
        or custom install images)

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
  * Pulling in project customizations (nanobsd/freenas-common)
  * Building and installing the base OS
  * Building and installing third-party packages
  * Adding in infrastructure required by project (gui, middleware, etc)
  * Build install images and media

Project Agnostic Infrastructure
-------------------------------

The nanobsd/common file defines common infrastructure for driving the
nanobsd build infrastructure available in FreeBSD. It should contain
components, macros, etc which can be used in several dissimilar projects
(e.g. BSD Router project, FreeNAS, pfSense, etc); ultimately the
components in nanobsd/common are candidates for inclusion in the base
nanobsd build infrastructure or in the Avatar project.

Examples of what are contained in this file are generic glue that
handles chrooting, package building, installation, etc.

Project Customizations
----------------------

nanobsd/freenas-common defines how the FreeNAS project will be built
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
process is handled by customize_cmd macros defined in
nanobsd/freenas-common and -- finally -- freenas_custom in
nanobsd/freenas-common (this is where the initial configuration
database is generated).

Create Install Images and Media
-------------------------------

Full disk install media is initially created via the
create_${ARCH}_diskimage . The full install media and GUI upgrade
images are compressed and the ISO image is created in last_orders
(nanobsd/freenas-common).
