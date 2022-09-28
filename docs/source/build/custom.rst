Building A Custom Image
=======================

.. contents:: Table of Contents
    :depth: 3

iX build server (accessible only from iXsystems VPN) provides a `Jenkins pipeline
<https://ci.tn.ixsystems.net/jenkins/job/TrueNAS%20SCALE%20-%20Unstable/job/Build%20-%20TrueNAS%20SCALE%20(Custom)/>`_
for building a TrueNAS ISO image and .update file using specific branches of specific repositories from which the whole
distribution is assembled.

Clicking "Build with Parameters" button will present a number of `*_OVERRIDE` variables. Each variable represents a
repository branch override for a specific "component" of the image. Every component is built from a single repository.
The list of components and their repositories can be found in `sources` section of `scale-build:conf/build.manifest
<https://github.com/truenas/scale-build/blob/master/conf/build.manifest>`_ file. `scale_build_OVERRIDE` option specifies
an override branch for the `scale-build` repository itself.

An additional convenience option `TRY_BRANCH_OVERRIDE` will attempt to check out specified branch name for every
repository. This can be used for builds that need to pull from the same non-default branch in multiple repositories.
If the branch does not exist, the default branch is used.

Please note the difference between `truenas`, `truenas_files` and `middleware` components:

* `truenas` component is a metapackage that only contains systemd units and performs post-installation tasks (it is
  built from `debian/rules` file of the middleware repository).
* `truenas_files` component builds the `truenas-files` debian package that contains all the :doc:`TrueNAS filesystem
  assets <../os/root-filesystem>`_ (it is built from `src/freenas/debian/rules` file of the middleware repository).
* `middleware` component only contains TrueNAS middleware python code, systemd unit and factory database.

After a build succeeds, `.iso` and `.update` files can be accessed using the "Build Artifacts" link on the build page.
