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
from utils import sh, e, setup_env, objdir, info, import_function


installworldlog = objdir('logs/jail-installworld')
distributionlog = objdir('logs/jail-distribution')
installkernellog = objdir('logs/jail-installkernel')
installworld = import_function('build-os', 'installworld')
installkernel = import_function('build-os', 'installkernel')


if __name__ == '__main__':
    if e('${SKIP_INSTALL_JAIL}'):
        info('Skipping jail installation, as instructed by setting SKIP_INSTALL_JAIL')
        sys.exit(0)

    if os.path.isdir(e('${WORLD_DESTDIR}')):
        sh('chflags -fR 0 ${JAIL_DESTDIR}')
        sh('rm -rf ${JAIL_DESTDIR}')

    sh('mkdir -p ${JAIL_DESTDIR}')
    installworld(e('${JAIL_DESTDIR}'), installworldlog, distributionlog)
    installkernel(e('${JAIL_DESTDIR}'), installkernellog)
