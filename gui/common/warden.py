#+
# Copyright 2013 iXsystems, Inc.
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
import logging
import os

log = logging.getLogger('common.warden')

#
# Python bindings for the PC-BSD warden
#
WARDEN = "/usr/local/bin/warden"
WARDENCONF = "/usr/local/etc/warden.conf"

from freenasUI.common.cmd import cmd_arg, cmd_pipe

class warden_arg(cmd_arg):
    pass
class warden_pipe(cmd_pipe):
    pass
class warden_exception(Exception):
    pass

WARDEN_FLAGS_NONE = warden_arg(0x00000000, None)

WARDEN_AUTO = "auto"
WARDEN_AUTO_FLAGS = []

WARDEN_CHECKUP = "checkup"
WARDEN_CHECKUP_FLAGS_ALL = warden_arg(0x00000001, "all")
WARDEN_CHECKUP_FLAGS = [
    WARDEN_CHECKUP_FLAGS_ALL
]

WARDEN_CHROOT = "chroot"
WARDEN_CHROOT_FLAGS = []

WARDEN_CREATE = "create"
WARDEN_CREATE_FLAGS_32BIT		= warden_arg(0x00000001, "-32")
WARDEN_CREATE_FLAGS_SRC			= warden_arg(0x00000002, "--src")
WARDEN_CREATE_FLAGS_PORTS		= warden_arg(0x00000004, "--ports")
WARDEN_CREATE_FLAGS_STARTAUTO		= warden_arg(0x00000008, "--startauto")
WARDEN_CREATE_FLAGS_PORTJAIL		= warden_arg(0x00000010, "--portjail")
WARDEN_CREATE_FLAGS_PLUGINJAIL		= warden_arg(0x00000020, "--pluginjail")
WARDEN_CREATE_FLAGS_LINUXJAIL		= warden_arg(0x00000040, "--linuxjail", True, "script")
WARDEN_CREATE_FLAGS_ARCHIVE		= warden_arg(0x00000080, "--archive", True, "tar")
WARDEN_CREATE_FLAGS_LINUXARCHIVE	= warden_arg(0x00000100, "--linuxarchive", True, "tar")
WARDEN_CREATE_FLAGS_VERSION		= warden_arg(0x00000200, "--version", True, "string")
WARDEN_CREATE_FLAGS = [
    WARDEN_CREATE_FLAGS_32BIT,
    WARDEN_CREATE_FLAGS_SRC,
    WARDEN_CREATE_FLAGS_PORTS,
    WARDEN_CREATE_FLAGS_STARTAUTO,
    WARDEN_CREATE_FLAGS_PORTJAIL,
    WARDEN_CREATE_FLAGS_PLUGINJAIL,
    WARDEN_CREATE_FLAGS_LINUXJAIL,
    WARDEN_CREATE_FLAGS_ARCHIVE,
    WARDEN_CREATE_FLAGS_LINUXARCHIVE,
    WARDEN_CREATE_FLAGS_VERSION
]

WARDEN_DETALS = "details"
WARDEN_DETAILS_FLAGS = []

WARDEN_DELETE = "delete"
WARDEN_DELETE_FLAGS_CONFIRM = warden_arg(0x00000001, "--confirm")
WARDEN_DELETE_FLAGS = [
    WARDEN_DELETE_FLAGS_CONFIRM
]

WARDEN_EXPORT = "export"
WARDEN_EXPORT_FLAGS_DIR = warden_arg(0x00000001, "--dir", True, "path")
WARDEN_EXPORT_FLAGS = [
    WARDEN_EXPORT_FLAGS_DIR
]

WARDEN_GET = "get"
WARDEN_GET_FLAGS_IP	= warden_arg(0x00000001, "ip")
WARDEN_GET_FLAGS_FLAGS	= warden_arg(0x00000002, "flags")
WARDEN_GET_FLAGS = [
    WARDEN_GET_FLAGS_IP,
    WARDEN_GET_FLAGS_FLAGS
]

