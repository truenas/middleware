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
import grp
import os
import pwd
import re
import stat
import middlewared.logger

from pipes import quote
from subprocess import Popen, PIPE

log = middlewared.logger.Logger('common.acl')

GETFACL_PATH = "/bin/getfacl"
SETFACL_PATH = "/bin/setfacl"

#
# ACL flags
#
ACL_FLAGS_NONE = 0x0000
ACL_FLAGS_OS_UNIX = 0x0001
ACL_FLAGS_OS_WINDOWS = 0x0002
ACL_FLAGS_TYPE_POSIX = 0x0100
ACL_FLAGS_TYPE_NFSV4 = 0x0200


#
# Odds and ends
#
ACL_WINDOWS_FILE = ".windows"
ACL_MAC_FILE = ".mac"


class Base_ACL_Exception(Exception):
    def __init__(self, msg=None):
        self.value = msg
        log.debug("Base_ACL_Exception.__init__: enter")
        if msg:
            log.debug("Base_ACL_Exception.__init__: error = %s", msg)
        log.debug("Base_ACL_Exception.__init__: leave")

    def __str__(self):
        return self.value


class Base_ACL_pipe:
    def __init__(self, cmd):
        log.debug("Base_ACL_pipe.__init__: enter")
        log.debug("Base_ACL_pipe.__init__: cmd = %s", cmd)

        self.__pipe = Popen(
            cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True,
            close_fds=True
        )

        self.__stdin = self.__pipe.stdin
        self.__stdout = self.__pipe.stdout
        self.__stderr = self.__pipe.stderr

        self.__out, err = self.__pipe.communicate()

        log.debug("Base_ACL_pipe.__init__: out = %s", self.__out)

        if self.__pipe.returncode != 0:
            raise Base_ACL_Exception(err)

        log.debug("Base_ACL_pipe.__init__: leave")

    def __str__(self):
        return self.__out

    def __iter__(self):
        lines = self.__out.splitlines()
        for line in lines:
            yield line


class Base_ACL_getfacl:
    def __init__(self, path, flags=0):
        log.debug("Base_ACL_getfacl.__init__: enter")
        log.debug(
            "Base_ACL_getfacl.__init__: path = %s, flags = 0x%08x",
            path,
            flags
        )

        self.__getfacl = GETFACL_PATH
        self.__path = path

        args = self._build_args(path, flags)

        cmd = "%s " % self.__getfacl
        if args:
            cmd += "%s " % args
        cmd += quote(self.__path)

        self.__out = str(Base_ACL_pipe(cmd))

        log.debug("Base_ACL_getfacl.__init__: out = %s", self.__out)
        log.debug("Base_ACL_getfacl.__init__: leave")

    def _build_args(self, path, flags):
        return None

    def __str__(self):
        return self.__out

    def __iter__(self):
        lines = self.__out.splitlines()
        for line in lines:
            yield line


class Base_ACL_setfacl(object):

    _entry = None

    def __init__(self, path, entry=None, flags=0, pos=0):
        log.debug("Base_ACL_setfacl.__init__: enter")
        log.debug(
            "Base_ACL_setfacl.__init__: path = %s, entry = %s, flags = 0x%08x",
            path,
            entry if entry else "",
            flags
        )

        self.__setfacl = SETFACL_PATH
        self.__path = path
        self._entry = entry

        args = self._build_args(path, entry, flags, pos)

        cmd = "%s " % self.__setfacl
        if args:
            cmd += "%s " % args
        if self._entry:
            cmd += "%s " % self._entry
        cmd += quote(self.__path)

        self.__out = str(Base_ACL_pipe(cmd))

        log.debug("Base_ACL_setfacl.__init__: out = %s", self.__out)
        log.debug("Base_ACL_setfacl.__init__: leave")

    def _build_args(self, path, entry, flags, pos):
        return None


class Base_ACL_Entry:
    pass


