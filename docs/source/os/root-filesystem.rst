Root filesystem
===============

.. contents:: Table of Contents
    :depth: 3

TrueNAS image contains a number of extra files in the OS root filesystem. It also removes a few files provided by
standard Debian packages. Files are installed using `truenas-files` debian package and are modified in `truenas` debian
package `postinst` script.

Adding extra files to the root filesystem
-----------------------------------------

* Put your extra files into `src/freenas` directory of the `middleware` repository.
* Ensure that your files will be copied by `src/freenas/debian/rules` install script.
* If your file overwrites a file installed by another debian package, add it to the `dpkg-divert` for loop in
  `src/freenas/debian/preinst` script.

Removing standard files from the root filesystem
------------------------------------------------

* Add your file to the `dpkg-divert` for loop in `debian/postinst` script.
