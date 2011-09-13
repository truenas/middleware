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

from string import join

WWW_PATH = "/usr/local/www"
FREENASUI_PATH = os.path.join(WWW_PATH, "freenasUI")

sys.path.append(WWW_PATH)
sys.path.append(FREENASUI_PATH)

os.environ["DJANGO_SETTINGS_MODULE"] = "freenasUI.settings"

from freenasUI.common.freenascache import *
from freenasUI.common.freenasusers import *

def usage(keys):
    print >> sys.stderr, "Usage: %s <%s>" % (sys.argv[0], join(keys, '|'))
    sys.exit(1)


def cache_fill(**kwargs):
    for u in FreeNAS_Users():
        pass
    for g in FreeNAS_Groups():
        pass


def __cache_expire(cachedir):
    files = os.listdir(cachedir)
    for f in files:
        file = os.path.join(cachedir, f)
        st = os.stat(file)

        if stat.S_ISDIR(st.st_mode):
            __cache_expire(file)

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


def cache_expire(**kwargs):
    if kwargs.has_key('cachedir') and kwargs['cachedir']:
        __cache_expire(kwargs['cachedir'])


def cache_dump(**kwargs):
    print "FreeNAS_Users:"
    for u in FreeNAS_Users():
        print "    ", u

    print "\n\n"

    print "FreeNAS_Groups:"
    for g in FreeNAS_Groups():
        print "    ", g


def cache_keys(**kwargs):
    ucache = FreeNAS_UserCache()
    for key in ucache.keys():
        print "u key: %s" % key

    gcache = FreeNAS_GroupCache()
    for key in gcache.keys():
        print "g key: %s" % key

    ducache = FreeNAS_Directory_UserCache()
    for key in ducache.keys():
        print "du key: %s" % key

    dgcache = FreeNAS_Directory_GroupCache()
    for key in dgcache.keys():
        print "dg key: %s" % key


def cache_rawdump(**kwargs):
    ucache = FreeNAS_UserCache()
    for key in ucache.keys():
        print "u: %s=%s" % (key, ucache[key])

    gcache = FreeNAS_GroupCache()
    for key in gcache.keys():
        print "g: %s=%s" % (key, gcache[key])

    ducache = FreeNAS_Directory_UserCache()
    for key in ducache.keys():
        print "du: %s=%s" % (key, ducache[key])

    dgcache = FreeNAS_Directory_GroupCache()
    for key in dgcache.keys():
        print "dg: %s=%s" % (key, dgcache[key])


def cache_check(**kwargs):
    if not kwargs.has_key('args') and kwargs['args']:
        return

    ucache = FreeNAS_UserCache()
    gcache = FreeNAS_GroupCache()
    ducache = FreeNAS_Directory_UserCache()
    dgcache = FreeNAS_Directory_GroupCache()

    for arg in kwargs['args']:
        key = val = None
        try:
            parts = arg.split('=')
            key = parts[0]
            val = join(parts[1:], '=')

        except:
            continue

        if key == 'u':
            if ucache.has_key(val) and ucache[val]:
                print "%s: %s" % (val, ucache[val])

        elif key == 'g':
            if gcache.has_key(val) and gcache[val]:
                print "%s: %s" % (val, gcache[val])

        elif key == 'du':
            if ducache.has_key(val) and ducache[val]:
                print "%s: %s" % (val, ducache[val])

        elif key == 'dg':
            if dgache.has_key(val) and dgcache[val]:
                print "%s: %s" % (val, dgcache[val])


def cache_count(**kwargs):

    ucache = FreeNAS_UserCache()
    gcache = FreeNAS_GroupCache()
    ducache = FreeNAS_Directory_UserCache()
    dgcache = FreeNAS_Directory_GroupCache()

    print "u: %ld" % len(ucache)
    print "g: %ld" % len(gcache)
    print "du: %ld" % len(ducache)
    print "dg: %ld" % len(dgcache)


def main():
    cache_funcs = {}
    cache_funcs['fill'] = cache_fill
    cache_funcs['expire'] = cache_expire
    cache_funcs['dump'] = cache_dump
    cache_funcs['keys'] = cache_keys
    cache_funcs['rawdump'] = cache_rawdump
    cache_funcs['check'] = cache_check
    cache_funcs['count'] = cache_count

    if len(sys.argv) < 2:
        usage(cache_funcs.keys())

    if not sys.argv[1] in cache_funcs.keys():
        usage(cache_funcs.keys())

    kwargs = {}
    kwargs['cachedir'] = FREENAS_CACHEDIR
    kwargs['args'] = sys.argv[2:]

    (cache_funcs[sys.argv[1]])(**kwargs)

if __name__ == '__main__':
    main()