class Base_ACL(object):

    @staticmethod
    def get_acl_type(path):
        if not path:
            return 0
        if not os.access(path, 0):
            return 0

        type = ACL_FLAGS_NONE
        for line in Base_ACL_getfacl(path):
            if not line.startswith("#"):
                line = line.strip()
                parts = line.split(':')
                type = (ACL_FLAGS_TYPE_NFSV4 if (len(parts) > 3) else ACL_FLAGS_TYPE_POSIX)
                break

        return type

    @staticmethod
    def get_acl_ostype(path):
        ostype = ACL_FLAGS_OS_UNIX
        if os.access(os.path.join(path, ACL_WINDOWS_FILE), 0):
            ostype = ACL_FLAGS_OS_WINDOWS

        return ostype

    def __init__(self, path, acl=None):
        log.debug("Base_ACL.__init__: enter")
        log.debug(
            "Base_ACL.__init__: path = %s, acl = %s",
            path,
            acl if acl else ""
        )

        #
        # Array ACL_Entry's
        #
        self.__entries = []
        self.__file = None
        self.__owner = None
        self.__group = None

        self.__dirty = False
        self.__path = path
        self.__flags = ACL_FLAGS_NONE

        st = os.stat(self.__path)
        self.__mode = st.st_mode

        self.__flags |= self.__acl_ostype()
        self.__flags |= self.__acl_type()
        self._load()

        log.debug(
            "Base_ACL.__init__: owner = %s, group = %s, flags = 0x%08x",
            self.__owner,
            self.__group,
            self.__flags
        )
        log.debug("Base_ACL.__init__: leave")

    def __acl_type(self):
        type = ACL_FLAGS_TYPE_POSIX
        for line in Base_ACL_getfacl(self.path):
            if not line.startswith("#"):
                line = line.strip()
                parts = line.split(':')
                type = (ACL_FLAGS_TYPE_NFSV4 if (len(parts) > 3) else ACL_FLAGS_TYPE_POSIX)
                break
        return type

    def __acl_ostype(self):
        ostype = ACL_FLAGS_OS_UNIX
        if os.access(os.path.join(self.__path, ACL_WINDOWS_FILE), 0):
            ostype = ACL_FLAGS_OS_WINDOWS
        return ostype

    def set_entries(self, entry):
        if entry:
            self.__entries.append(entry)
        else:
            self.__entries = entry

    def get_entries(self):
        return self.__entries
    entries = property(get_entries, set_entries)

    def set_file(self, file):
        self.__file = file

    def get_file(self):
        return self.__file
    file = property(get_file, set_file)

    def set_owner(self, owner):
        self.__owner = owner

    def get_owner(self):
        return self.__owner
    owner = property(get_owner, set_owner)

    def set_group(self, group):
        self.__group = group

    def get_group(self):
        return self.__group
    group = property(get_group, set_group)

    def set_unix(self, value):
        self.__flags = (
            (self.__flags | ACL_FLAGS_OS_UNIX)
            if value else (self.flags & ~ACL_FLAGS_OS_UNIX)
        )

    def get_unix(self):
        return (True if self.__flags & ACL_FLAGS_OS_UNIX else False)
    unix = property(get_unix, set_unix)

    def set_windows(self, value):
        self.__flags = (
            (self.__flags | ACL_FLAGS_OS_WINDOWS)
            if value else (self.flags & ~ACL_FLAGS_OS_WINDOWS)
        )

    def get_windows(self):
        return (True if self.__flags & ACL_FLAGS_OS_WINDOWS else False)
    windows = property(get_windows, set_windows)

    def set_posix(self, value):
        self.__flags = (
            (self.__flags | ACL_FLAGS_TYPE_POSIX)
            if value else (self.flags & ~ACL_FLAGS_TYPE_POSIX)
        )

    def get_posix(self):
        return (True if self.__flags & ACL_FLAGS_TYPE_POSIX else False)
    posix = property(get_posix, set_posix)

    def set_nfsv4(self, value):
        self.__flags = (
            (self.__flags | ACL_FLAGS_TYPE_NFSV4)
            if value else (self.flags & ~ACL_FLAGS_TYPE_NFSV4)
        )

    def get_nfsv4(self):
        return (True if self.__flags & ACL_FLAGS_TYPE_NFSV4 else False)
    nfsv4 = property(get_nfsv4, set_nfsv4)

    def set_flags(self, value):
        pass

    def get_flags(self):
        return self.__flags
    flags = property(get_flags, set_flags)

    def set_path(self, path):
        self.__path = path

    def get_path(self):
        return self.__path
    path = property(get_path, set_path)

    def set_dirty(self, dirty):
        self.__dirty = dirty

    def get_dirty(self):
        return self.__dirty
    dirty = property(get_dirty, set_dirty)

    def set_mode(self, mode):
        pass

    def get_mode(self):
        return self.__mode
    mode = property(get_mode, set_mode)

    def _load(self):
        pass

    def _refresh(self):
        self.entries = []
        self._load()
        # self_dirty = False

    def update(self, *args, **kwargs):
        pass

    def add(self, *args, **kwargs):
        pass

    def get(self, *args, **kwargs):
        pass

    def remove(self, *args, **kwargs):
        pass

    def reset(self, *args, **kwargs):
        pass

    def clear(self, *args, **kwargs):
        pass

    def chmod(self, mode):
        log.debug("Base_ACL.chmod: enter")
        log.debug("Base_ACL.chmod: mode = %s", mode)

        os.chmod(self.path, int(mode, 8))

        log.debug("Base_ACL.chmod: leave")

    def chown(self, who):
        log.debug("Base_ACL.chown: enter")
        log.debug("Base_ACL.chown: who = %s", who)

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

        os.chown(self.path, uid, gid)
        self._refresh()

        log.debug("Base_ACL.chown: leave")
        return True

    def save(self):
        if not self.dirty:
            return False

        self._refresh()
        return True


