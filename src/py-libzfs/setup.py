#-
# Copyright (c) 2014 iXsystems, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#

import os
from distutils.core import setup
from Cython.Distutils.extension import Extension
from Cython.Distutils import build_ext

system_includes = [
    "${FREEBSD_SRC}/cddl/lib/libumem",
    "${FREEBSD_SRC}/sys/cddl/compat/opensolaris/",
    "${FREEBSD_SRC}/sys/cddl/compat/opensolaris",
    "${FREEBSD_SRC}/cddl/compat/opensolaris/include",
    "${FREEBSD_SRC}/cddl/compat/opensolaris/lib/libumem",
    "${FREEBSD_SRC}/cddl/contrib/opensolaris/lib/libzpool/common",
    "${FREEBSD_SRC}/sys/cddl/contrib/opensolaris/common/zfs",
    "${FREEBSD_SRC}/sys/cddl/contrib/opensolaris/uts/common/fs/zfs",
    "${FREEBSD_SRC}/sys/cddl/contrib/opensolaris/uts/common/sys",
    "${FREEBSD_SRC}/cddl/contrib/opensolaris/head",
    "${FREEBSD_SRC}/sys/cddl/contrib/opensolaris/uts/common",
    "${FREEBSD_SRC}/cddl/contrib/opensolaris/lib/libnvpair",
    "${FREEBSD_SRC}/cddl/contrib/opensolaris/lib/libuutil/common",
    "${FREEBSD_SRC}/cddl/contrib/opensolaris/lib/libzfs/common",
    "${FREEBSD_SRC}/cddl/contrib/opensolaris/lib/libzfs_core/common"
]

system_includes = [os.path.expandvars(x) for x in system_includes]

setup(
    name='libzfs',
    version='1.0',
    cmdclass={'build_ext': build_ext},
    ext_modules=[
        Extension(
            "nvpair",
            ["nvpair.pyx"],
            libraries=["nvpair"],
            extra_compile_args=["-DNEED_SOLARIS_BOOLEAN", "-D_XPG6", "-g"],
            cython_include_dirs=["./pxd"],
            include_dirs=system_includes,
            extra_link_args=["-g"]
        ),
        Extension(
            "libzfs",
            ["libzfs.pyx"],
            libraries=["nvpair", "zfs", "zfs_core", "uutil", "geom"],
            extra_compile_args=["-DNEED_SOLARIS_BOOLEAN", "-D_XPG6", "-g"],
            cython_include_dirs=["./pxd"],
            include_dirs=system_includes,
            extra_link_args=["-g"]
        )
    ]
)
