#+
# Copyright 2011 iXsystems
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
import stat
import syslog

from subprocess import Popen, PIPE
from syslog import syslog, LOG_DEBUG

GETFACL_PATH = "/bin/getfacl"
SETFACL_PATH = "/bin/setfacl"

#
# getfacl NFSv4 flags
#
GETFACL_FLAGS_SYMLINK_ACL  = 0x0001
GETFACL_FLAGS_APPEND_IDS   = 0x0002
GETFACL_FLAGS_NUMERIC_IDS  = 0x0004
GETFACL_FLAGS_NO_COMMENTS  = 0x0008
GETFACL_FLAGS_VERBOSE      = 0x0010

#
# setfacl NFSv4 flags
#
SETFACL_FLAGS_MODIFY_ENTRY = 0x0001
SETFACL_FLAGS_SET_DEFAULTS = 0x0002
SETFACL_FLAGS_SYMLINK_OP   = 0x0004
SETFACL_FLAGS_MODIFY       = 0x0008
SETFACL_FLAGS_REMOVE_ENTRY = 0x0010

#
# NFSv4_ACL entry flags
#
ACL_ENTRY_FLAGS_NONE       = 0x0000
ACL_ENTRY_FLAGS_ADD        = 0x0001
ACL_ENTRY_FLAGS_UPDATE     = 0x0002
ACL_ENTRY_FLAGS_REMOVE     = 0x0004

#
# NFSv4_ACL type
#
# This should probably be filesystem types ;-)
#
ACL_TYPE_UNIX              = 0x0001
ACL_TYPE_WINDOWS           = 0x0002



ACL_HIER_COURSE_GRAINED    = 0x0001
ACL_HIER_FINE_GRAINED      = 0x0002


class NFSv4_ACL_Exception(Exception):
    def __init__(self, msg = None):
        syslog(LOG_DEBUG, "NFSv4_ACL_Exception.__init__: enter")
        if msg:
            syslog(LOG_DEBUG, "NFSv4_ACL_Exception.__init__: error = %s" % msg)
        syslog(LOG_DEBUG, "NFSv4_ACL_Exception.__init__: leave")


class NFSv4_pipe:
    def __init__(self, cmd):
        syslog(LOG_DEBUG, "NFSv4_pipe.__init__: enter")
        syslog(LOG_DEBUG, "NFSv4_pipe.__init__: cmd = %s" % cmd)

        self.__pipe = Popen(cmd, stdin = PIPE, stdout = PIPE,
            stderr = PIPE, shell = True, close_fds = True)

        self.__stdin = self.__pipe.stdin
        self.__stdout = self.__pipe.stdout
        self.__stderr = self.__pipe.stderr

        self.__out = self.__stdout.read().strip()
        self.__pipe.wait()

        syslog(LOG_DEBUG, "NFSv4_pipe.__init__: out = %s" % self.__out)

        if self.__pipe.returncode != 0:
            raise NFSv4_ACL_Exception(self.__stderr.read().strip())

        syslog(LOG_DEBUG, "NFSv4_pipe.__init__: leave")

    def __str__(self):
        return self.__out

    def __iter__(self):
        lines = self.__out.splitlines()
        for line in lines:
            yield line


class NFSv4_getfacl:
    def __init__(self, path, flags = 0):
        syslog(LOG_DEBUG, "NFSv4_getfacl.__init__: enter")
        syslog(LOG_DEBUG, "NFSv4_getfacl.__init__: path = %s, flags = 0x%08x" % (path, flags))

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

        cmd = "%s " % self.__getfacl
        if args:
            cmd += "%s " % args
        cmd += "'%s'" % self.__path

        self.__out = str(NFSv4_pipe(cmd))

        syslog(LOG_DEBUG, "NFSv4_getfacl.__init__: out = %s" % self.__out)
        syslog(LOG_DEBUG, "NFSv4_getfacl.__init__: leave")

    def __str__(self):
        return self.__out

    def __iter__(self):
        lines = self.__out.splitlines()
        for line in lines:
            yield line


class NFSv4_setfacl:
    def __init__(self, path, entry = None, flags = 0, pos = 0):
        syslog(LOG_DEBUG, "NFSv4_setfacl.__init__: enter")
        syslog(LOG_DEBUG, "NFSv4_setfacl.__init__: path = %s, entry = %s, flags = 0x%08x" %
            (path, (entry if entry else ""), flags))

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
            args += "-x %d" % pos
            self.__entry = None

        cmd = "%s " % self.__setfacl
        if args:
            cmd += "%s " % args
        if self.__entry:
            cmd += "%s " % self.__entry
        cmd += "'%s'" % self.__path
        
        self.__out = str(NFSv4_pipe(cmd))

        syslog(LOG_DEBUG, "NFSv4_setfacl.__init__: out = %s" % self.__out)
        syslog(LOG_DEBUG, "NFSv4_setfacl.__init__: leave")



