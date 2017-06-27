#!/usr/local/bin/python
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

import os
import sys

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI'
])

os.environ["DJANGO_SETTINGS_MODULE"] = "freenasUI.settings"

import django
django.setup()

from freenasUI.common.system import (
    activedirectory_enabled,
    ldap_enabled,
    nis_enabled
)

from freenasUI.common.freenascache import (
    FreeNAS_UserCache,
    FreeNAS_GroupCache,
    FreeNAS_Directory_UserCache,
    FreeNAS_Directory_GroupCache,
    FREENAS_CACHEDIR
)

from freenasUI.common.freenasldap import (
    FreeNAS_ActiveDirectory,
    FLAGS_DBINIT,
    FLAGS_CACHE_READ_USER,
    FLAGS_CACHE_WRITE_USER,
    FLAGS_CACHE_READ_GROUP,
    FLAGS_CACHE_WRITE_GROUP
)

from freenasUI.common.freenasnis import FreeNAS_NIS
from freenasUI.common.freenasusers import (
    FreeNAS_Users,
    FreeNAS_Groups
)


def usage(keys):
    print("Usage: %s <%s>" % (sys.argv[0], '|'.join(keys)), file=sys.stderr)
    sys.exit(1)


def _cachelen(cache):
    cachelen = 0

    try:
        cachelen = len(cache)

    except:
        cachelen = 0

    return cachelen


def cache_fill(**kwargs):
    uargs = {'flags': FLAGS_DBINIT | FLAGS_CACHE_WRITE_USER}
    gargs = {'flags': FLAGS_DBINIT | FLAGS_CACHE_WRITE_GROUP}

    for u in FreeNAS_Users(**uargs):
        pass
    for g in FreeNAS_Groups(**gargs):
        pass


def __cache_expire(cachedir):
    """Nuke everything under cachedir, but preserve the root directory
       hierarchy so it doesn't screw up certain services like smbd,
       etc."""
    if not os.path.exists(cachedir):
        return

    for ent in os.listdir(cachedir):
        p = os.path.join(cachedir, ent)
        if os.path.isdir(p):
            # Delete all cached information (subdirectories and files)
            # under /var/tmp/.cache/.{ldap,samba,..}.
            for root, dirs, files, in os.walk(p, topdown=False):
                list(map(lambda f: os.unlink(os.path.join(root, f)), files))
                list(map(lambda d: os.rmdir(os.path.join(root, d)), dirs))
        else:
            # Some other random file that probably doesn't belong here.
            os.unlink(p)


def cache_expire(**kwargs):
    if 'cachedir' in kwargs and kwargs['cachedir']:
        __cache_expire(kwargs['cachedir'])


def cache_dump(**kwargs):
    print("FreeNAS_Users:")
    for u in FreeNAS_Users(flags=FLAGS_DBINIT | FLAGS_CACHE_READ_USER):
        print("    ", u)

    print("\n\n")

    print("FreeNAS_Groups:")
    for g in FreeNAS_Groups(flags=FLAGS_DBINIT | FLAGS_CACHE_READ_GROUP):
        print("    ", g)


def _cache_keys_ActiveDirectory(**kwargs):
    ad = FreeNAS_ActiveDirectory(flags=FLAGS_DBINIT)
    domains = ad.get_domains()
    for d in domains:
        workgroup = d['nETBIOSName']

        print("w: %s" % workgroup)

        ucache = FreeNAS_UserCache(dir=workgroup)
        if ucache:
            for key in list(ucache.keys()):
                print("u key: %s" % key)

        gcache = FreeNAS_GroupCache(dir=workgroup)
        if gcache:
            for key in list(gcache.keys()):
                print("g key: %s" % key)

        ducache = FreeNAS_Directory_UserCache(dir=workgroup)
        if ducache:
            for key in list(ducache.keys()):
                print("du key: %s" % key)

        dgcache = FreeNAS_Directory_GroupCache(dir=workgroup)
        if dgcache:
            for key in list(dgcache.keys()):
                print("dg key: %s" % key)


