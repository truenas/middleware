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
% git clone git://github.com/freenas/freenas.git --branch freenas10/development
% cd freenas
```

* Build it

```
% make git-external
% make checkout
% make release
```

* Update the source tree, to pull in new source code changes

```
% make update
```

This will also fetch TrueOS and ports for the build from github.

## The End Result:

If your build completes successfully, you'll have both 32 and 64 bit
release products in the release_stage directory.  You will also have
a tarball in your build directory containing the entire release for
easy transport.
