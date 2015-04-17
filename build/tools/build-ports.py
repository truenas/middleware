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
from utils import sh, sh_str, env, e, objdir, pathjoin, setfile, setup_env, template, debug, on_abort, info


setup_env()
makejobs = 1
dsl = load_file('${BUILD_CONFIG}/ports.pyd', os.environ)
installer_dsl = load_file('${BUILD_CONFIG}/ports-installer.pyd', os.environ)
reposconf = load_file('${BUILD_CONFIG}/repos.pyd', os.environ)
jailconf = load_file('${BUILD_CONFIG}/jail.pyd', os.environ)
conf = load_file('${BUILD_CONFIG}/config.pyd', os.environ)

portslist = e('${POUDRIERE_ROOT}/etc/ports.conf')
portoptions = e('${POUDRIERE_ROOT}/etc/poudriere.d/options')


def calculate_make_jobs():
    global makejobs

    jobs = sh_str('sysctl -n kern.smp.cpus')
    if not jobs:
        makejobs = 2

    makejobs = int(jobs) + 1
    debug('Using {0} make jobs', makejobs)


def create_poudriere_config():
    conf = pathjoin('${POUDRIERE_ROOT}', 'etc/poudriere.conf')
    setfile(conf, template('${BUILD_CONFIG}/templates/poudriere.conf', {
        'ports_repo': reposconf['repository']['ports']['path'],
        'ports_branch': reposconf['repository']['ports']['branch'],
        'ports_distfiles_cache': e('${MAKEOBJDIRPREFIX}/ports/distfiles')
    }))

    tree = e('${POUDRIERE_ROOT}/etc/poudriere.d/ports/p')
    sh('mkdir -p', tree)
    setfile(pathjoin(tree, 'mnt'), env('PORTS_ROOT'))
    setfile(pathjoin(tree, 'method'), 'git')


def create_make_conf():
    makeconf = e('${POUDRIERE_ROOT}/etc/poudriere.d/make.conf')
    setfile(makeconf, template('${BUILD_CONFIG}/templates/poudriere-make.conf', {

    }))


def create_ports_list():
    info('Creating ports list')
    sh('rm -rf', portoptions)

    f = open(portslist, 'w')
    for port in installer_dsl['port'].values() + dsl['port'].values():
        port_und = port['name'].replace('/', '_')
        options_path = pathjoin(portoptions, port_und)
        f.write('{0}\n'.format(port['name']))

        sh('mkdir -p', options_path)

        if 'options' in port:
            opt = open(pathjoin(options_path, 'options'), 'w')
            for o in port['options']:
                opt.write('{0}\n'.format(o))

            opt.close()

    f.close()


def prepare_jail():
    jailname = 'ja'
    basepath = e('${POUDRIERE_ROOT}/etc/poudriere.d/jails/${jailname}')
    sh('mkdir -p ${basepath}')

    setfile(e('${basepath}/method'), 'git')
    setfile(e('${basepath}/mnt'), e('${JAIL_DESTDIR}'))
    setfile(e('${basepath}/version'), e('${FREEBSD_RELEASE_VERSION}'))
    setfile(e('${basepath}/arch'), e('${BUILD_ARCH}'))

    sh("jail -U root -c name=${jailname} path=${JAIL_DESTDIR} command=/sbin/ldconfig -m /lib /usr/lib /usr/lib/compat")


def merge_freenas_ports():
    sh('mkdir -p ${PORTS_ROOT}/freenas')
    sh('cp -a ${BUILD_ROOT}/nas_ports/freenas ${PORTS_ROOT}/')


def prepare_env():
    for cmd in jailconf.get('copy', []).values():
        dest = os.path.join(e('${JAIL_DESTDIR}'), cmd['dest'][1:])
        sh('rm -rf ${dest}')
        sh('cp -a', cmd['source'], dest)

    for cmd in jailconf.get('link', []).values():
        flags = '-o {0}'.format(cmd['flags']) if 'flags' in cmd else ''
        dest = os.path.join(e('${JAIL_DESTDIR}'), cmd['dest'][1:])
        sh('mkdir -p', os.path.dirname(dest))
        sh('mount -t nullfs', flags, cmd['source'], dest)


def cleanup_env():
    for cmd in jailconf.get('link', []).values():
        sh('umount', cmd['source'])


def run():
    sh('poudriere -e ${POUDRIERE_ROOT}/etc bulk -w -J', str(makejobs), '-f', portslist, '-j ja -p p')


if __name__ == '__main__':
    if env('SKIP_PORTS'):
        info('Skipping ports build as instructed by setting SKIP_PORTS')
        sys.exit(0)

    on_abort(cleanup_env)
    calculate_make_jobs()
    create_poudriere_config()
    create_make_conf()
    create_ports_list()
    prepare_jail()
    merge_freenas_ports()
    prepare_env()
    run()
    cleanup_env()