#+
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
# $FreeBSD$
#####################################################################
import os
import sys
import syslog

from subprocess import Popen, PIPE
from syslog import syslog, LOG_DEBUG

PBI_PATH = "/usr/local/sbin"
JEXEC_PATH = "/usr/sbin/jexec"

class pbi_arg(object):
    def __init__(self, int, string, arg=False, argname=None):
        self.int = int
        self.string = string
        self.arg = arg 
        self.argname = argname

    def __str__(self):
        return self.string

    def __lt__(self, other):
        return self.int < other
    def __le__(self, other):
        return self.int <= other
    def __eq__(self, other):
        return self.int == other
    def __ne__(self, other):
        return self.int != other
    def __gt__(self, other):
        return self.int > other
    def __ge__(self, other):
        return self.int >= other
    def __add__(self, other):
        return self.int + other
    def __sub__(self, other):
        return self.int - other
    def __mul__(self, other):
        return self.int * other
    def __floordiv__(self, other):
        return self.int // other
    def __mod__(self, other):
        return self.int % other
    def __divmod__(self, other):
        return (self.int // other, self.int % other)
    def __pow__(self, other):
        return self.int ** other
    def __lshift__(self, other):
        return self.int << other
    def __rshift__(self, other):
        return self.int >> other
    def __and__(self, other):
        return self.int & other
    def __xor__(self, other):
        return self.int ^ other
    def __or__(self, other):
        return self.int | other
    def __div__(self, other):
        return self.int / other
    def __truediv__(self, other):
        return self.int / other

    def __radd__(self, other):
        return self.int + other
    def __rsub__(self, other):
        return self.int - other
    def __rmul__(self, other):
        return self.int * other
    def __rdiv__(self, other):
        return self.int / other
    def __rtruediv__(self, other):
        return self.int // other
    def __rfloordiv__(self, other):
        return self.int // other
    def __rmod__(self, other):
        return self.int % other
    def __rdivmod__(self, other):
        return (self.int // other, self.int % other)
    def __rpow__(self, other):
        return self.int ** other
    def __rlshift__(self, other):
        return self.int << other
    def __rrshift__(self, other):
        return self.int << other
    def __rand__(self, other):
        return self.int & other
    def __rxor__(self, other):
        return self.int ^ other
    def __ror__(self, other):
        return self.int | other

    def __iadd__(self, other):
        return self.int + other
    def __isub__(self, other):
        return self.int - other
    def __imul__(self, other):
        return self.int * other
    def __idiv__(self, other):
        return self.int / other
    def __itruediv__(self, other):
        return self.int // other
    def __ifloordiv__(self, other):
        return self.int // other
    def __imod__(self, other):
        return self.int % other
    def __ipow__(self, other):
        return self.int ** other
    def __ilshift__(self, other):
        return self.int << other
    def __irshift__(self, other):
        return self.int >> other
    def __iand__(self, other):
        return self.int & other
    def __ixor__(self, other):
        return self.int ^ other
    def __ior__(self, other):
        return self.int | other


PBI_FLAGS_NONE = pbi_arg(0x00000000, None)


PBI_ADD = os.path.join(PBI_PATH, "pbi_add")
PBI_ADD_FLAGS_EXTRACT_ONLY  = pbi_arg(0x00000001, "-e")
PBI_ADD_FLAGS_FORCE         = pbi_arg(0x00000002, "-f")
PBI_ADD_FLAGS_ICONPATH      = pbi_arg(0x00000004, "-g")
PBI_ADD_FLAGS_INFO          = pbi_arg(0x00000008, "-i")
PBI_ADD_FLAGS_LICENSE       = pbi_arg(0x00000010, "-l")
PBI_ADD_FLAGS_OUTDIR        = pbi_arg(0x00000020, "-o", True, "outdir")
PBI_ADD_FLAGS_FETCH         = pbi_arg(0x00000040, "-r")
PBI_ADD_FLAGS_VERBOSE       = pbi_arg(0x00000080, "-v")
PBI_ADD_FLAGS_CHECKSCRIPT   = pbi_arg(0x00000100, "--checkscript")
PBI_ADD_FLAGS_LICENSE_AGREE = pbi_arg(0x00000200, "--licagree")
PBI_ADD_FLAGS_NOCHECKSUM    = pbi_arg(0x00000400, "--no-checksum")
PBI_ADD_FLAGS_NOCHECKSIG    = pbi_arg(0x00000800, "--no-checksig")
PBI_ADD_FLAGS_NOHASH        = pbi_arg(0x00001000, "--no-hash")
PBI_ADD_FLAGS_ARCH          = pbi_arg(0x00002000, "--rArch", True, "arch")
PBI_ADD_FLAGS_VERSION       = pbi_arg(0x00004000, "--rVer", True, "ver")
PBI_ADD_FLAGS_REPOID        = pbi_arg(0x00008000, "--repoid", True, "repoid")
PBI_ADD_FLAGS = [
    PBI_ADD_FLAGS_EXTRACT_ONLY,
    PBI_ADD_FLAGS_FORCE,
    PBI_ADD_FLAGS_ICONPATH,
    PBI_ADD_FLAGS_INFO,
    PBI_ADD_FLAGS_LICENSE,
    PBI_ADD_FLAGS_OUTDIR,
    PBI_ADD_FLAGS_FETCH,
    PBI_ADD_FLAGS_VERBOSE,
    PBI_ADD_FLAGS_CHECKSCRIPT,
    PBI_ADD_FLAGS_LICENSE_AGREE,
    PBI_ADD_FLAGS_NOCHECKSUM,
    PBI_ADD_FLAGS_NOCHECKSIG,
    PBI_ADD_FLAGS_NOHASH,
    PBI_ADD_FLAGS_ARCH,
    PBI_ADD_FLAGS_VERSION,
    PBI_ADD_FLAGS_REPOID
]


PBI_ADDREPO = os.path.join(PBI_PATH, "pbi_addrepo")
# no flags...


PBI_AUTOBUILD = os.path.join(PBI_PATH, "pbi_autobuild")
PBI_AUTOBUILD_FLAGS_CONFDIR  = pbi_arg(0x00000001, "-c", True, "confdir")
PBI_AUTOBUILD_FLAGS_PORTDIR  = pbi_arg(0x00000002, "-d", True, "portdir")
PBI_AUTOBUILD_FLAGS_SCRIPT   = pbi_arg(0x00000004, "-h", True, "script")
PBI_AUTOBUILD_FLAGS_OUTDIR   = pbi_arg(0x00000008, "-o", True, "outdir")
PBI_AUTOBUILD_FLAGS_GENPATCH = pbi_arg(0x00000010, "--genpatch")
PBI_AUTOBUILD_FLAGS_KEEP     = pbi_arg(0x00000020, "--key", True, "num")
PBI_AUTOBUILD_FLAGS_PRUNE    = pbi_arg(0x00000040, "--prune")
PBI_AUTOBUILD_FLAGS_TMPFS    = pbi_arg(0x00000080, "--tmpfs")
PBI_AUTOBUILD_FLAGS_SIGN     = pbi_arg(0x00000100, "--sign", True, "key")
PBI_AUTOBUILD_FLAGS = [
    PBI_AUTOBUILD_FLAGS_CONFDIR,
    PBI_AUTOBUILD_FLAGS_PORTDIR,
    PBI_AUTOBUILD_FLAGS_SCRIPT,
    PBI_AUTOBUILD_FLAGS_OUTDIR,
    PBI_AUTOBUILD_FLAGS_GENPATCH,
    PBI_AUTOBUILD_FLAGS_KEEP,
    PBI_AUTOBUILD_FLAGS_PRUNE,
    PBI_AUTOBUILD_FLAGS_TMPFS,
    PBI_AUTOBUILD_FLAGS_SIGN
]


PBI_BROWSER = os.path.join(PBI_PATH, "pbi_browser")
# no flags...


PBI_CREATE = os.path.join(PBI_PATH, "pbi_create")
PBI_CREATE_FLAGS_AUTHOR  = pbi_arg(0x00000001, "-a", True, "author")
PBI_CREATE_FLAGS_BACKUP  = pbi_arg(0x00000002, "-b")
PBI_CREATE_FLAGS_CONFDIR = pbi_arg(0x00000004, "-c", True, "confdir")
PBI_CREATE_FLAGS_PORTDIR = pbi_arg(0x00000008, "-d", True, "portdir")
PBI_CREATE_FLAGS_ICON    = pbi_arg(0x00000010, "-i", True, "icon")
PBI_CREATE_FLAGS_NAME    = pbi_arg(0x00000020, "-n", True, "name")
PBI_CREATE_FLAGS_OUTDIR  = pbi_arg(0x00000040, "-o", True, "outdir")
PBI_CREATE_FLAGS_PORT    = pbi_arg(0x00000080, "-p", True, "port")
PBI_CREATE_FLAGS_VERSION = pbi_arg(0x00000100, "-r", True, "version")
PBI_CREATE_FLAGS_URL     = pbi_arg(0x00000200, "-w", True, "url")
PBI_CREATE_FLAGS_NOHASH  = pbi_arg(0x00000400, "--no-hash")
PBI_CREATE_FLAGS_SIGN    = pbi_arg(0x00000800, "--sign", True, "key")
PBI_CREATE_FLAGS = [
    PBI_CREATE_FLAGS_AUTHOR,
    PBI_CREATE_FLAGS_BACKUP,
    PBI_CREATE_FLAGS_CONFDIR,
    PBI_CREATE_FLAGS_PORTDIR,
    PBI_CREATE_FLAGS_ICON,
    PBI_CREATE_FLAGS_NAME,
    PBI_CREATE_FLAGS_OUTDIR,
    PBI_CREATE_FLAGS_PORT,
    PBI_CREATE_FLAGS_VERSION,
    PBI_CREATE_FLAGS_URL,
    PBI_CREATE_FLAGS_NOHASH,
    PBI_CREATE_FLAGS_SIGN
]


PBI_DELETE = os.path.join(PBI_PATH, "pbi_delete")
PBI_DELETE_FLAGS_VERBOSE       = pbi_arg(0x00000001, "-v")
PBI_DELETE_FLAGS_CLEAN_HASHDIR = pbi_arg(0x00000002, "--clean-hdir")
PBI_DELETE_FLAGS = [
    PBI_DELETE_FLAGS_VERBOSE,
    PBI_DELETE_FLAGS_CLEAN_HASHDIR
]


PBI_DELETEREPO = os.path.join(PBI_PATH, "pbi_deleterepo")
# no flags...


PBI_ICON = os.path.join(PBI_PATH, "pbi_icon")
PBI_ICON_FLAGS_ADD_DESKTOP     = pbi_arg(0x00000001, "add-desktop")
PBI_ICON_FLAGS_ADD_MENU        = pbi_arg(0x00000002, "add-menu")
PBI_ICON_FLAGS_ADD_MIME        = pbi_arg(0x00000004, "add-mime")
PBI_ICON_FLAGS_ADD_PATHLINK    = pbi_arg(0x00000008, "add-pathlnk")
PBI_ICON_FLAGS_DELETE_DESKTOP  = pbi_arg(0x00000010, "del-desktop")
PBI_ICON_FLAGS_DELETE_MENU     = pbi_arg(0x00000020, "del-menu")
PBI_ICON_FLAGS_DELETE_MIME     = pbi_arg(0x00000040, "del-mime")
PBI_ICON_FLAGS_DELETE_PATHLINK = pbi_arg(0x00000080, "del-pathlnk")
PBI_ICON_FLAGS = [
    PBI_ICON_FLAGS_ADD_DESKTOP,
    PBI_ICON_FLAGS_ADD_MENU,
    PBI_ICON_FLAGS_ADD_MIME,
    PBI_ICON_FLAGS_ADD_PATHLINK,
    PBI_ICON_FLAGS_DELETE_DESKTOP,
    PBI_ICON_FLAGS_DELETE_MENU,
    PBI_ICON_FLAGS_DELETE_MIME,
    PBI_ICON_FLAGS_DELETE_PATHLINK
]


PBI_INDEXTOOL = os.path.join(PBI_PATH, "pbi_indextool")
PBI_INDEXTOOL_FLAGS_ADD    = pbi_arg(0x00000001, "add")
PBI_INDEXTOOL_FLAGS_REMOVE = pbi_arg(0x00000002, "rem")
PBI_INDEXTOOL_FLAGS = [
    PBI_INDEXTOOL_FLAGS_ADD,
    PBI_INDEXTOOL_FLAGS_REMOVE
]


PBI_INFO = os.path.join(PBI_PATH, "pbi_info")
# no flags...


PBI_LISTREPO = os.path.join(PBI_PATH, "pbi_listrepo")
# no flags...


PBI_MAKEPATCH = os.path.join(PBI_PATH, "pbi_makepatch")
PBI_MAKEPATCH_FLAGS_OUTDIR = pbi_arg(0x00000001, "-o", True, "outdir")
PBI_MAKEPATCH_FLAGS_SIGN   = pbi_arg(0x00000002, "--sign", True, "key")
PBI_MAKEPATCH_FLAGS = [
    PBI_MAKEPATCH_FLAGS_OUTDIR,
    PBI_MAKEPATCH_FLAGS_SIGN
]


PBI_MAKEPORT = os.path.join(PBI_PATH, "pbi_makeport")
# no flags...


PBI_MAKEREPO = os.path.join(PBI_PATH, "pbi_makerepo")
PBI_MAKEREPO_FLAGS_DESC   = pbi_arg(0x00000001, "--desc", True, "description")
PBI_MAKEREPO_FLAGS_KEY    = pbi_arg(0x00000002, "--key", True, "key")
PBI_MAKEREPO_FLAGS_URL    = pbi_arg(0x00000004, "--url", True, "url")
PBI_MAKEREPO_FLAGS_MIRROR = pbi_arg(0x00000008, "--mirror", True, "mirrorurl")
PBI_MAKEREPO_FLAGS = [
    PBI_MAKEREPO_FLAGS_DESC,
    PBI_MAKEREPO_FLAGS_KEY,
    PBI_MAKEREPO_FLAGS_URL,
    PBI_MAKEREPO_FLAGS_MIRROR
]


PBI_METATOOL = os.path.join(PBI_PATH, "pbi_metatool")
PBI_METATOOL_FLAGS_ADD    = pbi_arg(0x00000001, "add")
PBI_METATOOL_FLAGS_REMOVE = pbi_arg(0x00000002, "rem")
PBI_METATOOL_FLAGS = [
    PBI_METATOOL_FLAGS_ADD,
    PBI_METATOOL_FLAGS_REMOVE
]


PBI_PATCH = os.path.join(PBI_PATH, "pbi_patch")
PBI_PATCH_FLAGS_EXTRACT_ONLY = pbi_arg(0x00000001, "-e")
PBI_PATCH_FLAGS_ICONPATH     = pbi_arg(0x00000002, "-g")
PBI_PATCH_FLAGS_INFO         = pbi_arg(0x00000004, "-i")
PBI_PATCH_FLAGS_OUTDIR       = pbi_arg(0x00000008, "-o", True, "outdir")
PBI_PATCH_FLAGS_CHECKSCRIPT  = pbi_arg(0x00000010, "--checkscript")
PBI_PATCH_FLAGS_NOCHECKSIG   = pbi_arg(0x00000020, "--no-checksig")
PBI_PATCH_FLAGS_NOHASH       = pbi_arg(0x00000040, "--no-hash")
PBI_PATCH_FLAGS = [
    PBI_PATCH_FLAGS_EXTRACT_ONLY,
    PBI_PATCH_FLAGS_ICONPATH,
    PBI_PATCH_FLAGS_INFO,
    PBI_PATCH_FLAGS_OUTDIR,
    PBI_PATCH_FLAGS_CHECKSCRIPT,
    PBI_PATCH_FLAGS_NOCHECKSIG,
    PBI_PATCH_FLAGS_NOHASH
]


PBI_UPDATE = os.path.join(PBI_PATH, "pbi_update")
PBI_UPDATE_FLAGS_CHECK_ONLY   = pbi_arg(0x00000001, "-c")
PBI_UPDATE_FLAGS_CHECK_ALL    = pbi_arg(0x00000002, "--check-all")
PBI_UPDATE_FLAGS_DISABLE_AUTO = pbi_arg(0x00000004, "--disable-auto")
PBI_UPDATE_FLAGS_ENABLE_AUTO  = pbi_arg(0x00000008, "--enable-auto")
PBI_UPDATE_FLAGS_UPDATE_ALL   = pbi_arg(0x00000010, "--update-all")
PBI_UPDATE_FLAGS = [
    PBI_UPDATE_FLAGS_CHECK_ONLY,
    PBI_UPDATE_FLAGS_CHECK_ALL,
    PBI_UPDATE_FLAGS_DISABLE_AUTO,
    PBI_UPDATE_FLAGS_ENABLE_AUTO,
    PBI_UPDATE_FLAGS_UPDATE_ALL
]


PBI_UPDATE_HASHDIR = os.path.join(PBI_PATH, "pbi_update_hashdir")
# no flags...


PBID = os.path.join(PBI_PATH, "pbid")
# no flags...


class pbi_exception(Exception):
    def __init__(self, msg = None):
        syslog(LOG_DEBUG, "pbi_exception.__init__: enter")
        if msg:
            syslog(LOG_DEBUG, "pbi_exception.__init__: error = %s" % msg)
        syslog(LOG_DEBUG, "pbi_exception.__init__: leave")


class pbi_pipe(object):
    def __init__(self, cmd, func=None, **kwargs):
        syslog(LOG_DEBUG, "pbi_pipe.__init__: enter") 
        syslog(LOG_DEBUG, "pbi_pipe.__init__: cmd = %s" % cmd) 

        self.__pipe = Popen(cmd, stdin = PIPE, stdout = PIPE,
            stderr = PIPE, shell = True, close_fds = True)

        self.__stdin = self.__pipe.stdin
        self.__stdout = self.__pipe.stdout
        self.__stderr = self.__pipe.stderr

        self.__out = ""
        if func is not None:
            for line in self.__stdout: 
                line = line.strip()
                self.__out += line
                func(line, **kwargs)

        else:
            self.__out = self.__stdout.read().strip()

        self.__pipe.wait()
        syslog(LOG_DEBUG, "pbi_pipe.__init__: out = %s" % self.__out)

        if self.__pipe.returncode != 0:
            raise pbi_exception(self.__stderr.read().strip())

        self.returncode = self.__pipe.returncode
        syslog(LOG_DEBUG, "pbi_pipe.__init__: leave")

    def __str__(self):
        return self.__out

    def __iter__(self):
        lines = self.__out.splitlines()
        for line in lines:
            yield line


class pbi_base(object):
    def __init__(self, path, objflags, flags=PBI_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "pbi_base.__init__: enter")
        syslog(LOG_DEBUG, "pbi_base.__init__: path = %s" % path)
        syslog(LOG_DEBUG, "pbi_base.__init__: flags = 0x%08x" % (flags + 0))

        self.path = path
        self.flags = flags 
        self.args = "" 

        if objflags is None:
            objflags = []

        for obj in objflags:
            if self.flags & obj:
                if obj.arg == True and obj.argname is not None and \
                    kwargs.has_key(obj.argname) and kwargs[obj.argname] is not None:
                    self.args += " %s %s" % (obj, kwargs[obj.argname])

                elif obj.arg == False: 
                    self.args += " %s" % obj

        syslog(LOG_DEBUG, "pbi_base.__init__: args = %s" % self.args)

        self.pipe_func = None
        if kwargs.has_key("pipe_func") and kwargs["pipe_func"] is not None:
            self.pipe_func = kwargs["pipe_func"]

        syslog(LOG_DEBUG, "pbi_base.__init__: leave")

    def run(self, jail=False, jid=0):
        syslog(LOG_DEBUG, "pbi_base.run: enter")

        cmd = self.path
        if self.args is not None:
            cmd += " %s" % self.args

        if jail == True and jid > 0:
            cmd = "%s %d %s" % (JEXEC_PATH, jid, cmd.strip())

        syslog(LOG_DEBUG, "pbi_base.cmd = %s" % cmd)
        pobj = pbi_pipe(cmd, self.pipe_func)

        syslog(LOG_DEBUG, "pbi_base.run: leave")
        return (pobj.returncode, str(pobj))

    def __str__(self):
        return self.args


class pbi_add(pbi_base):
    def __init__(self, flags=PBI_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "pbi_add.__init__: enter")

        super(pbi_add, self).__init__(PBI_ADD, PBI_ADD_FLAGS, flags, **kwargs)

        self.pbi = None
        if kwargs.has_key("pbi") and kwargs["pbi"] is not None:
            self.pbi = kwargs["pbi"]
            self.args += " %s" % self.pbi

        syslog(LOG_DEBUG, "pbi_add.__init__: pbi = %s" % self.pbi)
        syslog(LOG_DEBUG, "pbi_add.__init__: leave")

    def info(self, jail=False, jid=0, *args):
         ret = []
         out = super(pbi_add, self).run(jail, jid)
         if out and out[0] == 0:
             out = out[1]
             for line in out.splitlines():
                 parts = line.split(':')
                 for arg in args:
                     if parts[0].strip().upper() == arg.strip().upper():
                         ret.append("%s=%s" % (parts[0].strip(), parts[1].strip()))
         return ret


class pbi_addrepo(pbi_base):
    def __init__(self, flags=PBI_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "pbi_addrepo.__init__: enter")

        super(pbi_addrepo, self).__init__(PBI_ADDREPO, None, flags, **kwargs)

        self.repofile = None
        if kwargs.has_key("repofile") and kwargs["repofile"] is not None:
            self.repofile = kwargs["repofile"]
            self.args += " %s" % self.repofile

        syslog(LOG_DEBUG, "pbi_addrepo.__init__: repofile = %s" % self.repofile)
        syslog(LOG_DEBUG, "pbi_addrepo.__init__: leave")


class pbi_autobuild(pbi_base):
    def __init__(self, flags=PBI_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "pbi_autobuild.__init__: enter")

        super(pbi_autobuild, self).__init__(PBI_AUTOBUILD, PBI_AUTOBUILD_FLAGS, flags, **kwargs)

        syslog(LOG_DEBUG, "pbi_autobuild.__init__: leave")


class pbi_browser(pbi_base):
    def __init__(self, flags=PBI_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "pbi_browser.__init__: enter")

        super(pbi_browser, self).__init__(PBI_BROWSER, None, flags, **kwargs)

        syslog(LOG_DEBUG, "pbi_browser.__init__: leave")


class pbi_create(pbi_base):
    def __init__(self, flags=PBI_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "pbi_create.__init__: enter")

        super(pbi_create, self).__init__(PBI_CREATE, PBI_CREATE_FLAGS, flags, **kwargs)

        self.pbidir = None
        if kwargs.has_key("pbidir") and kwargs["pbidir"] is not None:
            self.pbidir = kwargs["pbidir"]
            self.args += " %s" % self.pbidir

        syslog(LOG_DEBUG, "pbi_create.__init__: pbidir = %s" % self.pbidir)
        syslog(LOG_DEBUG, "pbi_create.__init__: leave")


class pbi_delete(pbi_base):
    def __init__(self, flags=PBI_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "pbi_delete.__init__: enter")

        super(pbi_delete, self).__init__(PBI_DELETE, PBI_DELETE_FLAGS, flags, **kwargs) 

        self.pbi = None
        if kwargs.has_key("pbi") and kwargs["pbi"] is not None:
            self.pbi = kwargs["pbi"]
            self.args += " %s" % self.pbi

        syslog(LOG_DEBUG, "pbi_delete.__init__: pbi = %s" % self.pbi)
        syslog(LOG_DEBUG, "pbi_delete.__init__: leave")


class pbi_deleterepo(pbi_base):
    def __init__(self, flags=PBI_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "pbi_deleterepo.__init__: enter")

        super(pbi_deleterepo, self).__init__(PBI_DELETEREPO, None, flags, **kwargs) 

        self.repoid = None
        if kwargs.has_key("repoid") and kwargs["repoid"] is not None:
            self.repoid = kwargs["repoid"]
            self.args += " %s" % self.repoid

        syslog(LOG_DEBUG, "pbi_deleterepo.__init__: repoid = %s" % self.repoid)
        syslog(LOG_DEBUG, "pbi_deleterepo.__init__: leave")


class pbi_icon(pbi_base):
    def __init__(self, flags=PBI_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "pbi_icon.__init__: enter")

        super(pbi_icon, self).__init__(PBI_ICON, PBI_ICON_FLAGS, flags, **kwargs) 

        self.pbi = None
        if kwargs.has_key("pbi") and kwargs["pbi"] is not None:
            self.pbi = kwargs["pbi"]
            self.args += " %s" % self.pbi

        syslog(LOG_DEBUG, "pbi_icon.__init__: pbi = %s" % self.pbi)
        syslog(LOG_DEBUG, "pbi_icon.__init__: leave")


class pbi_indextool(pbi_base):
    def __init__(self, flags=PBI_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "pbi_indextool.__init__: enter")

        super(pbi_indextool, self).__init__(PBI_INDEXTOOL, PBI_INDEXTOOL_FLAGS, flags, **kwargs) 

        self.indexfile = None
        if kwargs.has_key("indexfile") and kwargs["indexfile"] is not None:
            self.indexfile = kwargs["indexfile"]
            self.args += " %s" % self.indexfile

        syslog(LOG_DEBUG, "pbi_indextool.__init__: indexfile = %s" % self.indexfile)
        syslog(LOG_DEBUG, "pbi_indextool.__init__: leave")


class pbi_info(pbi_base):
    def __init__(self, flags=PBI_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "pbi_info.__init__: enter")

        super(pbi_info, self).__init__(PBI_INFO, None, flags, **kwargs) 

        self.pbi = None
        if kwargs.has_key("pbi") and kwargs["pbi"] is not None:
            self.pbi = kwargs["pbi"]
            self.args += " %s" % self.pbi

        syslog(LOG_DEBUG, "pbi_info.__init__: pbi = %s" % self.pbi)
        syslog(LOG_DEBUG, "pbi_info.__init__: leave")


class pbi_listrepo(pbi_base):
    def __init__(self, flags=PBI_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "pbi_listrepo.__init__: enter")

        super(pbi_listrepo, self).__init__(PBI_LISTREPO, None, flags, **kwargs) 

        self.repoid = None
        if kwargs.has_key("repoid") and kwargs["repoid"] is not None:
            self.repoid = kwargs["repoid"]
            self.args += " %s" % self.repoid

        syslog(LOG_DEBUG, "pbi_listrepo.__init__: repoid = %s" % self.repoid)
        syslog(LOG_DEBUG, "pbi_listrepo.__init__: leave")


class pbi_makepatch(pbi_base):
    def __init__(self, flags=PBI_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "pbi_makepatch.__init__: enter")

        super(pbi_makepatch, self).__init__(PBI_MAKEPATCH, PBI_MAKEPATCH_FLAGS, flags, **kwargs) 

        self.oldpbi = self.newpbi = None
        if kwargs.has_key("oldpbi") and kwargs["oldpbi"] is not None:
            self.oldpbi = kwargs["oldpbi"]
            self.args += " %s" % self.oldpbi
        if kwargs.has_key("newpbi") and kwargs["newpbi"] is not None:
            self.newpbi = kwargs["newpbi"]
            self.args += " %s" % self.newpbi

        syslog(LOG_DEBUG, "pbi_makepatch.__init__: oldpbi = %s, newpbi = %s" % (self.oldpbi, self.newpbi))
        syslog(LOG_DEBUG, "pbi_makepatch.__init__: leave")


class pbi_makeport(pbi_base):
    def __init__(self, flags=PBI_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "pbi_makeport.__init__: enter")

        super(pbi_makeport, self).__init__(PBI_MAKEPORT, None, flags, **kwargs) 

        self.port = None
        if kwargs.has_key("port") and kwargs["port"] is not None:
            self.port = kwargs["port"]
            self.args += " %s" % self.port

        syslog(LOG_DEBUG, "pbi_makeport.__init__: port = %s" % self.port)
        syslog(LOG_DEBUG, "pbi_makeport.__init__: leave")


class pbi_makerepo(pbi_base):
    def __init__(self, flags=PBI_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "pbi_makerepo.__init__: enter")

        super(pbi_makerepo, self).__init__(PBI_MAKEREPO, PBI_MAKEREPO_FLAGS, flags, **kwargs) 

        if kwargs.has_key("outdir") and kwargs["outdir"] is not None:
            self.outdir = kwargs["outdir"]
            self.args += " %s" % self.outdir

        syslog(LOG_DEBUG, "pbi_makerepo.__init__: outdir = %s" % self.outdir)
        syslog(LOG_DEBUG, "pbi_makerepo.__init__: leave")


class pbi_metatool(pbi_base):
    def __init__(self, flags=PBI_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "pbi_metatool.__init__: enter")

        super(pbi_metatool, self).__init__(PBI_METATOOL, PBI_METATOOL_FLAGS, flags, **kwargs) 

        self.metafile = None
        if kwargs.has_key("metafile") and kwargs["metafile"] is not None:
            self.metafile = kwargs["metafile"]
            self.args += " %s" % self.metafile

        syslog(LOG_DEBUG, "pbi_metatool.__init__: metafile = %s" % self.metafile)
        syslog(LOG_DEBUG, "pbi_metatool.__init__: leave")


class pbi_patch(pbi_base):
    def __init__(self, flags=PBI_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "pbi_patch.__init__: enter")

        super(pbi_patch, self).__init__(PBI_PATCH, PBI_PATCH_FLAGS, flags, **kwargs) 

        self.pbp = None
        if kwargs.has_key("pbp") and kwargs["pbp"] is not None:
            self.pbp = kwargs["pbp"]
            self.args += " %s" % self.pbp

        syslog(LOG_DEBUG, "pbi_patch.__init__: pbp = %s" % self.pbp)
        syslog(LOG_DEBUG, "pbi_patch.__init__: leave")


class pbi_update(pbi_base):
    def __init__(self, flags=PBI_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "pbi_update.__init__: enter")

        super(pbi_update, self).__init__(PBI_UPDATE, PBI_UPDATE_FLAGS, flags, **kwargs) 

        self.pbi = None
        if kwargs.has_key("pbi") and kwargs["pbi"] is not None:
            self.pbi = kwargs["pbi"]
            self.args += " %s" % self.pbi

        syslog(LOG_DEBUG, "pbi_update.__init__: pbi = %s" % self.pbi)
        syslog(LOG_DEBUG, "pbi_update.__init__: leave")


class pbi_update_hashdir(pbi_base):
    def __init__(self, flags=PBI_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "pbi_update_hashdir.__init__: enter")

        super(pbi_update_hashdir, self).__init__(PBI_UPDATE_HASHDIR, None, flags, **kwargs) 

        syslog(LOG_DEBUG, "pbi_update_hashdir.__init__: leave")


class pbid(pbi_base):
    def __init__(self, flags=PBI_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "pbid.__init__: enter")

        super(pbid, self).__init__(PBID, None, flags, **kwargs) 

        syslog(LOG_DEBUG, "pbid.__init__: leave")


class PBI(object):
    def __init__(self, flags=PBI_FLAGS_NONE, **kwargs):
        self.flags = flags
        self.path = PBI_PATH
        self.obj = None
        self.out = ""
        self.returncode = 0

    def __call(self, obj):
        if obj is not None:
            tmp = obj.run()
            if tmp is not None and len(tmp) > 1: 
                self.obj = obj
                self.returncode = tmp[0]
                self.out = tmp[1]
                return self.out

        return None 

    def add(self, flags=PBI_FLAGS_NONE, **kwargs):
        return self.__call(pbi_add(flags, **kwargs))

    def addrepo(self, flags=PBI_FLAGS_NONE, **kwargs):
        return self.__call(pbi_addrepo(flags, **kwargs))

    def autobuild(self, flags=PBI_FLAGS_NONE, **kwargs):
        return self.__call(pbi_autobuild(flags, **kwargs))

    def browser(self, flags=PBI_FLAGS_NONE, **kwargs):
        return self.__call(pbi_browser(flags, **kwargs))

    def create(self, flags=PBI_FLAGS_NONE, **kwargs):
        return self.__call(pbi_create(flags, **kwargs))

    def delete(self, flags=PBI_FLAGS_NONE, **kwargs):
        return self.__call(pbi_delete(flags, **kwargs))

    def deleterepo(self, flags=PBI_FLAGS_NONE, **kwargs):
        return self.__call(pbi_deleterepo(flags, **kwargs))

    def icon(self, flags=PBI_FLAGS_NONE, **kwargs):
        return self.__call(pbi_icon(flags, **kwargs))

    def indextool(self, flags=PBI_FLAGS_NONE, **kwargs):
        return self.__call(pbi_indextool(flags, **kwargs))

    def info(self, flags=PBI_FLAGS_NONE, **kwargs):
        return self.__call(pbi_info(flags, **kwargs))

    def listrepo(self, flags=PBI_FLAGS_NONE, **kwargs):
        return self.__call(pbi_listrepo(flags, **kwargs))

    def makepatch(self, flags=PBI_FLAGS_NONE, **kwargs):
        return self.__call(pbi_makepatch(flags, **kwargs))

    def makeport(self, flags=PBI_FLAGS_NONE, **kwargs):
        return self.__call(pbi_makeport(flags, **kwargs))

    def makerepo(self, flags=PBI_FLAGS_NONE, **kwargs):
        return self.__call(pbi_makerepo(flags, **kwargs))

    def metatool(self, flags=PBI_FLAGS_NONE, **kwargs):
        return self.__call(pbi_metatool(flags, **kwargs))

    def patch(self, flags=PBI_FLAGS_NONE, **kwargs):
        return self.__call(pbi_patch(flags, **kwargs))

    def update(self, flags=PBI_FLAGS_NONE, **kwargs):
        return self.__call(pbi_update(flags, **kwargs))

    def update_hashdir(self, flags=PBI_FLAGS_NONE, **kwargs):
        return self.__call(pbi_update_hashdir(flags, **kwargs))

    def pbid(self, flags=PBI_FLAGS_NONE, **kwargs):
        return self.__call(pbid(flags, **kwargs))
