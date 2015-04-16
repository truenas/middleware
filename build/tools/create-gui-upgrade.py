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
from utils import sh, info, objdir, e, chroot, setup_env, setfile, sha256, template


setup_env()
dsl = load_file("${BUILD_CONFIG}/config.pyd", os.environ)
output = objdir("${NAME}.GUI_Upgrade")


def main():
    sh("tar -c -p -f ${MAKEOBJDIRPREFIX}/gui-boot.tar -C ${MAKEOBJDIRPREFIX}/iso ./boot")
    sh("tar -c -p -f ${MAKEOBJDIRPREFIX}/gui-install-environment.tar -C ${MAKEOBJDIRPREFIX}/instufs .")
    sh(
        "tar -c -p -f ${MAKEOBJDIRPREFIX}/gui-packages.tar",
        "-s '@^Packages@FreeNAS/Packages@'",
        "-C ${MAKEOBJDIRPREFIX}/packages ."
    )
    sh(
        "tar -c -p -f ${output}.tar",
        "-C ${INSTUFS_DESTDIR}/etc/avatar.conf",
        "-C ${SRC_ROOT}/freenas-installer .",
        "-C ${SRC_ROOT}/freenas-gui-upgrade .",
        "-C ${MAKEOBJDIRPREFIX} gui-boot.tar gui-install-environment.tar gui-packages.tar"
    )

    sh("${XZ} ${PXZ_ACCEL} -9 -z -v ${output}.tar")
    sh("mv ${output}.tar.xz ${output}.txz")
    sha256("${output}.txz")

if __name__ == "__main__":
    info("Creating GUI upgrade image")
    main()