WARDEN_IMPORT = "import"
WARDEN_IMPORT_FLAGS_IP		= warden_arg(0x00000001, "--ip", True, "ip")
WARDEN_IMPORT_FLAGS_HOST	= warden_arg(0x00000002, "--host", True, "host")
WARDEN_IMPORT_FLAGS = [
    WARDEN_IMPORT_FLAGS_IP,
    WARDEN_IMPORT_FLAGS_HOST
]

WARDEN_LIST = "list"
WARDEN_LIST_FLAGS_IDS	= warden_arg(0x00000001, "--ids")
WARDEN_LIST_FLAGS = [
    WARDEN_LIST_FLAGS_IDS
]

WARDEN_PKGS = "pkgs"
WARDEN_PKGS_FLAGS = []

WARDEN_PBIS = "pbis"
WARDEN_PBIS_FLAGS = []

WARDEN_SET = "set"
WARDEN_SET_FLAGS_IP	= warden_arg(0x00000001, "ip", True, "ip")
WARDEN_SET_FLAGS_FLAGS	= warden_arg(0x00000002, "flags", True, "jflags")
WARDEN_SET_FLAGS = [
    WARDEN_SET_FLAGS_IP,
    WARDEN_SET_FLAGS_FLAGS
]

WARDEN_START = "start"
WARDEN_START_FLAGS = []

WARDEN_STOP = "stop"
WARDEN_STOP_FLAGS = []

WARDEN_TYPE = "type"
WARDEN_TYPE_FLAGS_PORTJAIL	= warden_arg(0x00000001, "portjail")
WARDEN_TYPE_FLAGS_PLUGINJAIL	= warden_arg(0x00000002, "pluginjail")
WARDEN_TYPE_FLAGS_STANARD	= warden_arg(0x00000004, "standard")
WARDEN_TYPE_FLAGS = [
    WARDEN_TYPE_FLAGS_PORTJAIL,
    WARDEN_TYPE_FLAGS_PLUGINJAIL,
    WARDEN_TYPE_FLAGS_STANARD
]

WARDEN_ZFSMKSNAP = "zfsmksnap"
WARDEN_ZFSMKSNAP_FLAGS = []

WARDEN_ZFSLISTCLONE = "zfslistclone"
WARDEN_ZFSLISTCLONE_FLAGS = []

WARDEN_ZFSLISTSNAP = "zfslistsnap"
WARDEN_ZFSLISTSNAP_FLAGS = []

WARDEN_ZFSCLONESNAP = "zfsclonesnap"
WARDEN_ZFSCLONESNAP_FLAGS = []

WARDEN_ZFSCRONSNAP = "zfscronsnap"
WARDEN_ZFSCRONSNAP_FLAGS = []

WARDEN_ZFSREVERTSNAP = "zfsrevertsnap"
WARDEN_ZFSREVERTSNAP_FLAGS = []

WARDEN_ZFSRMCLONE = "zfsrmclone"
WARDEN_ZFSRMCLONE_FLAGS = []

WARDEN_ZFSRMSNAP = "zfsrmsnap"
WARDEN_ZFSRMSNAP_FLAGS = []


