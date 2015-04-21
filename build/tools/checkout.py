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
from utils import sh, sh_str, info, debug, e, setfile


dsl = load_file('${BUILD_CONFIG}/repos.pyd', os.environ)


def checkout_repo(repo):
    os.chdir(e('${BUILD_ROOT}'))
    if os.path.isdir(os.path.join(repo['path'], '.git')):
        os.chdir(repo['path'])
        branch = sh_str('git rev-parse --abbrev-ref HEAD')
        if branch != repo['branch']:
            sh('git remote set-url origin', repo['url'])
            sh('git fetch origin')
            sh('git checkout', repo['branch'])

        sh('git pull --rebase')
    else:
        sh('git clone', '-b', repo['branch'], repo['url'], repo['path'])


if __name__ == '__main__':
    for i in dsl['repository'].values():
        info('Checkout: {0} -> {1}', i['name'], i['path'])
        debug('Repository URL: {0}', i['url'])
        debug('Local branch: {0}', i['branch'])
        checkout_repo(i)
        setfile('${BUILD_ROOT}/FreeBSD/.pulled', e('${PRODUCT}'))