#!/usr/bin/env python2.7
#+
# Copyright 2015 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################


import os
from dsl import load_file
from utils import sh, info, objdir, e, chroot, glob, setup_env, setfile, template, sha256, import_function


dsl = load_file('${BUILD_CONFIG}/config.pyd', os.environ)
ports = load_file('${BUILD_CONFIG}/ports-installer.pyd', os.environ)
installworld = import_function('build-os', 'installworld')
installkernel = import_function('build-os', 'installkernel')
installworldlog = objdir('logs/iso-installworld')
installkernellog = objdir('logs/iso-installkernel')
distributionlog = objdir('logs/iso-distribution')
sysinstalllog = objdir('logs/iso-sysinstall')
imgfile = objdir('base.ufs')
output = objdir('${NAME}.iso')


purge_dirs = [
    '/bin',
    '/sbin',
    '/usr/bin',
    '/usr/sbin'
]

files_to_preserve = [
    '/bin/sleep',
    '/usr/bin/dialog',
    '/usr/bin/dirname',
    '/usr/bin/awk',
    '/usr/bin/cut',
    '/usr/bin/cmp',
    '/usr/bin/find',
    '/usr/bin/grep',
    '/usr/bin/logger',
    '/usr/bin/mkfifo',
    '/usr/bin/mktemp',
    '/usr/bin/sed',
    '/usr/bin/sort',
    '/usr/bin/tr',
    '/usr/bin/uname',
    '/usr/bin/xargs',
    '/usr/sbin/diskinfo',
    '/usr/sbin/vidcontrol'
    '/sbin/geom'
]

symlinks = {
    '[': '/bin/[',
    'badsect': '/sbin/badsect',
    'bsdlabel': '/sbin/bsdlabel',
    'bunzip2': '/usr/bin/bunzip2',
    'bzcat': '/usr/bin/bzcat',
    'bzip2': '/usr/bin/bzip2',
    'camcontrol': '/sbin/camcontrol',
    'cat': '/bin/cat',
    'ccdconfig': '/sbin/ccdconfig',
    'chflags': '/bin/chflags',
    'chgrp': '/usr/bin/chgrp',
    'chio': '/bin/chio',
    'chmod': '/bin/chmod',
    'chown': '/usr/sbin/chown',
    'chroot': '/usr/sbin/chroot',
    'clri': '/sbin/clri',
    'cp': '/bin/cp',
    'csh': '/bin/csh',
    'date': '/bin/date',
    'dd': '/bin/dd',
    'devfs': '/sbin/devfs',
    'df': '/bin/df',
    'dhclient': '/sbin/dhclient',
    'dhclient-script': '/sbin/dhclient-script',
    'disklabel': '/sbin/disklabel',
    'dmesg': '/sbin/dmesg',
    'dump': '/sbin/dump',
    'dumpfs': '/sbin/dumpfs',
    'dumpon': '/sbin/dumpon',
    'echo': '/bin/echo',
    'ed': '/bin/ed',
    'ex': '/usr/bin/ex',
    'expr': '/bin/expr',
    'fastboot': '/sbin/fastboot',
    'fasthalt': '/sbin/fasthalt',
    'fdisk': '/sbin/fdisk',
    'fsck': '/sbin/fsck',
    'fsck_4.2bsd': '/sbin/fsck_4.2bsd',
    'fsck_ffs': '/sbin/fsck_ffs',
    'fsck_msdosfs': '/sbin/fsck_msdosfs',
    'fsck_ufs': '/sbin/fsck_ufs',
    'fsdb': '/sbin/fsdb',
    'fsirand': '/sbin/fsirand',
    'gbde': '/sbin/gbde',
    'getfacl': '/bin/getfacl',
    'groups': '/usr/bin/groups',
    'gunzip': '/usr/bin/gunzip',
    'gzcat': '/usr/bin/gzcat',
    'gzip': '/usr/bin/gzip',
    'halt': '/sbin/halt',
    'head': '/usr/bin/head',
    'hostname': '/bin/hostname',
    'id': '/usr/bin/id',
    'ifconfig': '/sbin/ifconfig',
    'init': '/sbin/init',
    'kenv': '/bin/kenv',
    'kill': '/bin/kill',
    'kldconfig': '/sbin/kldconfig',
    'kldload': '/sbin/kldload',
    'kldstat': '/sbin/kldstat',
    'kldunload': '/sbin/kldunload',
    'ldconfig': '/sbin/ldconfig',
    'less': '/usr/bin/less',
    'link': '/bin/link',
    'ln': '/bin/ln',
    'ls': '/bin/ls',
    'lzcat': '/usr/bin/lzcat',
    'lzma': '/usr/bin/lzma',
    'md5': '/sbin/md5',
    'mdconfig': '/sbin/mdconfig',
    'mdmfs': '/sbin/mdmfs',
    'mkdir': '/bin/mkdir',
    'mknod': '/sbin/mknod',
    'more': '/usr/bin/more',
    'mount': '/sbin/mount',
    'mount_cd9660': '/sbin/mount_cd9660',
    'mount_msdosfs': '/sbin/mount_msdosfs',
    'mount_nfs': '/sbin/mount_nfs',
    'mount_nullfs': '/sbin/mount_nullfs',
    'mount_udf': '/sbin/mount_udf',
    'mount_unionfs': '/sbin/mount_unionfs',
    'mt': '/usr/bin/mt',
    'mv': '/bin/mv',
    'nc': '/usr/bin/nc',
    'newfs': '/sbin/newfs',
    'newfs_msdos': '/sbin/newfs_msdos',
    'nextboot': '/sbin/nextboot',
    'nos-tun': '/sbin/nos-tun',
    'pc-sysinstall': '/usr/sbin/pc-sysinstall',
    'pgrep': '/bin/pgrep',
    'ping': '/sbin/ping',
    'ping6': '/sbin/ping6',
    'pkill': '/bin/pkill',
    'ps': '/bin/ps',
    'pwd': '/bin/pwd',
    'rcorder': '/sbin/rcorder',
    'rdump': '/sbin/rdump',
    'realpath': '/bin/realpath',
    'reboot': '/sbin/reboot',
    'red': '/bin/red',
    'restore': '/sbin/restore',
    'rm': '/bin/rm',
    'rmdir': '/bin/rmdir',
    'route': '/sbin/route',
    'routed': '/sbin/routed',
    'rrestore': '/sbin/rrestore',
    'rtquery': '/sbin/rtquery',
    'rtsol': '/sbin/rtsol',
    'savecore': '/sbin/savecore',
    'setfacl': '/bin/setfacl',
    'sh': '/bin/sh',
    'spppcontrol': '/sbin/spppcontrol',
    'stty': '/bin/stty',
    'swapon': '/sbin/swapon',
    'sync': '/bin/sync',
    'sysctl': '/sbin/sysctl',
    'tail': '/usr/bin/tail',
    'tar': '/usr/bin/tar',
    'tcsh': '/bin/tcsh',
    'tee': '/usr/bin/tee',
    'test': '/bin/test',
    'tunefs': '/sbin/tunefs',
    'umount': '/sbin/umount',
    'unlink': '/bin/unlink',
    'unlzma': '/usr/bin/unlzma',
    'unxz': '/usr/bin/unxz',
    'vi': '/usr/bin/vi',
    'whoami': '/usr/bin/whoami',
    'xz': '/usr/bin/xz',
    'xzcat': '/usr/bin/xzcat',
    'zcat': '/usr/bin/zcat',
    'zfs': '/sbin/zfs',
    'zpool': '/sbin/zpool',
    '/bin/pgrep': '/usr/bin/pgrep',
    '/bin/pkill': '/usr/bin/pkill',
    '/.mount/boot': '/boot'
}


