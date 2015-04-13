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
import sys
from dsl import load_file
from utils import sh, sh_str, e, setup_env, objdir, info, debug, error


setup_env()
dsl = load_file('${BUILD_CONFIG}/packages.pyd', os.environ)
tooldir = objdir('pkgtools')
pkgdir = objdir('packages')
pkgversion = ''


def read_repo_manifest():
    global version
    versions = []
    f = open(e("${BUILD_ROOT}/FreeBSD/repo-manifest"))
    for i in f:
        versions.append(i.split()[1])

    version = '-'.join(versions)


def build_pkgtools():
    info('Building freenas-pkgtools')
    sh("make -C ${SRC_ROOT}/freenas-pkgtools obj all")
    sh("make -C ${SRC_ROOT}/freenas-pkgtools install DESTDIR=${tooldir} PREFIX=/usr/local")


def build_packages():
    info('Building packages')
    sh('mkdir -p ${pkgdir}/Packages')
    for i in dsl['package'].values():
        template = i['template']
        name = i['name']
        sh(
            "${tooldir}/usr/local/bin/create_package",
            "-R ${WORLD_DESTDIR}",
            "-T ${template}",
            "-N ${name}",
            "-V ${VERSION}",
            '${pkgdir}/Packages/${name}-${VERSION}.tgz')


def create_manifest():
    info('Creating package manifests')
    pkgs = []
    for i in dsl['package'].values():
        pkgs.append(e("${i}=${VERSION}${pkgversion}"))

    sh(
        "env PYTHONPATH=${tooldir}/usr/local/lib",
        "${tooldir}/usr/local/bin/create_manifest",
        "-P ${pkgdir}/Packages",
        "-o ${pkgdir}/${PRODUCT}-${sequence}",
        "-R ${PRODUCT}-${VERSION}",
        "-T ${train}",
        "-t ${date}",
        *pkgs
    )

if __name__ == '__main__':
    read_repo_manifest()
    build_pkgtools()
    build_packages()
    create_manifest()