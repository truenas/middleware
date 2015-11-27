# Copyright 2011 iXsystems, Inc.
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
import logging

from freenasUI.common.acl import *

log = logging.getLogger('common.freenasnfsv4')


#
# getfacl NFSv4 flags
#
GETFACL_FLAGS_SYMLINK_ACL = 0x0001
GETFACL_FLAGS_APPEND_IDS = 0x0002
GETFACL_FLAGS_NUMERIC_IDS = 0x0004
GETFACL_FLAGS_NO_COMMENTS = 0x0008
GETFACL_FLAGS_VERBOSE = 0x0010

#
# setfacl NFSv4 flags
#
SETFACL_FLAGS_MODIFY_ENTRY = 0x0001
SETFACL_FLAGS_SET_DEFAULTS = 0x0002
SETFACL_FLAGS_SYMLINK_OP = 0x0004
SETFACL_FLAGS_MODIFY = 0x0008
SETFACL_FLAGS_REMOVE_ENTRY = 0x0010

#
# NFSv4_ACL entry flags
#
ACL_ENTRY_FLAGS_NONE = 0x0000
ACL_ENTRY_FLAGS_ADD = 0x0001
ACL_ENTRY_FLAGS_UPDATE = 0x0002
ACL_ENTRY_FLAGS_REMOVE = 0x0004


class NFSv4_ACL_Exception(Base_ACL_Exception):
    pass


class NFSv4_pipe(Base_ACL_pipe):
    pass


class NFSv4_getfacl(Base_ACL_getfacl):
    def _build_args(self, path, flags):
        log.debug("NFSv4_getfacl._build_args: enter")
        log.debug(
            "NFSv4_getfacl._build_args: path = %s, flags = 0x%08x",
            path,
            flags
        )

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

        log.debug("NFSv4_getfacl._build_args: leave")
        return args


class NFSv4_setfacl(Base_ACL_setfacl):
    def _build_args(self, path, entry, flags, pos):
        log.debug("NFSv4_setfacl._build_args: enter")
        log.debug(
            "NFSv4_setfacl._build_args: path = %s, entry = %s, flags = 0x%08x, pos = %d",
            path,
            entry,
            flags,
            pos
        )

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
            self._entry = None

        log.debug("NFSv4_setfacl._build_args: leave")
        return args


class NFSv4_ACL_Entry(Base_ACL_Entry):
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
        elif permission == 's':
            self.synchronize = value

    def set_access_permissions(self, permissions):
        log.debug("NFSv4_ACL_Entry.set_access_permissions: enter")
        log.debug(
            "NFSv4_ACL_Entry.set_access_permissions: permissions = %s",
            permissions
        )

        self.clear_access_permissions()
        for p in permissions:
            self.__set_access_permission(p, True)

        log.debug("NFSv4_ACL_Entry.set_access_permissions: leave")

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

    def set_inheritance_flags(self, flags):
        log.debug("NFSv4_ACL_Entry.set_inheritance_flags: enter")
        log.debug(
            "NFSv4_ACL_Entry.set_inheritance_flags: flags = %s",
            flags
        )

        self.clear_inheritance_flags()
        for f in flags:
            self.__set_inheritance_flag(f, True)

        log.debug("NFSv4_ACL_Entry.set_inheritance_flags: leave")

    def set_inheritance_flag(self, flag):
        self.__set_inheritance_flag(flag, True)

    def clear_inheritance_flags(self):
        self.file_inherit = False
        self.dir_inherit = False
        self.inherit_only = False
        self.no_propagate = False

    def clear_inheritance_flag(self, flag):
        self.__set_inheritance_flag(flag, False)

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


