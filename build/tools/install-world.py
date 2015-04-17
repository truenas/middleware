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

import sys
from utils import sh, sh_str, e, setup_env, objdir, info, debug, error, import_function


setup_env()
installworldlog = objdir('logs/dest-installworld')
distributionlog = objdir('logs/dest-distribution')
installkernellog = objdir('logs/dest-installkernel')
installworld = import_function('build-os', 'installworld')
installkernel = import_function('build-os', 'installkernel')


if __name__ == '__main__':
    if e('${SKIP_INSTALL_WORLD}'):
        info('Skipping world installation, as instructed by setting SKIP_INSTALL_WORLD')
        sys.exit(0)

    sh('chflags -R 0 ${WORLD_DESTDIR}')
    sh('rm -rf ${WORLD_DESTDIR}')
    sh('mkdir -p ${WORLD_DESTDIR}')
    installworld(e('${WORLD_DESTDIR}'), installworldlog, distributionlog)
    installkernel(e('${WORLD_DESTDIR}'), installkernellog)