def _cache_keys_NIS(**kwargs):
    nis = FreeNAS_NIS(flags=FLAGS_DBINIT)
    domains = nis.get_domains()
    for d in domains:
        print("d: %s" % d)

        ucache = FreeNAS_UserCache(dir=d)
        if ucache:
            for key in list(ucache.keys()):
                print("u key: %s" % key)

        gcache = FreeNAS_GroupCache(dir=d)
        if gcache:
            for key in list(gcache.keys()):
                print("g key: %s" % key)

        ducache = FreeNAS_Directory_UserCache(dir=d)
        if ducache:
            for key in list(ducache.keys()):
                print("du key: %s" % key)

        dgcache = FreeNAS_Directory_GroupCache(dir=d)
        if dgcache:
            for key in list(dgcache.keys()):
                print("dg key: %s" % key)


def _cache_keys_default(**kwargs):
    ucache = FreeNAS_UserCache()
    if ucache:
        for key in list(ucache.keys()):
            print("u key: %s" % key)

    gcache = FreeNAS_GroupCache()
    if gcache:
        for key in list(gcache.keys()):
            print("g key: %s" % key)

    ducache = FreeNAS_Directory_UserCache()
    if ducache:
        for key in list(ducache.keys()):
            print("du key: %s" % key)

    dgcache = FreeNAS_Directory_GroupCache()
    if dgcache:
        for key in list(dgcache.keys()):
            print("dg key: %s" % key)


def cache_keys(**kwargs):
    if activedirectory_enabled():
        _cache_keys_ActiveDirectory(**kwargs)

    elif nis_enabled():
        _cache_keys_NIS(**kwargs)

    elif ldap_enabled():
        _cache_keys_default(**kwargs)

    else:
        _cache_keys_default(**kwargs)


def _cache_rawdump_ActiveDirectory(**kwargs):
    ad = FreeNAS_ActiveDirectory(flags=FLAGS_DBINIT)
    domains = ad.get_domains()
    for d in domains:
        workgroup = d['nETBIOSName']

        print("w: %s" % workgroup)

        ucache = FreeNAS_UserCache(dir=workgroup)
        if ucache:
            for key in list(ucache.keys()):
                print("u: %s=%s" % (key, ucache[key]))

        gcache = FreeNAS_GroupCache(dir=workgroup)
        if gcache:
            for key in list(gcache.keys()):
                print("g: %s=%s" % (key, gcache[key]))

        ducache = FreeNAS_Directory_UserCache(dir=workgroup)
        if ducache:
            for key in list(ducache.keys()):
                print("du: %s=%s" % (key, ducache[key]))

        dgcache = FreeNAS_Directory_GroupCache(dir=workgroup)
        if dgcache:
            for key in list(dgcache.keys()):
                print("dg: %s=%s" % (key, dgcache[key]))


def _cache_rawdump_NIS(**kwargs):
    nis = FreeNAS_NIS(flags=FLAGS_DBINIT)
    domains = nis.get_domains()
    for d in domains:
        print("d: %s" % d)

        ucache = FreeNAS_UserCache(dir=d)
        if ucache:
            for key in list(ucache.keys()):
                print("u: %s=%s" % (key, ucache[key]))

        gcache = FreeNAS_GroupCache(dir=d)
        if gcache:
            for key in list(gcache.keys()):
                print("g: %s=%s" % (key, gcache[key]))

        ducache = FreeNAS_Directory_UserCache(dir=d)
        if ducache:
            for key in list(ducache.keys()):
                print("du: %s=%s" % (key, ducache[key]))

        dgcache = FreeNAS_Directory_GroupCache(dir=d)
        if dgcache:
            for key in list(dgcache.keys()):
                print("dg: %s=%s" % (key, dgcache[key]))


def _cache_rawdump_default(**kwargs):
    ucache = FreeNAS_UserCache()
    for key in list(ucache.keys()):
        print("u: %s=%s" % (key, ucache[key]))

    gcache = FreeNAS_GroupCache()
    if gcache:
        for key in list(gcache.keys()):
            print("g: %s=%s" % (key, gcache[key]))

    ducache = FreeNAS_Directory_UserCache()
    if ducache:
        for key in list(ducache.keys()):
            print("du: %s=%s" % (key, ducache[key]))

    dgcache = FreeNAS_Directory_GroupCache()
    if dgcache:
        for key in list(dgcache.keys()):
            print("dg: %s=%s" % (key, dgcache[key]))


