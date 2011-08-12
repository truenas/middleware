#!/usr/local/bin/python
#- 
# Copyright (c) 2011 iXsystems, Inc.
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

import errno
import os
import sys
import stat


WWW_PATH = "/usr/local/www"
FREENASUI_PATH = os.path.join(WWW_PATH, "freenasUI")

sys.path.append(WWW_PATH)
sys.path.append(FREENASUI_PATH)

os.environ["DJANGO_SETTINGS_MODULE"] = "freenasUI.settings"

from freenasUI.common.freenascache import *
from freenasUI.common.freenasldap import *

def usage():
    print >> sys.stderr, "Usage: %s <fill|expire>" % sys.argv[0]
    sys.exit(1)


def cache_fill(cachedir):
    for u in FreeNAS_Users():
        pass
    for g in FreeNAS_Groups():
        pass


def cache_expire(cachedir):
    files = os.listdir(cachedir)
    for f in files:
        file = os.path.join(cachedir, f)
        st = os.stat(file)

        if stat.S_ISDIR(st.st_mode):
            cache_expire(file)

        else:
            os.unlink(file)


    #
    #   The cache is in /var/tmp/.cache, which is a mounted
    #   ramdisk. When trying to delete this directory after
    #   recursively removing other directories, this will fail
    #   with 'Device Busy' errno = 16, so this cheap hack works
    #   around this ;-)
    #
    try:
        os.rmdir(cachedir)

    except OSError, oe:
        if oe.errno == errno.EBUSY:
            pass
        else:
            raise

def cache_dump(cachedir):
    print "FreeNAS_Users:"
    for u in FreeNAS_Users():
        print "    ", u

    print "\n\n"

    print "FreeNAS_Groups:"
    for g in FreeNAS_Groups():
        print "    ", g


def main():
    cache_funcs = {}
    cache_funcs['fill'] = cache_fill
    cache_funcs['expire'] = cache_expire
    cache_funcs['dump'] = cache_dump

    if len(sys.argv) < 2:
        usage()

    if not sys.argv[1] in cache_funcs.keys():
        usage()

    (cache_funcs[sys.argv[1]])(FREENAS_CACHEDIR)

if __name__ == '__main__':
    main()

