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


from utils import setup_env, sh, chroot


setup_env()


files_to_save = [
    "/usr/local/lib/gcc48/libstdc++.so.6",
    "/usr/local/lib/gcc48/libstdc++.so",
    "/usr/local/lib/gcc48/libstdc++.a",
    "/usr/local/lib/gcc48/libmudflap.so.0",
    "/usr/local/lib/gcc48/libmudflap.so",
    "/usr/local/lib/gcc48/libmudflapth.so.0",
    "/usr/local/lib/gcc48/libmudflapth.so",
    "/usr/local/lib/gcc48/libssp.so.0",
    "/usr/local/lib/gcc48/libssp.so",
    "/usr/local/lib/gcc48/libgcc_s.so.1",
    "/usr/local/lib/gcc48/libgcc_s.so",
    "/usr/local/lib/gcc48/libquadmath.so.0",
    "/usr/local/lib/gcc48/libquadmath.so",
    "/usr/local/lib/gcc48/libquadmath.a",
    "/usr/local/lib/gcc48/libgomp.spec",
    "/usr/local/lib/gcc48/libgomp.so.1",
    "/usr/local/lib/gcc48/libgomp.so",
    "/usr/local/lib/gcc48/libitm.spec",
    "/usr/local/lib/gcc48/libitm.so.1",
    "/usr/local/lib/gcc48/libitm.so"
]


def main():
    for i in files_to_save:
        sh('mv ${WORLD_DESTDIR}/${i} ${WORLD_DESTDIR}/${i}.bak')

    chroot('${WORLD_DESTDIR}', 'pkg delete -y -f gcc\* || true')

    for i in files_to_save:
        sh('mv ${WORLD_DESTDIR}/${i}.bak ${WORLD_DESTDIR}/${i}')


if __name__ == '__main__':
    main()