def cache_rawdump(**kwargs):
    if activedirectory_enabled():
        _cache_rawdump_ActiveDirectory(**kwargs)

    elif nis_enabled():
        _cache_rawdump_NIS(**kwargs)

    elif ldap_enabled():
        _cache_rawdump_default(**kwargs)

    else:
        _cache_rawdump_default(**kwargs)


def _cache_check_ActiveDirectory(**kwargs):
    if 'args' not in kwargs and kwargs['args']:
        return

    valid = {}
    ad = FreeNAS_ActiveDirectory(flags=FLAGS_DBINIT)
    domains = ad.get_domains()
    for d in domains:
        workgroup = d['nETBIOSName']
        valid[workgroup] = True

    for arg in kwargs['args']:
        key = val = None

        if arg.startswith("u="):
            key = "u"
            val = arg.partition("u=")[2]

        elif arg.startswith("g="):
            key = "g"
            val = arg.partition("g=")[2]

        elif arg.startswith("du="):
            key = "du"
            val = arg.partition("du=")[2]

        elif arg.startswith("dg="):
            key = "dg"
            val = arg.partition("dg=")[2]

        else:
            continue

        if key in ('u', 'g'):
            parts = val.split('\\')
            if len(parts) < 2:
                continue

            workgroup = parts[0]
            if workgroup not in valid:
                continue

            ucache = FreeNAS_UserCache(dir=workgroup)
            gcache = FreeNAS_GroupCache(dir=workgroup)
            ducache = FreeNAS_Directory_UserCache(dir=workgroup)
            dgcache = FreeNAS_Directory_GroupCache(dir=workgroup)

            if key == 'u':
                if ucache and val in ucache and ucache[val]:
                    print("%s: %s" % (val, ucache[val]))

            elif key == 'g':
                if gcache and val in gcache and gcache[val]:
                    print("%s: %s" % (val, gcache[val]))

        elif key in ('du', 'dg'):
            for workgroup in list(valid.keys()):
                ucache = FreeNAS_UserCache(dir=workgroup)
                gcache = FreeNAS_GroupCache(dir=workgroup)
                ducache = FreeNAS_Directory_UserCache(dir=workgroup)
                dgcache = FreeNAS_Directory_GroupCache(dir=workgroup)

                if key == 'du':
                    if ducache and val in ducache and ducache[val]:
                        print("%s: %s" % (val, ducache[val]))

                elif key == 'dg':
                    if dgcache and val in dgcache and dgcache[val]:
                        print("%s: %s" % (val, dgcache[val]))


def _cache_check_NIS(**kwargs):
    if 'args' not in kwargs and kwargs['args']:
        return

    valid = {}
    nis = FreeNAS_NIS(flags=FLAGS_DBINIT)
    domains = nis.get_domains()
    for d in domains:
        valid[d] = True

    for arg in kwargs['args']:
        key = val = None

        if arg.startswith("u="):
            key = "u"
            val = arg.partition("u=")[2]

        elif arg.startswith("g="):
            key = "g"
            val = arg.partition("g=")[2]

        elif arg.startswith("du="):
            key = "du"
            val = arg.partition("du=")[2]

        elif arg.startswith("dg="):
            key = "dg"
            val = arg.partition("dg=")[2]

        else:
            continue

        if key in ('u', 'g'):
            parts = val.split('\\')
            if len(parts) < 2:
                continue

            d = parts[0]
            if d not in valid:
                continue

            ucache = FreeNAS_UserCache(dir=d)
            gcache = FreeNAS_GroupCache(dir=d)
            ducache = FreeNAS_Directory_UserCache(dir=d)
            dgcache = FreeNAS_Directory_GroupCache(dir=d)

            if key == 'u':
                if ucache and val in ucache and ucache[val]:
                    print("%s: %s" % (val, ucache[val]))

            elif key == 'g':
                if gcache and val in gcache and gcache[val]:
                    print("%s: %s" % (val, gcache[val]))

        elif key in ('du', 'dg'):
            for d in list(valid.keys()):
                ucache = FreeNAS_UserCache(dir=d)
                gcache = FreeNAS_GroupCache(dir=d)
                ducache = FreeNAS_Directory_UserCache(dir=d)
                dgcache = FreeNAS_Directory_GroupCache(dir=d)

                if key == 'du':
                    if ducache and val in ducache and ducache[val]:
                        print("%s: %s" % (val, ducache[val]))

                elif key == 'dg':
                    if dgcache and val in dgcache and dgcache[val]:
                        print("%s: %s" % (val, dgcache[val]))


