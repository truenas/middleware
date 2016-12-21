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
import middlewared.logger

from freenasUI.common.acl import (
    Base_ACL_Exception, Base_ACL_pipe, Base_ACL_getfacl, Base_ACL_setfacl,
    Base_ACL_Hierarchy, Base_ACL_Entry, Base_ACL
)

log = middlewared.logger.Logger('commnon.freenasufs')


#
# getfacl POSIX flags
#
GETFACL_POSIX_FLAGS_DEFALT = 0x0001
GETFACL_POSIX_FLAGS_SYMLINK_ACL = 0x0002
SETFACL_POSIX_FLAGS_NO_COMMENTS = 0x0004


#
# setfacl POSIX flags
#
SETFACL_POSIX_FLAGS_SET_DEFAULTS = 0x0001
SETFACL_POSIX_FLAGS_APPLY_DEFAULT = 0x0002
SETFACL_POSIX_FLAGS_SYMLINK_OP = 0x0004
SETFACL_POSIX_FLAGS_DELETE_DEFAULTS = 0x0008
SETFACL_POSIX_FLAGS_MODIFY = 0x0010
SETFACL_POSIX_FLAGS_NO_RECALCULATE = 0x0020
SETFACL_POSIX_FLAGS_REMOVE_ENTRY = 0x0040


class POSIX_ACL_Exception(Base_ACL_Exception):
    pass


class POSIX_pipe(Base_ACL_pipe):
    pass


class POSIX_getfacl(Base_ACL_getfacl):
    def _build_args(self, path, flags):
        log.debug("POSIX_getfacl._build_args: enter")
        log.debug(
            "POSIX_getfacl._build_args: path = %s, flags = 0x%08x",
            path,
            flags
        )

        args = ""
        if flags & GETFACL_POSIX_FLAGS_DEFALT:
            args += "-d "
        if flags & GETFACL_POSIX_FLAGS_SYMLINK_ACL:
            args += "-h "
        if flags & SETFACL_POSIX_FLAGS_NO_COMMENTS:
            args += "-q "

        log.debug("POSIX_getfacl._build_args: enter")
        return args


class POSIX_setfacl(Base_ACL_setfacl):
    def _build_args(self, path, entry, flags, pos):
        log.debug("POSIX_setfacl._build_args: enter")
        log.debug(
            "POSIX_setfacl._build_args: path = %s, entry = %s, "
            "flags = 0x%08x, pos = %d",
            path,
            entry,
            flags,
            pos
        )

        args = ""
        if flags & SETFACL_POSIX_FLAGS_SET_DEFAULTS:
            args += "-b "
        if flags & SETFACL_POSIX_FLAGS_APPLY_DEFAULT:
            args += "-d "
        if flags & SETFACL_POSIX_FLAGS_SYMLINK_OP:
            args += "-h "
        if flags & SETFACL_POSIX_FLAGS_DELETE_DEFAULTS:
            args += "-k "
        if flags & SETFACL_POSIX_FLAGS_MODIFY:
            args += "-m "
        if flags & SETFACL_POSIX_FLAGS_NO_RECALCULATE:
            args += "-n "
        if flags & SETFACL_POSIX_FLAGS_REMOVE_ENTRY:
            args += "-x %d" % pos

        log.debug("POSIX_setfacl._build_args: enter")
        return args


class POSIX_ACL_Entry(Base_ACL_Entry):
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
        self.read = False
        self.write = False
        self.execute = False

    def __set_access_permission(self, permission, value):
        if permission == 'r':
            self.read = value
        elif permission == 'w':
            self.write = value
        elif permission == 'x':
            self.execute = value

    def set_access_permissions(self, permissions):
        log.debug("POSIX_ACL_Entry.set_access_permissions: enter")
        log.debug(
            "POSIX_ACL_Entry.set_access_permissions: permissions = %s",
            permissions
        )

        flag = True
        for p in permissions:
            if p == '+':
                flag = True
                continue
            elif p == '-':
                flag = False
                continue

            self.__set_access_permission(p, flag)

        log.debug("POSIX_ACL_Entry.set_access_permissions: leave")

    def set_access_permission(self, permission):
        self.__set_access_permission(permission, True)

    def clear_access_permissions(self):
        self.read = False
        self.write = False
        self.execute = False

    def clear_access_permission(self, permission):
        self.__set_access_permission(permission, False)

    def get_access_permissions(self):
        str = ""
        str = str + ('r' if self.read else '-')
        str = str + ('w' if self.write else '-')
        str = str + ('x' if self.execute else '-')
        return str

    def __str__(self):
        str = self.tag

        str += ":"
        if self.qualifier:
            str += self.qualifier

        str += ":"
        str += self.get_access_permissions()

        return str