class NFSv4_ACL(Base_ACL):

    def _load(self):
        for line in NFSv4_getfacl(self.path):
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
                self.entries.append(entry)

    def _refresh(self):
        self.entries = []
        self._load()
        self.dirty = False

    def update(self, tag, qualifier, permissions, inheritance_flags=None, type=None):
        log.debug("NFSv4_ACL.update: enter")
        log.debug(
            "NFSv4_ACL.update: tag = %s, qualifier = %s, permissions = %s,"
            "inheritance_flags = %s, type = %s",
            tag,
            qualifier if qualifier else "",
            permissions if permissions else "",
            inheritance_flags if inheritance_flags else "",
            type if type else ""
        )

        entry = NFSv4_ACL_Entry()
        entry.tag = tag

        if qualifier:
            entry.qualifier = qualifier
        if permissions:
            entry.set_access_permissions(permissions)
        if inheritance_flags and not stat.S_ISREG(self.mode):
            entry.set_inheritance_flags(inheritance_flags)

        entry.type = (type if type else 'allow')
        self.dirty = True

        NFSv4_setfacl(self.path, entry, SETFACL_FLAGS_MODIFY)
        self._refresh()

        log.debug("NFSv4_ACL.update: leave")

    def add(self, tag, qualifier=None, permissions=None, inheritance_flags=None, type=None, pos=0):
        log.debug("NFSv4_ACL.add: enter")
        log.debug(
            "NFSv4_ACL.add: tag = %s, qualifier = %s, permissions = %s, "
            "inheritance_flags = %s, type = %s, pos = %s",
            tag,
            qualifier if qualifier else "",
            permissions if permissions else "",
            inheritance_flags if inheritance_flags else "",
            type if type else "", pos
        )

        entry = NFSv4_ACL_Entry()
        entry.tag = tag

        if qualifier:
            entry.qualifier = qualifier
        if permissions:
            entry.set_access_permissions(permissions)
        if inheritance_flags and not stat.S_ISREG(self.mode):
            entry.set_inheritance_flags(inheritance_flags)

        entry.type = (type if type else 'allow')
        self.dirty = True

        NFSv4_setfacl(self.path, entry, SETFACL_FLAGS_MODIFY_ENTRY, pos)
        self._refresh()

        log.debug("NFSv4_ACL.add: leave")

    def get(self, tag=None, qualifier=None, type=None):
        log.debug("NFSv4_ACL.get: enter")
        log.debug(
            "NFSv4_ACL.get: tag = %s, qualifier = %s, type = %s",
            tag if tag else "",
            qualifier if qualifier else "",
            type if type else ""
        )

        entries = []
        for entry in self.entries:
            if tag and entry.tag == tag and entry.qualifier == qualifier:
                if not type or entry.type == type:
                    entries.append(entry)

            elif not tag:
                entries.append(entry)

        log.debug("NFSv4_ACL.get: leave")
        return entries

    def remove(self, tag, qualifier=None, permissions=None, inheritance_flags=None, type=None, pos=None):
        log.debug("NFSv4_ACL.remove: enter")
        log.debug(
            "NFSv4_ACL.remove: tag = %s, qualifier = %s, type = %s",
            tag if tag else "",
            qualifier if qualifier else "",
            type if type else ""
        )

        n = 0
        entry = None
        for entry in self.entries:
            if entry.tag == tag and entry.qualifier == qualifier and pos is None:
                if type and entry.type == type:
                    NFSv4_setfacl(self.path, entry, SETFACL_FLAGS_REMOVE_ENTRY, 0)
                    self.dirty = True

                elif not type:
                    NFSv4_setfacl(self.path, entry, SETFACL_FLAGS_REMOVE_ENTRY, 0)
                    self.dirty = True

            elif n == pos:
                NFSv4_setfacl(self.path, entry, SETFACL_FLAGS_REMOVE_ENTRY, n)
                self.dirty = True

            n += 1

        if pos == -1 and entry:
            NFSv4_setfacl(self.path, entry, SETFACL_FLAGS_REMOVE_ENTRY, (n - 1) if n > 0 else n)
            self.dirty = True

        self._refresh()
        log.debug("NFSv4_ACL.remove: leave")

    def reset(self):
        NFSv4_setfacl(self.path, None, SETFACL_FLAGS_SET_DEFAULTS)
        self._refresh()

    def clear(self):
        self.reset()
        self._refresh()

        for entry in self.entries:
            if not (entry.tag == 'everyone@' and entry.type == 'allow'):
                self.remove(entry.tag, qualifier=entry.qualifier, type=entry.type)

    def chmod(self, mode):
        log.debug("NFSv4_ACL.chmod: enter")
        log.debug("NFSv4_ACL.chmod: mode = %s", mode)

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
                permissions_allow += "+wp"
                permissions_deny += "-wp"
            else:
                permissions_allow += "-wp"
                permissions_deny += "+wp"

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

        log.debug("NFSv4_ACL.chmod: leave")

    def save(self):
        if not self.dirty:
            return False

        self._refresh()
        return True


class NFSv4_ACL_Hierarchy(Base_ACL_Hierarchy):

    def _set_windows_file_defaults(self, acl):
        log.debug("NFSv4_ACL_Hierarchy._set_windows_file_defaults: enter")
        log.debug(
            "NFSv4_ACL_Hierarchy._set_windows_file_defaults: acl = %s",
            acl
        )

        pos = 0
        acl.clear()
        acl.add('group@', None, 'rxaRcs', None, 'allow', pos)
        pos += 1
        acl.add('everyone@', None, 'rxaRcs', None, 'allow', pos)
        pos += 1
        acl.add('owner@', None, 'rwxpDdaARWcCos', None, 'allow', pos)
        pos += 1
        acl.remove('everyone@', None, None, -1)
        acl.chmod('755')

        log.debug("NFSv4_ACL_Hierarchy._set_windows_file_defaults: leave")

    def _set_windows_directory_defaults(self, acl):
        log.debug("NFSv4_ACL_Hierarchy._set_windows_directory_defaults: enter")
        log.debug(
            "NFSv4_ACL_Hierarchy._set_windows_directory_defaults: acl = %s",
            acl
        )

        pos = 0
        acl.clear()
        acl.add('group@', None, 'rxaRcs', 'fd', 'allow', pos)
        pos += 1
        acl.add('everyone@', None, 'rxaRcs', 'fd', 'allow', pos)
        pos += 1
        acl.add('owner@', None, 'rwxpDdaARWcCos', 'fd', 'allow', pos)
        pos += 1
        acl.remove('everyone@', None, None, -1)
        acl.chmod('755')

        log.debug("NFSv4_ACL_Hierarchy._set_windows_directory_defaults: leave")

    def _set_unix_file_defaults(self, acl):
        log.debug("NFSv4_ACL_Hierarchy._set_unix_file_defaults: enter")
        log.debug(
            "NFSv4_ACL_Hierarchy._set_unix_file_defaults: acl = %s",
            acl
        )

        acl.reset()
        acl.chmod('644')

        log.debug("NFSv4_ACL_Hierarchy._set_unix_file_defaults: leave")

    def _set_unix_directory_defaults(self, acl):
        log.debug("NFSv4_ACL_Hierarchy._set_unix_directory_defaults: enter")
        log.debug(
            "NFSv4_ACL_Hierarchy._set_unix_directory_defaults: acl = %s",
            acl
        )

        acl.reset()
        acl.chmod('755')

        log.debug("NFSv4_ACL_Hierarchy._set_unix_directory_defaults: leave")

    def new_ACL(self, path):
        return NFSv4_ACL(path)