class NFSv4_ACL_Entry:
    def __init__(self):
        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.__init__: enter")

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

        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.__init__: leave")

    def __set_access_permission(self, permission, value):
        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.__set_access_permission: enter")
        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.__set_access_permission: permission = %s, value = %s" %
            (permission, value))

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
        elif permission == 's':
            self.synchronize = value

        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.__set_access_permission: enter")

    def set_access_permissions(self, permissions):
        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.set_access_permissions: enter")
        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.set_access_permissions: permissions = %s" % permissions)

        flag = True
        for p in permissions:
            if p == '+':
                flag = True
                continue
            elif p == '-':
                flag = False
                continue

            self.__set_access_permission(p, flag)

        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.set_access_permissions: leave")

    def set_access_permission(self, permission):
        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.set_access_permission: enter")
        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.set_access_permission: permission = %s" % permission)

        self.__set_access_permission(permission, True)

        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.set_access_permission: leave")

    def clear_access_permissions(self):
        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.clear_access_permissions: enter")

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

        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.clear_access_permissions: leave")

    def clear_access_permission(self, permission):
        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.clear_access_permission: enter")
        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.clear_access_permission: permission = %s" % permission)

        self.__set_access_permission(permission, False)

        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.clear_access_permission: leave")

    def __set_inheritance_flag(self, flag, value):
        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.__set_inheritance_flag: enter")
        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.__set_inheritance_flag: flag = %s, value = %s" % (flag, value))

        if flag == 'f':
            self.file_inherit = value
        elif flag == 'd':
            self.dir_inherit = value
        elif flag == 'i':
            self.inherit_only = value
        elif flag == 'n':
            self.no_propagate = value

        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.__set_inheritance_flag: enter")

    def set_inheritance_flags(self, flags):
        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.set_inheritance_flags: enter")
        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.set_inheritance_flags: flags = %s" % flags)

        flag = True
        for f in flags:
            if f == '+':
                flag = True
                continue
            elif f == '-':
                flag = False
                continue

            self.__set_inheritance_flag(f, flag)

        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.set_inheritance_flags: leave")

    def set_inheritance_flag(self, flag):
        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.set_inheritance_flag: enter")
        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.set_inheritance_flag: flag = %s" % flag)

        self.__set_inheritance_flag(flag, True)

        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.set_inheritance_flag: leave")

    def clear_inheritance_flags(self):
        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.clear_inheritance_flags: enter")

        self.file_inherit = False
        self.dir_inherit = False
        self.inherit_only = False
        self.no_propagate = False

        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.clear_inheritance_flags: leave")

    def clear_inheritance_flag(self, flag):
        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.set_inheritance_flag: enter")
        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.set_inheritance_flag: flag = %s" % flag)

        self.__set_inheritance_flag(flag, False)

        syslog(LOG_DEBUG, "NFSv4_ACL_Entry.set_inheritance_flag: leave")

    def get_access_permissions(self):
        str = ""
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
        str = str + ('s' if self.synchronize else '-')
        return str

    def get_inheritance_flags(self):
        str = ""
        str = str + ('f' if self.file_inherit else '-')
        str = str + ('d' if self.dir_inherit else '-')
        str = str + ('i' if self.inherit_only else '-')
        str = str + ('n' if self.no_propagate else '-')
        return str

    def __str__(self):
        str = self.tag

        if self.qualifier:
            str = str + ":" + self.qualifier

        str = str + ":"
        str += self.get_access_permissions()

        str = str + ":"
        str += self.get_inheritance_flags()

        str = str + ":" + self.type
        return str