class POSIX_ACL(Base_ACL):
    def _load(self):
        for line in POSIX_getfacl(self.path):
            log.debug("POSIX_ACL._load: line = %s", line)

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

                entry = POSIX_ACL_Entry()
                entry.tag = parts[0]

                if parts[1]:
                    entry.qualifier = parts[1]
                for a in parts[2]:
                    if a != '-':
                        entry.set_access_permission(a)

                self.entries.append(entry)

    def update(self, tag, qualifier, permissions):
        log.debug("POSIX_ACL.update: enter")
        log.debug(
            "POSIX_ACL.update: tag=%s, qualifier=%s, permissions=%s",
            tag,
            qualifier if qualifier else "",
            permissions if permissions else ""
        )

        for entry in self.entries:
            if entry.tag == tag and entry.qualifier == qualifier:
                if permissions:
                    entry.set_access_permissions(permissions)
                    self.dirty = True
                    break

        if self.dirty:
            POSIX_setfacl(self.path, entry, SETFACL_POSIX_FLAGS_MODIFY)

        self._refresh()
        log.debug("POSIX_ACL.update: leave")

    def add(self, tag, qualifier=None, permissions=None):
        log.debug("POSIX_ACL.add: enter")
        log.debug(
            "POSIX_ACL.add: tag = %s, qualifier = %s, permissions = %s",
            tag,
            qualifier if qualifier else "",
            permissions if permissions else ""
        )

        entry = POSIX_ACL_Entry()
        entry.tag = tag

        if qualifier:
            entry.qualifier = qualifier
        if permissions:
            entry.set_access_permissions(permissions)

        self.entries.append(entry)
        self.dirty = True

        POSIX_setfacl(self.path, entry, SETFACL_POSIX_FLAGS_MODIFY)
        self._refresh()

        log.debug("POSIX_ACL.add: leave")

    def get(self, tag=None, qualifier=None):
        log.debug("POSIX_ACL.get: enter")
        log.debug(
            "POSIX_ACL.get: tag = %s, qualifier = %s",
            tag if tag else "",
            qualifier if qualifier else ""
        )

        entries = []
        for entry in self.entries:
            if tag and entry.tag == tag:
                if qualifier is None or qualifier == entry.qualifier:
                    entries.append(entry)
            elif not tag:
                entries.append(entry)

        log.debug("POSIX_ACL.get: leave")
        return entries

    def remove(self, tag, qualifier=None, pos=None):
        log.debug("POSIX_ACL.remove: enter")
        log.debug(
            "POSIX_ACL.remove: tag = %s, qualifier = %s, pos = %s",
            tag if tag else "",
            qualifier if qualifier else "",
            str(pos) if pos else "None"
        )

        n = 0
        entry = None
        for entry in self.entries:
            if entry.tag == tag and entry.qualifier == qualifier and pos == pos:
                POSIX_setfacl(self.path, entry, SETFACL_POSIX_FLAGS_REMOVE_ENTRY, n)
                self.dirty = True
            n += 1

        if pos == -1 and entry:
            POSIX_setfacl(self.path, entry, SETFACL_POSIX_FLAGS_REMOVE_ENTRY, (n - 1) if n > 0 else n)
            self.dirty = True

        self._refresh()
        log.debug("POSIX_ACL.remove: leave")

    def reset(self):
        POSIX_setfacl(self.path, None, SETFACL_POSIX_FLAGS_SET_DEFAULTS)
        self._refresh()

    def chmod(self, mode):
        log.debug("POSIX_ACL.chmod: enter")
        log.debug("POSIX_ACL.chmod: mode = %s", mode)

        length = len(mode)
        if length == 4:
            mode = mode[1:]

        pos = 0
        acl = ['user', 'group', 'other']
        mask = None
        for c in mode:
            n = int(c)
            tag = acl[pos]

            permissions = ""
            permissions = ((permissions + "+r") if (n & 4) else (permissions + "-r"))
            permissions = ((permissions + "+w") if (n & 2) else (permissions + "-w"))
            permissions = ((permissions + "+x") if (n & 1) else (permissions + "-x"))
            if permissions:
                self.update(tag, None, permissions)
            if tag == 'group':
                mask = permissions

            pos += 1

        if mask:
            self.update('mask', None, mask)

        log.debug("POSIX_ACL.chmod: leave")


class POSIX_ACL_Hierarchy(Base_ACL_Hierarchy):

    def _set_windows_file_defaults(self, acl):
        pass

    def _set_windows_directory_defaults(self, acl):
        pass

    def _set_unix_file_defaults(self, acl):
        log.debug("POSIX_ACL_Hierarchy._set_unix_file_defaults: enter")
        log.debug("POSIX_ACL_Hierarchy._set_unix_file_defaults: acl = %s", acl)

        acl.reset()
        acl.chmod('644')

        log.debug("POSIX_ACL_Hierarchy._set_unix_file_defaults: leave")

    def _set_unix_directory_defaults(self, acl):
        log.debug("POSIX_ACL_Hierarchy._set_unix_directory_defaults: enter")
        log.debug(
            "POSIX_ACL_Hierarchy._set_unix_directory_defaults: acl = %s",
            acl
        )

        acl.reset()
        acl.chmod('755')

        log.debug("POSIX_ACL_Hierarchy._set_unix_directory_defaults: leave")

    def new_ACL(self, path):
        return POSIX_ACL(path)
