#+
# Copyright 2010 iXsystems
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
# $FreeBSD$
#####################################################################
import os
import sys
import grp
import pwd
import re

from subprocess import Popen, PIPE

GETFACL_PATH = "/bin/getfacl"
SETFACL_PATH = "/bin/setfacl"

#
# NFSv4 flags only
#
GETFACL_FLAGS_SYMLINK_ACL  = 0x0001
GETFACL_FLAGS_APPEND_IDS   = 0x0002
GETFACL_FLAGS_NUMERIC_IDS  = 0x0004
GETFACL_FLAGS_NO_COMMENTS  = 0x0008
GETFACL_FLAGS_VERBOSE      = 0x0010

#
# NFSv4 flags only
#
SETFACL_FLAGS_MODIFY_ENTRY = 0x0001
SETFACL_FLAGS_SET_DEFAULTS = 0x0002
SETFACL_FLAGS_SYMLINK_OP   = 0x0004
SETFACL_FLAGS_MODIFY       = 0x0008
SETFACL_FLAGS_REMOVE_ENTRY = 0x0010


class NFSv4_ACL_Exception(Exception):
    def __init__(self, msg = None):
        if msg:
            print >> sys.stderr, "NFSv4_ACL_Exception: %s" % msg


class NFSv4_pipe:
    def __init__(self, cmd):
        self.__pipe = Popen(cmd, stdin = PIPE, stdout = PIPE,
            stderr = PIPE, shell = True, close_fds = True)

        self.__stdin = self.__pipe.stdin
        self.__stdout = self.__pipe.stdout
        self.__stderr = self.__pipe.stderr

        self.__out = self.__stdout.read().strip()
        self.__pipe.wait()

        if self.__pipe.returncode != 0:
            raise NFSv4_ACL_Exception(self.__stderr.read().strip())

    def __str__(self):
        return self.__out

    def __iter__(self):
        lines = self.__out.splitlines()
        for line in lines:
            yield line


class NFSv4_getfacl:
    def __init__(self, path, flags = 0):
        self.__getfacl = GETFACL_PATH
        self.__path = path

        args = ""
        if flags & GETFACL_FLAGS_SYMLINK_ACL:
            args += "-h "
        if flags & GETFACL_FLAGS_APPEND_IDS:
            args += "-i "
        if flags & GETFACL_FLAGS_NUMERIC_IDS:
            args += "-n "
        if flags & GETFACL_FLAGS_NO_COMMENTS:
            args += "-q "
        if flags & GETFACL_FLAGS_VERBOSE:
            args += "-v "

        self.__out = str(NFSv4_pipe("%s %s '%s'" % (self.__getfacl, args, self.__path)))

    def __str__(self):
        return self.__out

    def __iter__(self):
        lines = self.__out.splitlines()
        for line in lines:
            yield line


class NFSv4_setfacl:
    def __init__(self, path, entry, flags = 0, pos = 0):
        self.__setfacl = SETFACL_PATH
        self.__path = path
        self.__entry = entry

        args = ""
        if flags & SETFACL_FLAGS_MODIFY_ENTRY:
            args += "-a %d" % pos
        if flags & SETFACL_FLAGS_SET_DEFAULTS:
            args += "-b "
        if flags & SETFACL_FLAGS_SYMLINK_OP:
            args += "-h "
        if flags & SETFACL_FLAGS_MODIFY:
            args += "-m "
        if flags & SETFACL_FLAGS_REMOVE_ENTRY:
            args += "-x "

        self.__out = str(NFSv4_pipe("%s %s '%s' '%s'" % (self.__setfacl, args, self.__entry, self.__path)))