class warden_base(object):
    def __init__(self, cmd, objflags, flags=WARDEN_FLAGS_NONE, **kwargs):
        log.debug("warden_base.__init__: enter")
        log.debug("warden_base.__init__: cmd = %s", cmd)
        log.debug("warden_base.__init__: flags = 0x%08x", flags + 0)

        self.cmd = cmd
        self.flags = flags
        self.error = None
        self.wtmp = None
        self.jdir = None

        if not hasattr(self, "jail"):
            self.jail = None
        if not hasattr(self, "args"):
            self.args = ""

        self.readconf()

        if objflags is None:
            objflags = []

        for obj in objflags:
            if self.flags & obj:
                if obj.arg == True and obj.argname is not None and \
                    kwargs.has_key(obj.argname) and kwargs[obj.argname] is not None:
                    self.args += " %s=%s" % (obj, kwargs[obj.argname])

                elif obj.arg == False:
                    self.args += " %s" % obj

        log.debug("warden_base.__init__: args = %s", self.args)

        self.pipe_func = None
        if kwargs.has_key("pipe_func") and kwargs["pipe_func"] is not None:
            self.pipe_func = kwargs["pipe_func"]

        log.debug("warden_base.__init__: leave")

    def run(self, jail=False, jid=0):
        log.debug("warden_base.run: enter")

        cmd = "%s %s" % (WARDEN, self.cmd)
        if self.args is not None:
            cmd += " %s" % self.args

        if jail == True and jid > 0:
            cmd = "%s %d %s" % (JEXEC_PATH, jid, cmd.strip())

        log.debug("warden_base.cmd = %s", cmd)
        pobj = warden_pipe(cmd, self.pipe_func)
        self.error = pobj.error
        if self.error:
            msg = self.error 
            if pobj.err:
                msg = pobj.err
            raise warden_exception(msg)

        log.debug("warden_base.run: leave")
        return (pobj.returncode, str(pobj))

    def __str__(self):
        return self.args

    def readconf(self):
        wconf = open(WARDENCONF, "r")
        for line in wconf:
            line = line.strip()
            if line.startswith("WTMP:"):
                parts = line.split(':')
                if len(parts) > 1:
                    self.wtmp = parts[1].strip()

            elif line.startswith("JDIR:"):
                parts = line.split(':')
                if len(parts) > 1:
                    self.jdir = parts[1].strip()

        wconf.close()

    def save(self):
        lines = []

        wconf = open(WARDENCONF, "r")
        for line in wconf:
            line = line.strip()
            if line.startswith("WTMP:"):
                line = "WTMP: %s" % self.wtmp

            elif line.startswith("JDIR:"):
                line = "JDIR: %s" % self.jdir

            lines.append(line) 

        wconf.close()

        tmpfile = "%s.tmp" % WARDENCONF

        tmp = open(tmpfile, "w")
        for line in lines:
            tmp.write(line + "\n")
        tmp.close() 

        os.rename(tmpfile, WARDENCONF)