def _cache_check_default(**kwargs):
    if not ('args' in kwargs and kwargs['args']):
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
            val = '='.join(parts[1:])

        except:
            continue

        if key == 'u':
            if ucache and val in ucache and ucache[val]:
                print("%s: %s" % (val, ucache[val]))

        elif key == 'g':
            if gcache and val in gcache and gcache[val]:
                print("%s: %s" % (val, gcache[val]))

        elif key == 'du':
            if ducache and val in ducache and ducache[val]:
                print("%s: %s" % (val, ducache[val]))

        elif key == 'dg':
            if dgcache and val in dgcache and dgcache[val]:
                print("%s: %s" % (val, dgcache[val]))


def cache_check(**kwargs):
    if activedirectory_enabled():
        _cache_check_ActiveDirectory(**kwargs)

    elif nis_enabled():
        _cache_check_NIS(**kwargs)

    elif ldap_enabled():
        _cache_check_default(**kwargs)

    else:
        _cache_check_default(**kwargs)


def _cache_count_ActiveDirectory(**kwargs):
    ad = FreeNAS_ActiveDirectory(flags=FLAGS_DBINIT)
    domains = ad.get_domains()
    for d in domains:
        workgroup = d['nETBIOSName']

        print("w:  %s" % workgroup)
        print("u:  %ld" % _cachelen(FreeNAS_UserCache(dir=workgroup)))
        print("g:  %ld" % _cachelen(FreeNAS_GroupCache(dir=workgroup)))
        print("du: %ld" % _cachelen(FreeNAS_Directory_UserCache(dir=workgroup)))
        print("dg: %ld" % _cachelen(FreeNAS_Directory_GroupCache(dir=workgroup)))
        print("\n")


def _cache_count_NIS(**kwargs):
    nis = FreeNAS_NIS(flags=FLAGS_DBINIT)
    domains = nis.get_domains()
    for d in domains:
        print("d:  %s" % d)
        print("u:  %ld" % _cachelen(FreeNAS_UserCache(dir=d)))
        print("g:  %ld" % _cachelen(FreeNAS_GroupCache(dir=d)))
        print("du: %ld" % _cachelen(FreeNAS_Directory_UserCache(dir=d)))
        print("dg: %ld" % _cachelen(FreeNAS_Directory_GroupCache(dir=d)))
        print("\n")


def _cache_count_default(**kwargs):
    print("u:  %ld" % _cachelen(FreeNAS_UserCache()))
    print("g:  %ld" % _cachelen(FreeNAS_GroupCache()))
    print("du: %ld" % _cachelen(FreeNAS_Directory_UserCache()))
    print("dg: %ld" % _cachelen(FreeNAS_Directory_GroupCache()))
    print("\n")


def cache_count(**kwargs):
    if activedirectory_enabled():
        _cache_count_ActiveDirectory(**kwargs)

    elif nis_enabled():
        _cache_count_NIS(**kwargs)

    elif ldap_enabled():
        _cache_count_default(**kwargs)

    else:
        _cache_count_default(**kwargs)


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
        usage(list(cache_funcs.keys()))

    if not sys.argv[1] in list(cache_funcs.keys()):
        usage(list(cache_funcs.keys()))

    kwargs = {}
    kwargs['cachedir'] = FREENAS_CACHEDIR
    kwargs['args'] = sys.argv[2:]

    (cache_funcs[sys.argv[1]])(**kwargs)


if __name__ == '__main__':
    main()