class NFSv4_ACL:
    def __init__(self, path, acl = None):
        syslog(LOG_DEBUG, "NFSv4_ACL.__init__: enter")
        syslog(LOG_DEBUG, "NFSv4_ACL.__init__: path = %s, acl = %s" % (path, (acl if acl else "")))

        #
        # Array NFSv4_ACL_Entry's
        #
        self.__entries = []
        self.file = None
        self.owner = None
        self.group = None

        self.__dirty = False
        self.__path = path

        st = os.stat(path) 
        self.mode = st.st_mode

        self.__type = ACL_TYPE_UNIX
        if os.access(os.path.join(self.__path, ".windows"), 0):
            self.__type = ACL_TYPE_WINDOWS

        self.__get() 

        syslog(LOG_DEBUG, "NFSv4_ACL.__init__: leave")

    def is_unix(self):
        return self.__type == ACL_TYPE_UNIX

    def is_windows(self):
        return self.__type == ACL_TYPE_WINDOWS 

    def path(self):
        return self.__path

    def dirty(self):
        return self.__dirty

    def __get(self):
        syslog(LOG_DEBUG, "NFSv4_ACL.__get: enter")

        for line in NFSv4_getfacl(self.__path):
            syslog(LOG_DEBUG, "NFSv4_ACL.__get: line = %s" % line)

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

        syslog(LOG_DEBUG, "NFSv4_ACL.__get: enter")

    def __refresh(self):
        syslog(LOG_DEBUG, "NFSv4_ACL.__refresh: enter")

        self.__entries = []
        self.__get()
        self.__dirty = False

        syslog(LOG_DEBUG, "NFSv4_ACL.__refresh: leave")

    def update(self, tag, qualifier, permissions, inheritance_flags = None, type = None):
        syslog(LOG_DEBUG, "NFSv4_ACL.update: enter")
        syslog(LOG_DEBUG, "NFSv4_ACL.update: tag = %s, qualifier = %s, permissions = %s,"
            "inheritance_flags = %s, type = %s" % (tag,
            (qualifier if qualifier else ""), (permissions if permissions else ""),
            (inheritance_flags if inheritance_flags else ""), (type if type else "")))

        for entry in self.__entries:
            if entry.tag == tag and entry.qualifier == qualifier:
                if type == None or entry.type == type:
                    if permissions:
                        entry.set_access_permissions(permissions)
                        self.__dirty = True

                    if inheritance_flags and not stat.S_ISREG(self.mode):
                        entry.set_inheritance_flags(inheritance_flags)
                        self.__dirty = True

            if self.__dirty:
                NFSv4_setfacl(self.__path, entry, SETFACL_FLAGS_MODIFY)

        self.__refresh()
        syslog(LOG_DEBUG, "NFSv4_ACL.update: leave")

    def add(self, tag, qualifier = None, permissions = None, inheritance_flags = None, type = None, pos = 0):
        syslog(LOG_DEBUG, "NFSv4_ACL.add: enter")
        syslog(LOG_DEBUG, "NFSv4_ACL.add: tag = %s, qualifier = %s, permissions = %s, "
            "inheritance_flags = %s, type = %s, pos = %s" %
            (tag, qualifier if qualifier else "", permissions if permissions else "",
            inheritance_flags if inheritance_flags else "", type if type else "", pos))

        entry = NFSv4_ACL_Entry()
        entry.tag = tag

        if qualifier:
            entry.qualifier = qualifier
        if permissions:
            entry.set_access_permissions(permissions)
        if inheritance_flags and not stat.S_ISREG(self.mode):
            entry.set_inheritance_flags(inheritance_flags)

        entry.type = (type if type else 'allow')
        self.__entries.append(entry)
        self.__dirty = True

        NFSv4_setfacl(self.__path, entry, SETFACL_FLAGS_MODIFY_ENTRY, pos)
        self.__refresh()

        syslog(LOG_DEBUG, "NFSv4_ACL.add: leave")

    def get(self, tag = None, qualifier = None, type = None):
        syslog(LOG_DEBUG, "NFSv4_ACL.get: enter")
        syslog(LOG_DEBUG, "NFSv4_ACL.get: tag = %s, qualifier = %s, type = %s" % (
            (tag if tag else ""), (qualifier if qualifier else ""), (type if type else "")))

        entries = []
        for entry in self.__entries:
            if tag and entry.tag == tag and entry.qualifier == qualifier:
                if not type or entry.type == type:
                    entries.append(entry)

            elif not tag:
                entries.append(entry)

        syslog(LOG_DEBUG, "NFSv4_ACL.get: leave")
        return entries

    def remove(self, tag, qualifier = None, type = None, pos = None):
        syslog(LOG_DEBUG, "NFSv4_ACL.remove: enter")
        syslog(LOG_DEBUG, "NFSv4_ACL.remove: tag = %s, qualifier = %s, type = %s" % (
            (tag if tag else ""), (qualifier if qualifier else ""), (type if type else "")))

        entries = []
        entry = None

        n = 0
        for entry in self.__entries:
            if entry.tag == tag and entry.qualifier == qualifier and pos == None:
                if type and entry.type == type:
                    NFSv4_setfacl(self.__path, entry, SETFACL_FLAGS_REMOVE_ENTRY, 0)
                    self.__dirty = True

                elif not type:
                    NFSv4_setfacl(self.__path, entry, SETFACL_FLAGS_REMOVE_ENTRY, 0)
                    self.__dirty = True

            elif n == pos:
                NFSv4_setfacl(self.__path, entry, SETFACL_FLAGS_REMOVE_ENTRY, 0)
                self.__dirty = True

            n += 1

        if pos == -1 and entry:
            NFSv4_setfacl(self.__path, entry, SETFACL_FLAGS_REMOVE_ENTRY, (n - 1) if n > 0 else n)
            self.__dirty = True

        self.__refresh()
        syslog(LOG_DEBUG, "NFSv4_ACL.remove: leave")

    def reset(self):
        syslog(LOG_DEBUG, "NFSv4_ACL.reset: enter")

        NFSv4_setfacl(self.__path, None, SETFACL_FLAGS_SET_DEFAULTS)
        self.__refresh()

        syslog(LOG_DEBUG, "NFSv4_ACL.reset: leave")

    def clear(self):
        syslog(LOG_DEBUG, "NFSv4_ACL.clear: enter")

        self.reset()
        self.__refresh()

        for entry in self.__entries:
            if not (entry.tag == 'everyone@' and entry.type == 'allow'):
                self.remove(entry.tag, entry.qualifier, entry.type)

        syslog(LOG_DEBUG, "NFSv4_ACL.clear: leave")

    def chown(self, who):
        syslog(LOG_DEBUG, "NFSv4_ACL.chown: enter")
        syslog(LOG_DEBUG, "NFSv4_ACL.chown: who = %s" % who)

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

        syslog(LOG_DEBUG, "NFSv4_ACL.chown: leave")
        return True
            
    def chmod(self, mode):
        syslog(LOG_DEBUG, "NFSv4_ACL.chmod: enter")
        syslog(LOG_DEBUG, "NFSv4_ACL.chmod: mode = %s" % mode)

        length = len(mode) 
        if length == 4:
            mode = mode[1:]

        pos = 0 
        acl = ['owner@', 'group@', 'everyone@']
        for c in mode:
            n = int(c)
            tag = acl[pos]
            permissions_allow = permissions_deny = ""
           
            if n & 4:
                permissions_allow += "+r"
                permissions_deny += "-r"
            else:
                permissions_allow += "-r"
                permissions_deny += "+r"

            if n & 2:
                permissions_allow += "+w"
                permissions_deny += "-w"
            else:
                permissions_allow += "-w"
                permissions_deny += "+w"

            if n & 1:
                permissions_allow += "+x"
                permissions_deny += "-x"
            else:
                permissions_allow += "-x"
                permissions_deny += "+x"

            if permissions_allow:
                self.update(tag, None, permissions_allow, None, 'allow')

            if permissions_deny:
                self.update(tag, None, permissions_deny, None, 'deny')

            pos += 1

        syslog(LOG_DEBUG, "NFSv4_ACL.chmod: enter")

    def save(self):
        syslog(LOG_DEBUG, "NFSv4_ACL.save: enter")

        if not self.__dirty:
            return False

        self.__refresh()

        syslog(LOG_DEBUG, "NFSv4_ACL.save: leave")
        return True


