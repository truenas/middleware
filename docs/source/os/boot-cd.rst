Boot CD
=======

.. contents:: Table of Contents
    :depth: 3

Like any other Linux distribution, TrueNAS installer boots from a combined ISO/USB stick image. The standard way to
create such an image is using `grub-mkrescue <https://www.gnu.org/software/grub/manual/grub/html_node/Making-a-GRUB-bootable-CD_002dROM.html>`_
utility. It generates an image containing a very basic GRUB EFI loader. It works fine when the image is written to a
USB stick as-is; however, many users use `Rufus <https://rufus.ie/en/>`_ utility to write an image to a USB stick, and
its default behavior is to repartition the USB drive with purpose of having a partition for storing user data. Partition
schema changes can't be understood by the basic GRUB EFI loader resulting in an unbootable image.

We replace EFI loaders installed by `grub-mkrescue` with the ones shipped by Debian. Debian repository contains
already-built GRUB EFI images in `debian-cd_info.tar.gz`. Several smaller changes are performed with
`grub-mkrescue`-generated image to ensure it works with Rufus. See `scale-build repo
<https://github.com/truenas/scale-build>`_ ISO module for more information.

Boot CD has a `mount-cd service
<https://github.com/truenas/scale-build/blob/master/conf/cd-files/lib/systemd/system/mount-cd.service>`_
that discovers and mounts installation media at `/cdrom`. Root user autologin is
configured at tty0 and also serial tty. `.bash_profile` launches `truenas-install
<https://github.com/truenas/truenas-installer/blob/master/usr/sbin/truenas-install>`_ script.

Testing boot CD
---------------

Considering the above, TrueNAS CD image should be tested in the following configurations:

* Written using dd, BIOS boot.
* Written using dd, UEFI boot.
* Written using `Rufus <https://rufus.ie/en/>`_, BIOS boot.
* Written using `Rufus <https://rufus.ie/en/>`_, UEFI boot.
