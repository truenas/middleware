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
import glob
from dsl import load_file
from utils import sh, setup_env, objdir, info, debug, error, setfile, e, on_abort


setup_env()
dsl = load_file('${BUILD_CONFIG}/ports.pyd', os.environ)


def mount_packages():
    sh('mkdir -p ${WORLD_DESTDIR}/usr/ports/packages')
    sh('mount -t nullfs ${MAKEOBJDIRPREFIX}/ports/packages/ja-p ${WORLD_DESTDIR}/usr/ports/packages')


def umount_packages():
    sh('umount ${WORLD_DESTDIR}/usr/ports/packages')


def create_pkgng_configuration():
    sh('mkdir -p ${WORLD_DESTDIR}/usr/local/etc/pkg/repos')
    for i in glob.glob(e('${BUILD_CONFIG}/templates/pkg-repos/*')):
        fname = os.path.basename(i)
        sh(e('cp ${i} ${WORLD_DESTDIR}/usr/local/etc/pkg/repos/${fname}'))


def install_ports():
    pkgs = ' '.join(dsl['port'].keys())
    sh(e('chroot ${WORLD_DESTDIR} /bin/sh -c "env ASSUME_ALWAYS_YES=yes pkg install -r local -f ${pkgs}"'))


if __name__ == '__main__':
    on_abort(umount_packages)
    mount_packages()
    create_pkgng_configuration()
    install_ports()
    umount_packages()