class warden_auto(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if kwargs.has_key("jail") and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " %s" % self.jail

        super(warden_auto, self).__init__(WARDEN_AUTO,
            WARDEN_AUTO_FLAGS, flags, **kwargs)

    def parse(self, thestuff):
        lines = thestuff[1].splitlines()
        for line in lines:
            line = line.strip()
            parts = line.split() 
            return parts[0]
        return None 


class warden_checkup(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        if not (kwargs.has_key("jail") and kwargs["jail"] is not None):
            flags |= WARDEN_CHECKUP_FLAGS_ALL

        super(warden_checkup, self).__init__(WARDEN_CHECKUP,
            WARDEN_CHECKUP_FLAGS, flags, **kwargs)


class warden_chroot(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if kwargs.has_key("jail") and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " %s" % self.jail

        super(warden_chroot, self).__init__(WARDEN_CHROOT,
            WARDEN_CHROOT_FLAGS, flags, **kwargs)


class warden_create(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.ip = None
        self.jail = None

        if kwargs.has_key("jail") and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " %s" % self.jail

        if kwargs.has_key("ip") and kwargs["ip"] is not None:
            self.ip = kwargs["ip"]
            self.args += " %s" % self.ip

        super(warden_create, self).__init__(WARDEN_CREATE,
            WARDEN_CREATE_FLAGS, flags, **kwargs)


class warden_details(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if kwargs.has_key("jail") and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " %s" % self.jail

        super(warden_details, self).__init__(WARDEN_DETAILS,
            WARDEN_DETAILS_FLAGS, flags, **kwargs)


class warden_delete(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if kwargs.has_key("jail") and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " %s" % self.jail

        super(warden_delete, self).__init__(WARDEN_DELETE,
            WARDEN_DELETE_FLAGS, flags, **kwargs)


class warden_export(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if kwargs.has_key("jail") and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " %s" % self.jail

        super(warden_export, self).__init__(WARDEN_EXPORT,
            WARDEN_EXPORT_FLAGS, flags, **kwargs)


class warden_get(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        super(warden_get, self).__init__(WARDEN_GET, WARDEN_GET_FLAGS, flags, **kwargs)

        if kwargs.has_key("jail") and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " %s" % self.jail


class warden_import(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""

        if kwargs.has_key("file") and kwargs["file"] is not None:
            self.file = kwargs["file"]
            self.args += " %s" % self.file

        super(warden_export, self).__init__(WARDEN_EXPORT,
            WARDEN_EXPORT_FLAGS, flags, **kwargs)


class warden_list(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        super(warden_list, self).__init__(WARDEN_LIST, WARDEN_LIST_FLAGS, flags, **kwargs)

    def parse(self, thestuff):
        lines = thestuff[1].splitlines()

        jails = []
        for line in lines:
            line = line.strip()
            if not (line.startswith("HOST") or line.startswith("----")):
                parts = line.split()
                if len(parts) < 5:
                    continue 
                jail = {
                    "host": parts[0],
                    "ip": parts[1],
                    "autostart": parts[2],
                    "status": parts[3],
                    "type": parts[4]
                }

                if self.flags & WARDEN_LIST_FLAGS_IDS:
                    jail["id"] = int(parts[5])

                jails.append(jail)

        return jails


class warden_pkgs(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if kwargs.has_key("jail") and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " %s" % self.jail

        super(warden_pkgs, self).__init__(WARDEN_PKGS,
            WARDEN_PKGS_FLAGS, flags, **kwargs)


class warden_pbis(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if kwargs.has_key("jail") and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " %s" % self.jail

        super(warden_pbis, self).__init__(WARDEN_PBIS,
            WARDEN_PBIS_FLAGS, flags, **kwargs)


class warden_set(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        saved_flags = flags

        if flags & WARDEN_SET_FLAGS_IP:
            flags &= ~WARDEN_SET_FLAGS_IP
            if kwargs.has_key("ip") and kwargs["ip"] is not None:
                self.args = "ip"
                
        elif flags & WARDEN_SET_FLAGS_FLAGS:
            flags &= ~WARDEN_SET_FLAGS_FLAGS
            if kwargs.has_key("jflags") and kwargs["jflags"] is not None:
                self.args = "flags"

        super(warden_set, self).__init__(WARDEN_SET, WARDEN_SET_FLAGS, flags, **kwargs)

        if kwargs.has_key("jail") and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " %s" % self.jail

        if saved_flags & WARDEN_SET_FLAGS_IP:
            if kwargs.has_key("ip") and kwargs["ip"] is not None:
                self.args += " %s" % kwargs["ip"]

        elif saved_flags & WARDEN_SET_FLAGS_FLAGS:
            if kwargs.has_key("jflags") and kwargs["jflags"] is not None:
                self.args += " %s" % kwargs["jflags"]


class warden_start(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if kwargs.has_key("jail") and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " %s" % self.jail

        super(warden_start, self).__init__(WARDEN_START,
            WARDEN_START_FLAGS, flags, **kwargs)


class warden_stop(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if kwargs.has_key("jail") and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " %s" % self.jail

        super(warden_stop, self).__init__(WARDEN_STOP,
            WARDEN_STOP_FLAGS, flags, **kwargs)


class warden_type(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if kwargs.has_key("jail") and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " %s" % self.jail

        super(warden_type, self).__init__(WARDEN_TYPE,
            WARDEN_TYPE_FLAGS, flags, **kwargs)


class warden_zfsmksnap(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if kwargs.has_key("jail") and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " %s" % self.jail

        super(warden_zfsmksnap, self).__init__(WARDEN_ZFSMKSNAP, 
            WARDEN_ZFSMKSNAP_FLAGS, flags, **kwargs)


class warden_zfslistclone(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if kwargs.has_key("jail") and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " %s" % self.jail

        super(warden_zfslistclone, self).__init__(WARDEN_ZFSLISTCLONE, 
            WARDEN_ZFSLISTCLONE_FLAGS, flags, **kwargs)


class warden_zfslistsnap(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if kwargs.has_key("jail") and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " %s" % self.jail

        super(warden_zfslistsnap, self).__init__(WARDEN_ZFSLISTSNAP, 
            WARDEN_ZFSLISTSNAP_FLAGS, flags, **kwargs)


class warden_zfsclonesnap(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None
        self.snap = None

        if kwargs.has_key("jail") and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " %s" % self.jail

        if kwargs.has_key("snap") and kwargs["snap"] is not None:
            self.snap = kwargs["snap"]
            self.args += " %s" % self.snap

        super(warden_zfsclonesnap, self).__init__(WARDEN_ZFSCLONESNAP, 
            WARDEN_ZFSCLONESNAP_FLAGS, flags, **kwargs)


class warden_zfscronsnap(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None
        self.action = None
        self.freq = None
        self.days = None

        if kwargs.has_key("jail") and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " %s" % self.jail

        if kwargs.has_key("action") and kwargs["action"] is not None:
            self.action = kwargs["action"]
            self.args += " %s" % self.action

        if kwargs.has_key("freq") and kwargs["freq"] is not None:
            self.freq = kwargs["freq"]
            self.args += " %s" % self.freq

        if kwargs.has_key("days") and kwargs["days"] is not None:
            self.days = kwargs["days"]
            self.args += " %s" % self.days

        super(warden_zfscronsnap, self).__init__(WARDEN_ZFSCRONSNAP, 
            WARDEN_ZFSCRONSNAP_FLAGS, flags, **kwargs)


class warden_zfsrevertsnap(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None
        self.snap = None

        if kwargs.has_key("jail") and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " %s" % self.jail

        if kwargs.has_key("snap") and kwargs["snap"] is not None:
            self.snap = kwargs["snap"]
            self.args += " %s" % self.snap

        super(warden_zfsrevertsnap, self).__init__(WARDEN_ZFSREVERTSNAP, 
            WARDEN_ZFSREVERTSNAP_FLAGS, flags, **kwargs)


class warden_zfsrmclone(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None
        self.clone = None

        if kwargs.has_key("jail") and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " %s" % self.jail

        if kwargs.has_key("clone") and kwargs["clone"] is not None:
            self.clone = kwargs["clone"]
            self.args += " %s" % self.clone

        super(warden_zfsrmclone, self).__init__(WARDEN_ZFSRMCLONE, 
            WARDEN_ZFSRMCLONE_FLAGS, flags, **kwargs)


class warden_zfsrmsnap(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None
        self.snap = None

        if kwargs.has_key("jail") and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " %s" % self.jail

        if kwargs.has_key("snap") and kwargs["snap"] is not None:
            self.snap = kwargs["snap"]
            self.args += " %s" % self.snap

        super(warden_zfsrmsnap, self).__init__(WARDEN_ZFSRMSNAP, 
            WARDEN_ZFSRMSNAP, flags, **kwargs)


class Warden(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.flags = flags
        self.obj = None
        self.out = ""
        self.returncode = 0

    def __call(self, obj):
        if obj is not None:
            tmp = obj.run()
            if tmp is not None and len(tmp) > 1:
                if hasattr(obj, "parse"):
                    return obj.parse(tmp)
                self.obj = obj
                self.returncode = tmp[0]
                self.out = tmp[1]
                return self.out

        return None

    def auto(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_auto(flags, **kwargs))

    def checkup(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_checkup(flags, **kwargs))

    def chroot(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_chroot(flags, **kwargs))

    def create(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_create(flags, **kwargs))

    def details(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_details(flags, **kwargs))

    def delete(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_delete(flags, **kwargs))

    def export(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_export(flags, **kwargs))

    def get(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_get(flags, **kwargs))

    def list(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_list(flags, **kwargs))

    def pkgs(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_pkgs(flags, **kwargs))

    def pbis(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_pbis(flags, **kwargs))

    def set(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_set(flags, **kwargs))

    def start(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_start(flags, **kwargs))

    def stop(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_stop(flags, **kwargs))

    def type(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_type(flags, **kwargs))

    def zfsmksnap(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_zfsmksnap(flags, **kwargs))

    def zfslistclone(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_zfslistclone(flags, **kwargs))

    def zfslistsnap(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_zfslistsnap(flags, **kwargs))

    def zfsclonesnap(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_zfsclonesnap(flags, **kwargs))

    def zfscronsnap(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_zfscronsnap(flags, **kwargs))

    def zfsrevertsnap(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_zfsrevertsnap(flags, **kwargs))

    def zfsrmclone(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_zfsrmclone(flags, **kwargs))

    def zfsrmsnap(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_zfsrmsnap(flags, **kwargs))
