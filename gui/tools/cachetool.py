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
from freenasUI.common.freenasldap import *
from freenasUI.common.freenasusers import *

def usage(keys):
    print >> sys.stderr, "Usage: %s <%s>" % (sys.argv[0], join(keys, '|'))
    sys.exit(1)


def cache_fill(**kwargs):
    for u in FreeNAS_Users(flags=FLAGS_DBINIT|FLAGS_CACHE_WRITE_USER):
        pass
    for g in FreeNAS_Groups(flags=FLAGS_DBINIT|FLAGS_CACHE_WRITE_GROUP):
        pass


def __cache_expire(cachedir):
    """Nuke everything under cachedir, but preserve the root directory
       hierarchy so it doesn't screw up certain services like smbd,
       etc."""

    for ent in os.listdir(cachedir):
        p = os.path.join(cachedir, ent)
        if os.path.isdir(p):
            # Delete all cached information (subdirectories and files)
            # under /var/tmp/.cache/.{ldap,samba,..}.
            for root, dirs, files, in os.walk(p, topdown=False):
                map(lambda f: os.unlink(os.path.join(root, f)), files)
                map(lambda d: os.rmdir(os.path.join(root, d)), dirs)
        else:
            # Some other random file that probably doesn't belong here.
            os.unlink(p)

def cache_expire(**kwargs):
    if kwargs.has_key('cachedir') and kwargs['cachedir']:
        __cache_expire(kwargs['cachedir'])


def cache_dump(**kwargs):
    print "FreeNAS_Users:"
    for u in FreeNAS_Users(flags=FLAGS_DBINIT|FLAGS_CACHE_READ_USER):
        print "    ", u

    print "\n\n"

    print "FreeNAS_Groups:"
    for g in FreeNAS_Groups(flags=FLAGS_DBINIT|FLAGS_CACHE_READ_GROUP):
        print "    ", g


def _cache_keys_ActiveDirectory(**kwargs):
    ad = FreeNAS_ActiveDirectory(flags=FLAGS_DBINIT)
    domains = ad.get_domains()
    for d in domains:
        workgroup = d['nETBIOSName']
        print "w: %s" % workgroup 

        ucache = FreeNAS_UserCache(dir=workgroup)
        for key in ucache.keys():
            print "u key: %s" % key

        gcache = FreeNAS_GroupCache(dir=workgroup)
        for key in gcache.keys():
            print "g key: %s" % key

        ducache = FreeNAS_Directory_UserCache(dir=workgroup)
        for key in ducache.keys():
            print "du key: %s" % key

        dgcache = FreeNAS_Directory_GroupCache(dir=workgroup)
        for key in dgcache.keys():
            print "dg key: %s" % key

def _cache_keys_default(**kwargs):
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

def cache_keys(**kwargs):
    if ActiveDirectoryEnabled():
        _cache_keys_ActiveDirectory(**kwargs)

    elif LDAPEnabled():
        _cache_keys_default(**kwargs)

    else:
        _cache_keys_default(**kwargs)


def _cache_rawdump_ActiveDirectory(**kwargs):
    ad = FreeNAS_ActiveDirectory(flags=FLAGS_DBINIT)
    domains = ad.get_domains()
    for d in domains:
        workgroup = d['nETBIOSName']
        print "w: %s" % workgroup 

        ucache = FreeNAS_UserCache(dir=workgroup)
        for key in ucache.keys():
            print "u: %s=%s" % (key, ucache[key])

        gcache = FreeNAS_GroupCache(dir=workgroup)
        for key in gcache.keys():
            print "g: %s=%s" % (key, gcache[key])

        ducache = FreeNAS_Directory_UserCache(dir=workgroup)
        for key in ducache.keys():
            print "du: %s=%s" % (key, ducache[key])

        dgcache = FreeNAS_Directory_GroupCache(dir=workgroup)
        for key in dgcache.keys():
            print "dg: %s=%s" % (key, dgcache[key])

def _cache_rawdump_default(**kwargs):
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

def cache_rawdump(**kwargs):
    if ActiveDirectoryEnabled():
        _cache_rawdump_ActiveDirectory(**kwargs)

    elif LDAPEnabled():
        _cache_rawdump_default(**kwargs)

    else:
        _cache_rawdump_default(**kwargs)


def _cache_check_ActiveDirectory(**kwargs):
    if not kwargs.has_key('args') and kwargs['args']:
        return

    valid = {}
    ad = FreeNAS_ActiveDirectory(flags=FLAGS_DBINIT)
    domains = ad.get_domains()
    for d in domains:
        valid[d['nETBIOSName']] = True

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
            if not valid.has_key(workgroup):
                continue

            ucache = FreeNAS_UserCache(dir=workgroup)
            gcache = FreeNAS_GroupCache(dir=workgroup)
            ducache = FreeNAS_Directory_UserCache(dir=workgroup)
            dgcache = FreeNAS_Directory_GroupCache(dir=workgroup)

            if key == 'u':
                if ucache.has_key(val) and ucache[val]:
                    print "%s: %s" % (val, ucache[val])

            elif key == 'g':
                if gcache.has_key(val) and gcache[val]:
                    print "%s: %s" % (val, gcache[val])


        elif key in ('du', 'dg'):
            for workgroup in valid.keys():
                ucache = FreeNAS_UserCache(dir=workgroup)
                gcache = FreeNAS_GroupCache(dir=workgroup)
                ducache = FreeNAS_Directory_UserCache(dir=workgroup)
                dgcache = FreeNAS_Directory_GroupCache(dir=workgroup)

                if key == 'du':
                    if ducache.has_key(val) and ducache[val]:
                        print "%s: %s" % (val, ducache[val])

                elif key == 'dg':
                    if dgache.has_key(val) and dgcache[val]:
                        print "%s: %s" % (val, dgcache[val])
         

def _cache_check_default(**kwargs):
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

def cache_check(**kwargs):
    if ActiveDirectoryEnabled():
        _cache_check_ActiveDirectory(**kwargs) 

    elif LDAPEnabled():
        _cache_check_default(**kwargs)
     
    else:
        _cache_check_default(**kwargs)



def _cache_count_ActiveDirectory(**kwargs):
    ad = FreeNAS_ActiveDirectory(flags=FLAGS_DBINIT)
    domains = ad.get_domains()
    for d in domains:
        workgroup = d['nETBIOSName']
        print "w:  %s" % workgroup
        print "u:  %ld" % len(FreeNAS_UserCache(dir=workgroup))
        print "g:  %ld" % len(FreeNAS_GroupCache(dir=workgroup))
        print "du: %ld" % len(FreeNAS_Directory_UserCache(dir=workgroup))
        print "dg: %ld" % len(FreeNAS_Directory_GroupCache(dir=workgroup))
        print "\n"

def _cache_count_default(**kwargs):
    print "u:  %ld" % len(FreeNAS_UserCache())
    print "g:  %ld" % len(FreeNAS_GroupCache())
    print "du: %ld" % len(FreeNAS_Directory_UserCache())
    print "dg: %ld" % len(FreeNAS_Directory_GroupCache())
    print "\n"

def cache_count(**kwargs):
    if ActiveDirectoryEnabled():
        _cache_count_ActiveDirectory(**kwargs)

    elif LDAPEnabled():
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
        usage(cache_funcs.keys())

    if not sys.argv[1] in cache_funcs.keys():
        usage(cache_funcs.keys())

    kwargs = {}
    kwargs['cachedir'] = FREENAS_CACHEDIR
    kwargs['args'] = sys.argv[2:]

    (cache_funcs[sys.argv[1]])(**kwargs)

if __name__ == '__main__':
    main()

