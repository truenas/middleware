#!/usr/local/bin/python

import getopt
import grp
import os
import pwd
import re
import string
import sys

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI'
])

os.environ["DJANGO_SETTINGS_MODULE"] = "freenasUI.settings"

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI.common.freenasacl import ACL

class WindowsACLSet(object):
    def __init__(self, *args, **kwargs):
        self.only_files = False
        self.only_directories = False
        self.owner_permissions = None
        self.group_permissions = None
        self.everyone_permissions = None
        self.owner = None
        self.group = None
        self.append = False
        self.remove = False
        self.update = False
        self.recursive = False
        self.verbose = False
        self.reset = False
        self.path = None

        self.default_owner_permissions = "owner@:rwxpDdaARWcCos:fd:allow"
        self.default_group_permissions = "group@:rwxpDdaARWcCos:fd:allow"
        self.default_everyone_permissions = "everyone@:rxDaRc:fd:allow"

        for key in kwargs:
            if key in self.__dict__:
                self.__dict__[key] = kwargs[key]

        if self.reset:
            self.owner_permissions = self.default_owner_permissions
            self.group_permissions = self.default_group_permissions
            self.everyone_permissions = self.default_everyone_permissions

    def parse(self, entry):
        if not entry:    
            print >> sys.stderr, "parse: NULL ACL entry"
            sys.exit(1)
        parts = entry.split(':')     
        if len(parts) < 4:
            print >> sys.stderr, "parse: %s: invalid ACL entry" % parts[0]
            sys.exit(1)

        acl_entry = {
            'tag': None,
            'qualifier': None,
            'permissions': None,
            'inheritance_flags': None,
            'type': None
        }

        if len(parts) == 4:
            acl_entry['tag'] = parts[0]
            acl_entry['qualifier'] = None
            acl_entry['permissions'] = parts[1]
            acl_entry['inheritance_flags'] =  parts[2]
            acl_entry['type'] = parts[3]

        elif len(parts) == 5:
            acl_entry['tag'] = parts[0]
            acl_entry['qualifier'] = parts[1]
            acl_entry['permissions'] = parts[2]
            acl_entry['inheritance_flags'] = parts[3]
            acl_entry['type'] = parts[4]

        return acl_entry  

    def __do_set(self, path):
        if self.verbose:
            print >> sys.stdout, "%s" % path
        if self.only_files and os.path.isdir(path):
            return
        if self.only_directories and os.path.isfile(path):
            return

        acl = ACL(path=path)
        if self.reset:
            acl.reset()

        method = acl.update
        if self.append:
            method = acl.add
        elif self.remove:
            method = acl.remove

        if self.owner_permissions:
            owner = self.parse(self.owner_permissions)
            method(owner['tag'], owner['qualifier'],
                owner['permissions'], owner['inheritance_flags'], owner['type'])

        if self.group_permissions:
            group = self.parse(self.group_permissions)
            method(group['tag'], group['qualifier'],
                group['permissions'], group['inheritance_flags'], group['type'])

        if self.everyone_permissions:  
            everyone = self.parse(self.everyone_permissions)
            method(everyone['tag'], everyone['qualifier'],
                everyone['permissions'], everyone['inheritance_flags'], everyone['type'])

        uid = gid = -1
        if self.owner:
            try:
                u = pwd.getpwnam(self.owner)
                uid = u.pw_uid
            except Exception as e:
                print >> sys.stderr, "getpwuid: %s" % e
        if self.group:
            try:
                g = grp.getgrnam(self.group)
                gid = g.gr_gid
            except Exception as e:
                print >> sys.stderr, "getgrgid: %s" % e

        if uid > -1 or gid > -1:
            os.chown(path, uid, gid) 
            

    def set(self):
        if not self.path:
            return    

        for root, dirs, files in os.walk(self.path):
            self.__do_set(root)
            if not self.recursive:
                break  
            for f in files:
                self.__do_set(os.path.join(root, f))


def usage(err):
    if err:
        print >> sys.stderr, "ERROR: %s" % err

    print >> sys.stderr, """
Usage: %s [OPTIONS] ...
Where option is:
    -o <owner permission>        # owner ACL entry
    -g <group permission>        # group ACL entry
    -e <everyone permission>     # everyone ACL entry
    -O <owner>                   # change owner
    -G <group>                   # change group
    -p <path>                    # path to set
    -f                           # only set files
    -d                           # only set directories
    -a                           # append this ACL entry
    -r                           # remove this ACL entry
    -u                           # update this ACL entry
    -R                           # recursive
    -v                           # verbose
    -x                           # reset to default permissions
    """ % sys.argv[0]


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "o:g:e:O:G:p:aRufdrvx")

    except Exception as e:
        usage(e)
        sys.exit(1)

    args = {}
    for opt, arg in opts:
        if opt == '-o':
            args['owner_permissions'] = arg
        elif opt == '-g':
            args['group_permissions'] = arg
        elif opt == '-e':
            args['everyone_permissions'] = arg
        elif opt == '-O':
            args['owner'] = arg
        elif opt == '-G':
            args['group'] = arg
        elif opt == '-p':
            args['path'] = arg
        elif opt == '-a':
            args['append'] = True
        elif opt == '-r':
            args['remove'] = True
        elif opt == '-u':
            args['update'] = True
        elif opt == '-f':
            args['only_files'] = True
        elif opt == '-d':
            args['only_directories'] = True
        elif opt == '-R':
            args['recursive'] = True
        elif opt == '-v':
            args['verbose'] = True
        elif opt == '-x':
            args['reset'] = True

    w = WindowsACLSet(**args)
    if not w.path:
        usage("No path specified")
        sys.exit(1)

    if not (w.append or w.remove or w.update or w.owner or w.group or w.reset):
        usage("Update/Append/Remove or Owner/Group must be specified")
        sys.exit(1)

    if (w.append or w.remove or w.update) and not \
        (w.owner_permissions or w.group_permissions or w.everyone_permissions):
        usage("Owner, group or everyone permissions must be specified")
        sys.exit(1)

    w.set()


if __name__ == '__main__':
    main()