isodir = objdir('isodir')
instufs = objdir('instufs')


def create_iso_dirs():
    sh('mkdir -p ${ISO_DESTDIR} ${INSTUFS_DESTDIR}')
    sh('mkdir -p ${ISO_DESTDIR}/data')
    sh('mkdir -p ${ISO_DESTDIR}/dev')
    sh('mkdir -p ${ISO_DESTDIR}/.mount')
    sh('mkdir -p ${ISO_DESTDIR}/mnt')
    sh('mkdir -p ${ISO_DESTDIR}/tmp')
    sh('mkdir -p ${ISO_DESTDIR}/boot/grub')


def create_ufs_dirs():
    sh('mkdir -p ${INSTUFS_DESTDIR}/usr/local/pre-install')
    sh('mkdir -p ${INSTUFS_DESTDIR}/usr/local/firmware')
    sh('mkdir -p ${INSTUFS_DESTDIR}/usr/local/install')
    sh('mkdir -p ${INSTUFS_DESTDIR}/usr/local/sbin')
    sh('mkdir -p ${INSTUFS_DESTDIR}/.mount')
    sh('mkdir -p ${INSTUFS_DESTDIR}/cdrom')
    sh('mkdir -p ${INSTUFS_DESTDIR}/conf/default/etc')
    sh('mkdir -p ${INSTUFS_DESTDIR}/conf/default/tmp')
    sh('mkdir -p ${INSTUFS_DESTDIR}/conf/default/var')
    sh('mkdir -p ${INSTUFS_DESTDIR}/tank')
    sh('rm -rf ${INSTUFS_DESTDIR}/boot')


