# Building FreeNAS

To build the system (experts only):

## Requirements:

* Your build environment must be FreeBSD 10.0-RELEASE/FreeBSD 10.1-STABLE (building on
  FreeBSD 9 or 11 is not supported at this time).

* an amd64 capable processor.  8GB of memory, or an equal/greater amount
  of swap space, is also required

* You will need the following ports/packages when compiling anything
  FreeNAS-related:
  * ports-mgmt/poudriere-devel
  * devel/git
  * sysutils/cdrtools
  * archivers/pxz
  * lang/python (2.7 or later, with THREADS support)
  * sysutils/grub2-pcbsd
  * sysutils/xorriso
  * www/npm
  * devel/gmake
  * py-sphinx
  * py-sphinx_rtd_theme
  * py-sphinxcontrib-httpdomain

  (and all the dependencies that these ports/pkgs install, of course)

## Building the System Quickstart Flow:

* Checking out the code from git:

```
% cd /path/to/your-build-filesystem
% git clone https://github.com/freenas/freenas-build
% cd freenas-build
```

## NOTE:  The freenas build infrastructure is now separate and in its own repo;
## if you are reading this file in the freenas repo, you need to check out
## the freenas-build repo separately, as above.  The freenas repo now contains
## only the freenas sources.

* Build it

```
% make git-external
% make checkout
% make release
```

* Update the source tree, to pull in new source code changes

```

## The End Result:

If your build completes successfully, you'll have 64 bit release products
in the _BE directory. 
