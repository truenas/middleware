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
import glob
from utils import env, e, setup_env, sh, sh_str, info, debug, error, walk, objdir


setup_env()
logfile = objdir('logs/build-gui')


def cleandirs():
    sh('mkdir -p ${GUI_STAGEDIR}')
    sh('mkdir -p ${GUI_DESTDIR}')
    sh('rm -rf ${GUI_STAGEDIR}/*')
    sh('rm -rf ${GUI_DESTDIR}/*')


def copy():
    sh('cp -a ${SRC_ROOT}/gui/ ${GUI_STAGEDIR}/')


def gplusplus_version():
    return glob.glob('/usr/local/bin/g++??')[0]


def apply_npm_quirks():
    q = []
    if not os.path.islink('/usr/local/bin/g++'):
        os.symlink(gplusplus_version(), '/usr/local/bin/g++')
        q.append('g++')

    if not os.path.islink('/usr/local/bin/c++'):
        os.symlink(gplusplus_version(), '/usr/local/bin/c++')
        q.append('c++')

    return q


def remove_npm_quirks(quirks):
    for i in quirks:
        os.unlink(os.path.join('/usr/local/bin', i))


def install():
    node_modules = e('${GUI_STAGEDIR}/node_modules')
    bower = e('${node_modules}/bower/bin/bower')
    grunt = e('${node_modules}/grunt-cli/bin/grunt')

    os.chdir(e('${GUI_STAGEDIR}'))
    sh('npm install grunt grunt-cli bower')
    sh('npm install')
    sh(bower, '--allow-root install', log=logfile)
    sh(grunt, 'deploy --force --dir=${GUI_DESTDIR}', log=logfile)


def create_plist():
    with open(e('${GUI_DESTDIR}/gui-plist'), 'w') as f:
        for i in walk('${GUI_DESTDIR}'):
            if not os.path.isdir(e('${GUI_DESTDIR}/${i}')):
                f.write(e('/usr/local/www/gui/${i}\n'))

        with open(e('${GUI_STAGEDIR}/custom-plist')) as c:
            f.write(c.read())


if __name__ == '__main__':
    if env('SKIP_GUI'):
        info('Skipping GUI build as instructed by setting SKIP_GUI')
        sys.exit(0)

    info('Building GUI')
    cleandirs()
    copy()
    q = apply_npm_quirks()
    install()
    remove_npm_quirks(q)
    create_plist()