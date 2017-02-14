## IMPORTANT NOTE:  This is the master branch of freenas, which is used only for the creation and testing of 9.10-Nightlies builds.  If you are building or developing for:

* FreeNAS 10 / 9.10:	https://github.com/freenas/freenas-build
* Prior Releases:	Use the 9.3-STABLE branch (and old build system)

# Building FreeNAS

To build the system (experts only):

## Requirements:

* Your build environment must be FreeBSD 10.

* an amd64 capable processor.  8GB of memory, or an equal/greater amount
  of swap space, is also required

* You will need the following ports/packages when compiling anything
  FreeNAS-related:
  * ports-mgmt/poudriere-devel
  * devel/git
  * devel/gmake
  * sysutils/cdrtools
  * archivers/pxz
  * lang/python3 
  * sysutils/xorriso
  * py27-sphinx
  * py27-sphinxcontrib-httpdomain-1.2.1
  (and all the dependencies that these ports/pkgs install, of course)

## Building the System Quickstart Flow:

* Checking out the code from git:

```
% cd /path/to/your-build-filesystem
% git clone https://github.com/freenas/freenas-build
% cd freenas-build
```

* Build it

```
% make checkout PROFILE=freenas9
% make release PROFILE=freenas9
```

* Update the source tree, to pull in new source code changes

```
% make update PROFILE=freenas9
```

This will also fetch TrueOS and ports for the build from github.

## The End Result:

If your build completes successfully, you'll have 64 bit release products in
the release_stage directory.  You will also have a tarball in your build
directory containing the entire release for easy transport.
