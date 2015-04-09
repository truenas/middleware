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
from utils import env, setup_env, sh, info, debug, error, pathjoin


setup_env()


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
    if not os.path.islink('/usr/local/bin/g++'):
        os.symlink(gplusplus_version(), '/usr/local/bin/g++')
        yield 'g++'

    if not os.path.islink('/usr/local/bin/c++'):
        os.symlink(gplusplus_version(), '/usr/local/bin/c++')
        yield 'c++'


def remove_npm_quirks(quirks):
    for i in quirks:
        os.unlink(os.path.join('/usr/local/bin', i))


def install():
    node_modules = pathjoin('${GUI_STAGEDIR}', 'node_modules')
    bower = pathjoin(node_modules, 'bower/bin/bower')
    grunt = pathjoin(node_modules, 'grunt-cli/bin/grunt')

    os.chdir(env('GUI_STAGEDIR'))
    sh('npm install grunt grunt-cli bower')
    sh('npm install')
    sh(bower, '--allow-root install')
    sh(grunt, 'deploy --force --dir=${GUI_DESTDIR}')


def create_plist():
    os.chdir(env('GUI_DESTDIR'))


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