def setup_diskless():
    sh('touch ${INSTUFS_DESTDIR}/etc/diskless')
    sh('cp -a ${INSTUFS_DESTDIR}/etc/ ${INSTUFS_DESTDIR}/conf/default/etc')
    sh('cp -a ${INSTUFS_DESTDIR}/var/ ${INSTUFS_DESTDIR}/conf/default/var')


def cleandirs():
    info('Cleaning previous build products')
    if os.path.isdir(e('${INSTUFS_DESTDIR}')):
        sh('chflags -R 0 ${INSTUFS_DESTDIR}')
        sh('rm -rf ${INSTUFS_DESTDIR}')

    sh('rm -rf ${ISO_DESTDIR}')


def install_ports():
    pkgs = ' '.join(ports['port'].keys())
    info('Installing packages')
    sh('mkdir -p ${INSTUFS_DESTDIR}/usr/local/etc/pkg/repos')
    sh('cp ${BUILD_CONFIG}/templates/pkg-repos/local.conf ${INSTUFS_DESTDIR}/usr/local/etc/pkg/repos/')
    chroot('${INSTUFS_DESTDIR}', 'env ASSUME_ALWAYS_YES=yes pkg install -r local -f ${pkgs}')


def install_pkgtools():
    info('Installing freenas-pkgtools')
    sh(
        "env MAKEOBJDIRPREFIX=${OBJDIR}",
        "make -C ${SRC_ROOT}/freenas-pkgtools obj all install DESTDIR=${INSTUFS_DESTDIR} PREFIX=/usr/local",
    )


def mount_packages():
    sh('mkdir -p ${INSTUFS_DESTDIR}/usr/ports/packages')
    sh('mount -t nullfs ${OBJDIR}/ports/packages/ja-p ${INSTUFS_DESTDIR}/usr/ports/packages')


def umount_packages():
    sh('umount ${INSTUFS_DESTDIR}/usr/ports/packages')


def install_files():
    info('Copying installer files')
    setfile('${INSTUFS_DESTDIR}/etc/avatar.conf', template('${BUILD_CONFIG}/templates/avatar.conf'))


def populate_ufsroot():
    info('Populating UFS root')

    for i in purge_dirs:
        for name in glob('${INSTUFS_DESTDIR}${i}/*'):
            if e('${i}/${name}') in files_to_preserve:
                continue

            sh('chflags -f 0 ${INSTUFS_DESTDIR}${i}/${name}')
            sh('rm -f ${INSTUFS_DESTDIR}${i}/${name}')

    for k, v in symlinks.items():
        p = os.path.join('/rescue', k)
        sh('ln -s ${p} ${INSTUFS_DESTDIR}${v}')


def copy_packages():
    sh('mkdir -p ${ISO_DESTDIR}/${PRODUCT}')
    sh('cp -R ${OBJDIR}/packages/Packages ${ISO_DESTDIR}/${PRODUCT}')
    sh('cp ${OBJDIR}/packages/${PRODUCT}-MANIFEST ${ISO_DESTDIR}/')


def clean_ufs_image():
    sh('${BUILD_ROOT}/build/customize/remove-bits.py ${INSTUFS_DESTDIR}')


def clean_iso_image():
    sh("find ${ISO_DESTDIR}/boot -name '*.symbols' -delete")


def make_ufs_image():
    sh('mkdir -p ${ISO_DESTDIR}/data')
    sh('makefs -b 10% ${imgfile} ${INSTUFS_DESTDIR}')
    sh('mkuzip -o ${ISO_DESTDIR}/data/base.ufs.uzip ${imgfile}')


def make_iso_image():
    setfile('${ISO_DESTDIR}/boot/loader.conf', template('${BUILD_CONFIG}/templates/cdrom/loader.conf'))
    setfile('${ISO_DESTDIR}/boot/grub/grub.cfg', template('${BUILD_CONFIG}/templates/cdrom/grub.cfg'))
    setfile('${ISO_DESTDIR}/.mount.conf', template('${BUILD_CONFIG}/templates/cdrom/mount.conf'))
    sh('cp ${WORLD_DESTDIR}/boot/device.hints ${ISO_DESTDIR}/boot/device.hints')
    sh('grub-mkrescue -o ${output} ${ISO_DESTDIR} -- -volid ${CDROM_LABEL}')
    sha256(output)


if __name__ == '__main__':
    info("Creating ISO image")
    cleandirs()
    installworld(e('${INSTUFS_DESTDIR}'), installworldlog, distributionlog)
    installkernel(e('${ISO_DESTDIR}'), installkernellog)
    create_ufs_dirs()
    mount_packages()
    install_ports()
    install_pkgtools()
    umount_packages()
    populate_ufsroot()
    install_files()
    copy_packages()
    clean_ufs_image()
    setup_diskless()
    clean_iso_image()
    create_iso_dirs()
    make_ufs_image()
    make_iso_image()