class NFSv4_ACL_Hierarchy:
    def __init__(self, path):
        self.__path = path
        self.__type = ACL_TYPE_UNIX
      
        if os.access(os.path.join(self.__path, ".windows"), 0):
            self.__type = ACL_TYPE_WINDOWS

    def is_unix(self):
        return self.__type == ACL_TYPE_UNIX

    def is_windows(self):
        return self.__type == ACL_TYPE_WINDOWS

    def __recurse(self, path, callback, *args):
        callback(path, *args)

        files = os.listdir(path)
        for f in files:
            file = os.path.join(path, f)
            st = os.stat(file)

            if stat.S_ISDIR(st.st_mode):
                if os.access(os.path.join(path, ".windows"), 0):
                    self.__type = ACL_TYPE_WINDOWS
                self.__recurse(file, callback, *args)

            else:
                if f != '.windows':
                    callback(file, *args)

    def __set_windows_file_defaults(self, acl):
        acl.clear()

        pos = 0
        acl.add('group@', None, 'rxaRcs', None, 'allow', pos); pos += 1
        acl.add('everyone@', None, 'rxaRcs', None, 'allow', pos); pos += 1
        acl.add('owner@', None, 'rwxpDdaARWcCos', None, 'allow', pos); pos += 1
        acl.remove('everyone@', None, None, -1)
        acl.chmod('755')

    def __set_unix_file_defaults(self, acl):
        acl.reset()
        acl.chmod('644')

    def __set_file_defaults(self, acl):
        if self.is_windows(): 
            self.__set_windows_file_defaults(acl)
        else:
            self.__set_unix_file_defaults(acl)


    def __set_windows_directory_defaults(self, acl):
        acl.clear()

        pos = 0
        acl.add('group@', None, 'rxaRcs', 'fd', 'allow', pos); pos += 1
        acl.add('everyone@', None, 'rxaRcs', 'fd', 'allow', pos); pos += 1
        acl.add('owner@', None, 'rwxpDdaARWcCos', 'fd', 'allow', pos); pos += 1
        acl.remove('everyone@', None, None, -1)
        acl.chmod('755') 

    def __set_unix_directory_defaults(self, acl):
        acl.reset()
        acl.chmod('755')

    def __set_directory_defaults(self, acl):
        if self.is_windows():
            self.__set_windows_directory_defaults(acl)
        else:
            self.__set_unix_directory_defaults(acl)

    def __set_defaults(self, path, args = None):
        acl = NFSv4_ACL(path)

        if stat.S_ISREG(acl.mode):
            self.__set_file_defaults(acl)
        elif stat.S_ISDIR(acl.mode):
            self.__set_directory_defaults(acl)
        else:
            self.__set_file_defaults(acl)

        acl.save()

    def set_defaults(self, recursive = False):
        if recursive:
            self.__recurse(self.__path, self.__set_defaults, None)

        else:
            self.__set_defaults(path)

    def __reset(self, path, args = None):
        acl = NFSv4_ACL(path)
        acl.reset()
        acl.save()

    def reset(self, recursive = False):
        if recursive:
            self.__recurse(self.__path, self.__reset, None)
        else:
            self.__reset(self.__path)

    def __clear(self, path, args = None):
        acl = NFSv4_ACL(path)
        acl.clear()
        acl.save()

    def clear(self, recursive = False):
        if recursive:
            self.__recurse(self.__path, self.__clear, None)
        else:
            self.__clear(self.__path)
    
    def __add(self, path, tag, qualifier = None, inheritance_flags = None, type = None, pos = 0):
        acl = NFSv4_ACL(path)
        acl.add(tag, qualifier, inheritance_flags, type, pos)
        acl.save()

    def add(self, tag, qualifier = None, inheritance_flags = None, type = None, pos = 0, recursive = False):
        if recursive:
            self.__recurse(self.__path, self.__add, tag, qualifier, inheritance_flags, type, pos)
        else:
            self.__add(self.__path, tag, qualifier, inheritance_flags, type, pos)

    def __update(self, path, tag, qualifier, permissions, inheritance_flags = None, type = None):
        acl = NFSv4_ACL(path)
        acl.update(tag, qualifier, permissions, inheritance_flags, type)
        acl.save()

    def update(self, tag, qualifier, permissions, inheritance_flags = None, type = None,  recursive = False):
        if recursive:
            self.__recurse(self.__path, self.__update, tag, qualifier, permissions, inheritance_flags, type)
        else:
            self.__update(self.__path, tag, qualifier, permissions, inheritance_flags, type)

    def __remove(self, path, tag, qualifier = None, type = None, pos = None):
        acl = NFSv4_ACL(path)
        acl.remove(tag, qualifier, type, pos)
        acl.save()

    def remove(self, tag, qualifier = None, type = None, pos = None, recursive = False):
        if recursive:
            self.__recurse(self.__path, self.__remove, tag, qualifier, type, pos)
        else:
            self.__remove(self.__path, tag, qualifier, type, pos)

    def __chmod(self, path, mode):
        acl = NFSv4_ACL(path)
        acl.chmod(mode)
        acl.save()

    def chmod(self, mode, recursive = False):
        if recursive:
            self.__recurse(self.__path, self.__chmod, mode)
        else:
            self.__chmod(self.__path, mode)

    def __chown(self, path, who):
        acl = NFSv4_ACL(path)
        acl.chown(who)
        acl.save()

    def chown(self, who, recursive = False):
        if recursive:
            self.__recurse(self.__path, self.__chown, who)
        else:
            self.__chown(self.__path, who)

    def close(self):
        self.__path = None
        self.__type = None
