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
from utils import setup_env, sh


setup_env()


def main(destdir):
    # Kill .pyo files
    sh("find ${destdir}/usr/local -name '*.pyo' -delete")

    # Kill includes
    sh("find ${destdir}/usr/local/include \! -name 'pyconfig.h' -delete")

    # Kill docs
    sh('rm -rf ${destdir}/usr/local/share/doc')
    sh('rm -rf ${destdir}/usr/local/share/gtk-doc')

    # Kill gobject introspection xml
    sh('rm -rf ${destdir}/usr/local/share/git-1.0')

    # Kill info
    sh('rm -rf ${destdir}/usr/local/info')

    # Kill man pages
    sh('rm -rf ${destdir}/usr/local/man')

    # Kill examples
    sh('rm -rf ${destdir}/usr/local/share/examples')

    # Kill groff_fonts junk
    sh('rm -rf ${destdir}/usr/share/groff_font')
    sh('rm -rf ${destdir}/usr/share/tmac')
    sh('rm -rf ${destdir}/usr/share/me')

    # Kill static libraries
    sh("find ${destdir}/usr/local -name '*.a' -or -name '*.la' -delete")

    # magic.mgc is just a speed optimization
    sh('rm -f ${destdir}/usr/share/misc/magic.mgc')


if __name__ == '__main__':
    main(sys.argv[1])