class Base_ACL_Hierarchy(Base_ACL):

    def __init__(self, path, acl=None):
        super(Base_ACL_Hierarchy, self).__init__(path, acl)

        self.__jobs = []

    def _recurse(self, path, callback, *args, **kwargs):
        callback(path, *args, **kwargs)

        files = os.listdir(path)
        decoded = path.decode('utf-8')
        for f in files:
            file = os.path.join(decoded, f.decode('utf-8')).encode('utf-8')
            st = os.lstat(file)

            # Do not follow symbolic links (default for chmod)
            if stat.S_ISLNK(st.st_mode):
                continue

            if stat.S_ISDIR(st.st_mode):
                if self.get_acl_ostype(path) == ACL_FLAGS_OS_WINDOWS:
                    self.windows = True
                self._recurse(file, callback, *args, **kwargs)

            else:
                if f != ACL_WINDOWS_FILE:
                    callback(file, *args, **kwargs)

    def new_ACL(self, path):
        return Base_ACL(path)

    def _set_windows_file_defaults(self, acl):
        pass

    def _set_windows_directory_defaults(self, acl):
        pass

    def _set_unix_file_defaults(self, acl):
        pass

    def _set_unix_directory_defaults(self, acl):
        pass

    def __set_file_defaults(self, acl):
        log.debug("Base_ACL_Hierarchy.__set_file_defaults: enter")
        log.debug("Base_ACL_Hierarchy.__set_file_defaults: acl = %s", acl)

        if self.windows:
            self._set_windows_file_defaults(acl)
        else:
            self._set_unix_file_defaults(acl)

        log.debug("Base_ACL_Hierarchy.__set_file_defaults: leave")

    def __set_directory_defaults(self, acl):
        if self.windows:
            self._set_windows_directory_defaults(acl)
        else:
            self._set_unix_directory_defaults(acl)

    def __set_defaults(self, path, *args, **kwargs):
        log.debug("Base_ACL_Hierarchy.__set_defaults: enter")
        log.debug("Base_ACL_Hierarchy.__set_defaults: path = %s", path)

        acl = self.new_ACL(path)

        if stat.S_ISREG(acl.mode):
            self.__set_file_defaults(acl)
        elif stat.S_ISDIR(acl.mode):
            self.__set_directory_defaults(acl)
        else:
            self.__set_file_defaults(acl)

        acl.save()
        log.debug("Base_ACL_Hierarchy.__set_defaults: leave")

    def set_defaults(self, *args, **kwargs):
        if 'recursive' in kwargs and kwargs['recursive'] is True:
            self._recurse(self.path, self.__set_defaults, *args, **kwargs)
        else:
            self.__set_defaults(self.path, *args, **kwargs)

    def __reset(self, path, *args, **kwargs):
        log.debug("Base_ACL_Hierarchy.__reset: enter")
        log.debug("Base_ACL_Hierarchy.__reset: path = %s", path)

        acl = self.new_ACL(path)
        acl.reset(*args, **kwargs)
        acl.save()

        log.debug("Base_ACL_Hierarchy.__reset: leave")

    def reset(self, *args, **kwargs):
        if 'recursive' in kwargs and kwargs['recursive'] is True:
            self._recurse(self.path, self.__reset, *args, **kwargs)
        else:
            self.__reset(self.path, *args, **kwargs)

    def __clear(self, path, *args, **kwargs):
        log.debug("Base_ACL_Hierarchy.__clear: enter")
        log.debug("Base_ACL_Hierarchy.__clear: path = %s", path)

        acl = self.new_ACL(path)
        acl.clear(*args, **kwargs)
        acl.save()

        log.debug("Base_ACL_Hierarchy.__clear: leave")

    def clear(self, *args, **kwargs):
        if 'recursive' in kwargs and kwargs['recursive'] is True:
            self._recurse(self.path, self.__clear, *args, **kwargs)
        else:
            self.__clear(self.path, *args, **kwargs)

    def __add(self, path, *args, **kwargs):
        log.debug("Base_ACL_Hierarchy.__add: enter")
        log.debug("Base_ACL_Hierarchy.__add: path = %s", path)

        acl = self.new_ACL(path)
        acl.add(*args, **kwargs)
        acl.save()

        log.debug("Base_ACL_Hierarchy.__add: leave")

    def add(self, *args, **kwargs):
        if 'recursive' in kwargs and kwargs['recursive'] is True:
            self._recurse(self.path, self.__add, *args, **kwargs)
        else:
            self.__add(self.path, *args, **kwargs)

    def __update(self, path, *args, **kwargs):
        log.debug("Base_ACL_Hierarchy.__update: enter")
        log.debug("Base_ACL_Hierarchy.__update: path = %s", path)

        acl = self.new_ACL(path)
        acl.update(*args, **kwargs)
        acl.save()

        log.debug("Base_ACL_Hierarchy.__update: leave")

    def update(self, *args, **kwargs):
        if 'recursive' in kwargs and kwargs['recursive'] is True:
            self._recurse(self.path, self.__update, *args, **kwargs)
        else:
            self.__update(self.path, *args, **kwargs)

    def __remove(self, path, *args, **kwargs):
        log.debug("Base_ACL_Hierarchy.__remove: enter")
        log.debug("Base_ACL_Hierarchy.__remove: path = %s", path)

        acl = self.new_ACL(path)
        acl.remove(*args, **kwargs)
        acl.save()

        log.debug("Base_ACL_Hierarchy.__remove: leave")

    def remove(self, *args, **kwargs):
        if 'recursive' in kwargs and kwargs['recursive'] is True:
            self._recurse(self.path, self.__remove, *args, **kwargs)
        else:
            self.__remove(self.path, *args, **kwargs)

    def __chmod(self, path, mode):
        log.debug("Base_ACL_Hierarchy.__chmod: enter")
        log.debug(
            "Base_ACL_Hierarchy.chmod: path = %s, mode = %s",
            path,
            mode
        )

        acl = self.new_ACL(path)
        acl.chmod(mode)
        acl.save()

        log.debug("Base_ACL_Hierarchy.__chmod: leave")

    def chmod(self, mode, recursive=False):
        log.debug("Base_ACL_Hierarchy.chmod: enter")
        log.debug("Base_ACL_Hierarchy.chmod: mode = %s", mode)

        if recursive:
            self._recurse(self.path, self.__chmod, mode)
        else:
            self.__chmod(self.path, mode)

        log.debug("Base_ACL_Hierarchy.chmod: leave")

    def __chown(self, path, who):
        log.debug("Base_ACL_Hierarchy.__chown: enter")
        log.debug(
            "Base_ACL_Hierarchy.__chown: path = %s, who = %s",
            path,
            who
        )

        acl = self.new_ACL(path)
        acl.chown(who)
        acl.save()

        log.debug("Base_ACL_Hierarchy.__chown: leave")

    def chown(self, who, recursive=False):
        log.debug("Base_ACL_Hierarchy.chown: enter")
        log.debug("Base_ACL_Hierarchy.chown: who = %s", who)

        if recursive:
            self._recurse(self.path, self.__chown, who)
        else:
            self.__chown(self.path, who)

        log.debug("Base_ACL_Hierarchy.chown: leave")

    def close(self):
        self.path = None
        self.flags = ACL_FLAGS_NONE

    def run(self):
        pass