class NFSv4_ACL_Entry:
    def __init__(self):

        #
        # ACL tag
        #
        self.tag = None

        #
        # ACL qualifier
        #
        self.qualifier = None

        #
        # Access Permissions
        #
        self.read_data = False
        self.write_data = False
        self.execute = False
        self.append_data = False
        self.delete_child = False
        self.delete = False
        self.read_attributes = False
        self.write_attributes = False
        self.read_xattr = False
        self.write_xattr = False
        self.read_acl = False
        self.write_acl = False
        self.write_owner = False
        self.synchronize = False

        #
        # ACL Inheritance Flags
        #
        self.file_inherit = False
        self.dir_inherit = False
        self.inherit_only = False
        self.no_propagate = False

        #
        # ACL type
        #
        self.type = None

    def __set_access_permission(self, permission, value):
        if permission == 'r':
            self.read_data = value
        elif permission == 'w':
            self.write_data = value
        elif permission == 'x':
            self.execute = value
        elif permission == 'p':
            self.append_data = value
        elif permission == 'd':
            self.delete_child = value
        elif permission == 'D':
            self.delete = value
        elif permission == 'a':
            self.read_attributes = value
        elif permission == 'A':
            self.write_attributes = value
        elif permission == 'R':
            self.read_xattr = value
        elif permission == 'W':
            self.write_xattr = value
        elif permission == 'c':
            self.read_acl = value
        elif permission == 'C':
            self.write_acl = value
        elif permission == 'o':
            self.write_owner = value
        elif permission == 'S':
            self.synchronize = value

    def __set_access_permissions(self, permissions):
        self.clear_access_permissions()
        for p in permissions:
            if p == '-':
                continue
            self.__set_access_permission(p)

    def set_access_permission(self, permission):
        self.__set_access_permission(permission, True)

    def clear_access_permissions(self):
        self.read_data = False
        self.write_data = False
        self.execute = False
        self.append_data = False
        self.delete_child = False
        self.delete = False
        self.read_attributes = False
        self.write_attributes = False
        self.read_xattr = False
        self.write_xattr = False
        self.read_acl = False
        self.write_acl = False
        self.write_owner = False
        self.synchronize = False

    def clear_access_permission(self, permission):
        self.__set_access_permission(permission, False)

    def __set_inheritance_flag(self, flag, value):
        if flag == 'f':
            self.file_inherit = value
        elif flag == 'd':
            self.dir_inherit = value
        elif flag == 'i':
            self.inherit_only = value
        elif flag == 'n':
            self.no_propagate = value

    def __set_inheritance_flags(self, flags):
        self.clear_inheritance_flags()
        for f in inheritance_flags:
            if f == '-':
                continue
            self.__set_inheritance_flag(f)

    def set_inheritance_flag(self, flag):
        self.__set_inheritance_flag(flag, True)

    def clear_inheritance_flags(self):
        self.file_inherit = False
        self.dir_inherit = False
        self.inherit_only = False
        self.no_propagate = False

    def clear_inheritance_flag(self, flag):
        self.__set_inheritance_flag(flag, False)

    def __str__(self):
        str = self.tag

        if self.qualifier:
            str = str + ":" + self.qualifier

        str = str + ":"
        str = str + ('r' if self.read_data else '-')
        str = str + ('w' if self.write_data else '-')
        str = str + ('x' if self.execute else '-')
        str = str + ('p' if self.append_data else '-')
        str = str + ('d' if self.delete_child else '-')
        str = str + ('D' if self.delete else '-')
        str = str + ('a' if self.read_attributes else '-')
        str = str + ('A' if self.write_attributes else '-')
        str = str + ('R' if self.read_xattr else '-')
        str = str + ('W' if self.write_xattr else '-')
        str = str + ('c' if self.read_acl else '-')
        str = str + ('C' if self.write_acl else '-')
        str = str + ('o' if self.write_owner else '-')
        str = str + ('S' if self.synchronize else '-')

        str = str + ":"
        str = str + ('f' if self.file_inherit else '-')
        str = str + ('d' if self.dir_inherit else '-')
        str = str + ('i' if self.inherit_only else '-')
        str = str + ('n' if self.no_propagate else '-')

        str = str + ":" + self.type
        return str


