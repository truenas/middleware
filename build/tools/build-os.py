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
from utils import sh, sh_str, env, e, setup_env, objdir, info, debug, error


dsl = load_file('${BUILD_CONFIG}/config.pyd', os.environ)
arch = env('TARGET_ARCH', 'amd64')
makeconfbuild = objdir('make-build.conf')
kernconf = objdir(e('${KERNCONF}'))
kernlog = objdir('logs/buildkernel')
worldlog = objdir('logs/buildworld')
makejobs = None


def calculate_make_jobs():
    global makejobs

    jobs = sh_str('sysctl -n kern.smp.cpus')
    if not jobs:
        makejobs = 2

    makejobs = 2 * int(jobs) + 1
    debug('Using {0} make jobs', makejobs)


def create_make_conf_build():
    conf = open(makeconfbuild, 'w')
    for m in dsl['make_conf_build'].values():
        for k, v in m.items():
            conf.write('{0}={1}\n'.format(k, v))

    conf.close()


def create_kernel_config():
    conf = open(kernconf, 'w')
    for i in dsl['kernel_config']:
        f = open(os.path.join(env('BUILD_CONFIG'), i), 'r')
        conf.write(f.read())
        f.close()

    conf.close()


def buildkernel():
    modules = ' '.join(dsl['kernel_module'])
    info('Building kernel from ${{TRUEOS_ROOT}}')
    info('Log file: {0}', kernlog)
    debug('Kernel configuration file: {0}', kernconf)
    debug('Selected modules: {0}', modules)

    sh(
        "env MAKEOBJDIRPREFIX=${OBJDIR}",
        "make",
        "-j {0}".format(makejobs),
        "-C ${TRUEOS_ROOT}",
        "NO_KERNELCLEAN=YES",
        "__MAKE_CONF={0}".format(makeconfbuild),
        "KERNCONFDIR={0}".format(os.path.dirname(kernconf)),
        "KERNCONF={0}".format(os.path.basename(kernconf)),
        "MODULES_OVERRIDE='{0}'".format(modules),
        "buildkernel",
        log=kernlog
    )


def buildworld():
    info('Building world from ${{TRUEOS_ROOT}}')
    info('Log file: {0}', worldlog)
    debug('World make.conf: {0}', makeconfbuild)

    sh(
        "env MAKEOBJDIRPREFIX=${OBJDIR}",
        "make",
        "-j {0}".format(makejobs),
        "-C ${TRUEOS_ROOT}",
        "__MAKE_CONF={0}".format(makeconfbuild),
        "NOCLEAN=YES",
        "buildworld",
        log=worldlog
    )


def installworld(destdir, worldlog, distriblog):
    info('Installing world in {0}', destdir)
    info('Log file: {0}', worldlog)
    sh(
        "env MAKEOBJDIRPREFIX=${OBJDIR}",
        "make",
        "-C ${TRUEOS_ROOT}",
        "installworld",
        "DESTDIR=${destdir}",
        "__MAKE_CONF=${makeconfbuild}",
        log=worldlog
    )

    info('Creating distribution in {0}', destdir)
    info('Log file: {0}', distriblog)
    sh(
        "env MAKEOBJDIRPREFIX=${OBJDIR}",
        "make",
        "-C ${TRUEOS_ROOT}",
        "distribution",
        "DESTDIR=${destdir}",
        "__MAKE_CONF=${makeconfbuild}",
        log=distriblog
    )


def installkernel(destdir, log):
    info('Installing kernel in {0}', log)
    info('Log file: {0}', log)

    modules = ' '.join(dsl['kernel_module'])
    sh(
        "env MAKEOBJDIRPREFIX=${OBJDIR}",
        "make",
        "-C ${TRUEOS_ROOT}",
        "installkernel",
        "DESTDIR=${destdir}",
        "__MAKE_CONF=${makeconfbuild}",
        "MODULES_OVERRIDE='{0}'".format(modules),
        log=log
    )


if __name__ == '__main__':
    if env('SKIP_OS'):
        info('Skipping buildworld & buildkernel as instructed by setting SKIP_OS')
        sys.exit(0)

    calculate_make_jobs()
    create_make_conf_build()
    create_kernel_config()
    buildworld()
    buildkernel()