class NFSv4_ACL:
    def __init__(self, path, acl = None):

        #
        # Array of NFSv4_Entry's
        #
        self.__entries = []
        self.file = None
        self.owner = None
        self.group = None

        self.__dirty = False
        self.__path = path
        self.__get() 

    def __get(self):
        for line in NFSv4_getfacl(self.__path):
            if line.startswith("#"):
                comment_parts = line.split('#')[1:]
                for c in comment_parts:
                    c = c.strip()

                    parts = c.split(":") 
                    if parts[0] == 'file':
                        self.file = parts[1]
                    elif parts[0] == 'owner':
                        self.owner = parts[1] 
                    elif parts[0] == 'group':
                        self.group = parts[1] 

            else:
                line = line.strip()
                parts = line.split(':')

                entry = NFSv4_ACL_Entry()
                entry.tag = parts[0]

                #
                # In '(owner|group|everyone)@' entries, qualifier is ommited.
                #
                if not parts[0].endswith("@"):
                    entry.qualifier = parts[1]
                    access_permissions = parts[2]
                    acl_inheritance_flags = parts[3]
                    acl_type = parts[4]

                else:
                    access_permissions = parts[1]
                    acl_inheritance_flags = parts[2]
                    acl_type = parts[3]

                for a in access_permissions:
                    if a != '-':
                        entry.set_access_permission(a)

                for f in acl_inheritance_flags:
                    if f != '-':
                        entry.set_inheritance_flag(f)

                entry.type = acl_type
                self.__entries.append(entry)

    def __refresh(self):
        self.__entries = []
        self.__get()
        self.__dirty = False

    def set(self, tag, qualifier, permissions, inheritance_flags = None, type = None):
        for entry in self.__entries:
            if entry.tag == tag and entry.qualifier == qualifier:
                if type == None or entry.type == type:
                    if permissions and permissions.startswith('+'):
                        for p in permissions[1:]:
                            entry.set_access_permission(p)
                        self.__dirty = True
                    elif permissions and permissions.startswith('-'):
                        for p in permissions[1:]:
                            entry.clear_access_permission(p)
                        self.__dirty = True
                    elif permissions:
                        entry.set_access_permissions(permissions)
                        self.__dirty = True

                    if inheritance_flags and inheritance_flags.startswith('+'):
                        for f in inheritance_flags[1:]:
                            entry.set_inheritance_flag(f)
                        self.__dirty = True
                    elif inheritance_flags and inheritance_flags.startswith('-'):
                        for f in inheritance_flags[1:]:
                            entry.clear_inheritance_flag(f)
                        self.__dirty = True
                    elif inheritance_flags:
                        entry.set_inheritance_flags(inheritance_flags)
                        self.__dirty = True

    def add(self, tag, qualifier = None, permissions = None, inheritance_flags = None, type = None):
        entry = NFSv4_ACL_Entry()
        entry.tag = tag

        if qualifier:
            entry.qualifier = qualifier
        if permissions:
            entry.set_access_permissions(permissions)
        if inheritance_flags:
            entry.set_inheritance_flags(inheritance_flags)

        entry.type = (type if type else 'allow')
        self.__entries.append(entry)
        self.__dirty = True

    def get(self, tag = None, qualifier = None, type = None):
        entries = []
        for entry in self.__entries:
            if tag and entry.tag == tag and entry.qualifier == qualifier:
                if not type or entry.type == type:
                    entries.append(entry)

            elif not tag:
                entries.append(entry)

        return entries

    def remove(self, tag, qualifier = None, type = None):
        entries = []
        for entry in self.__entries:
            if entry.tag == tag and entry.qualifier == qualifier:
                if type and entry.type == type:
                    self.__entries.remove(entry)
                    self.__dirty = True
                elif not type:
                    self.__entries.remove(entry)
                    self.__dirty = True

    def chown(self, who):
        if not who:
            return False 

        user = group = None
        uid = gid = -1

        parts = who.split(':')

        if parts[0]:
            user = parts[0]
        if len(parts) > 1 and parts[1]:
            group = parts[1]

        if user and re.match('^\d+', user):
            uid = int(user)
        elif user: 
            entry = pwd.getpwnam(user)
            uid = entry.pw_uid

        if group and re.match('^\d+', group):
            gid = int(group)
        elif group:
            entry = grp.getgrnam(group)
            gid = entry.gr_gid

        os.chown(self.__path, uid, gid)
        self.__refresh()

        return True
            
    def chmod(self, mode):
        length = len(mode) 
        if length == 4:
            mode = mode[1:]

        pos = 0 
        acl = ['owner@', 'group@', 'everyone@']
        for c in mode:
            n = int(c)
            tag = acl[pos]

            if n & 4:
                self.set(tag, None, '+r', None, 'allow')
            else:
                self.set(tag, None, '-r', None, 'allow')

            if n & 2:
                self.set(tag, None, '+w', None, 'allow')
            else:
                self.set(tag, None, '-w', None, 'allow')

            if n & 1:
                self.set(tag, None, '+x', None, 'allow')
            else:
                self.set(tag, None, '-x', None, 'allow')

            pos += 1

    def save(self):
        if not self.__dirty:
            return False

        n = 0
        for entry in self.__entries:
            NFSv4_setfacl(self.__path, entry, SETFACL_FLAGS_MODIFY)
            n += 1

        self.__refresh()
        return True
