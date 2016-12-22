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
import string

from django.core.cache import cache

log = logging.getLogger('common.warden')

#
# Python bindings for the PC-BSD warden
#
WARDEN = "/usr/local/bin/warden"
WARDENCONF = "/usr/local/etc/warden.conf"

from freenasUI.common.cmd import cmd_arg, cmd_pipe
from freenasUI.common.jail import JEXEC_PATH
from freenasUI.common.pipesubr import pipeopen


class warden_arg(cmd_arg):
    pass


class warden_pipe(cmd_pipe):
    pass


class warden_exception(Exception):
    pass


#
# Warden dict keys
#
WARDEN_KEY_ID = "id"
WARDEN_KEY_HOST = "host"
WARDEN_KEY_IP4 = "ipv4"
WARDEN_KEY_ALIASIP4 = "alias_ipv4"
WARDEN_KEY_BRIDGEIP4 = "bridge_ipv4"
WARDEN_KEY_ALIASBRIDGEIP4 = "alias_bridge_ipv4"
WARDEN_KEY_DEFAULTROUTER4 = "defaultrouter_ipv4"
WARDEN_KEY_IP6 = "ipv6"
WARDEN_KEY_ALIASIP6 = "alias_ipv6"
WARDEN_KEY_BRIDGEIP6 = "bridge_ipv6"
WARDEN_KEY_ALIASBRIDGEIP6 = "alias_bridge_ipv6"
WARDEN_KEY_DEFAULTROUTER6 = "defaultrouter_ipv6"
WARDEN_KEY_AUTOSTART = "autostart"
WARDEN_KEY_VNET = "vnet"
WARDEN_KEY_NAT = "nat"
WARDEN_KEY_MAC = "mac"
WARDEN_KEY_STATUS = "status"
WARDEN_KEY_TYPE = "type"
WARDEN_KEY_FLAGS = "flags"
WARDEN_KEY_IFACE = "iface"

#
# Warden template dict keys
#
WARDEN_TKEY_NICK = "nick"
WARDEN_TKEY_TYPE = "type"
WARDEN_TKEY_VERSION = "version"
WARDEN_TKEY_ARCH = "arch"
WARDEN_TKEY_INSTANCES = "instances"

#
# Warden jail status
#
WARDEN_STATUS_RUNNING = "Running"
WARDEN_STATUS_STOPPED = "Stopped"

#
# Warden jail type
#
WARDEN_TYPE_STANDARD = "standard"
WARDEN_TYPE_PLUGINJAIL = "pluginjail"
WARDEN_TYPE_PORTJAIL = "portjail"
WARDEN_TYPE_LINUXJAIL = "linuxjail"

#
# Warden jail autostart
#
WARDEN_AUTOSTART_ENABLED = "Enabled"
WARDEN_AUTOSTART_DISABLED = "Disabled"

#
# Warden jail vnet
#
WARDEN_VNET_ENABLED = "Enabled"
WARDEN_VNET_DISABLED = "Disabled"

#
# Warden jail nat
#
WARDEN_NAT_ENABLED = "Enabled"
WARDEN_NAT_DISABLED = "Disabled"

#
# extract-tarball status file
#
WARDEN_EXTRACT_STATUS_FILE = "/var/tmp/status"


WARDEN_FLAGS_NONE = warden_arg(0x00000000, None)

WARDEN_AUTO = "auto"
WARDEN_AUTO_FLAGS = []

WARDEN_BSPKGNG = "bspkgng"
WARDEN_BSPKGNG_FLAGS = []

WARDEN_CHECKUP = "checkup"
WARDEN_CHECKUP_FLAGS_ALL = warden_arg(0x00000001, "all")
WARDEN_CHECKUP_FLAGS = [
    WARDEN_CHECKUP_FLAGS_ALL
]

WARDEN_CHROOT = "chroot"
WARDEN_CHROOT_FLAGS = []

WARDEN_CREATE = "create"
WARDEN_CREATE_FLAGS_32BIT = warden_arg(0x00000001, "-32")
WARDEN_CREATE_FLAGS_IPV4 = warden_arg(0x00000002, "--ipv4", True, "ipv4")
WARDEN_CREATE_FLAGS_IPV6 = warden_arg(0x00000004, "--ipv6", True, "ipv6")
WARDEN_CREATE_FLAGS_SRC = warden_arg(0x00000008, "--src")
WARDEN_CREATE_FLAGS_PORTS = warden_arg(0x00000010, "--ports")
WARDEN_CREATE_FLAGS_VANILLA = warden_arg(0x00000020, "--vanilla")
WARDEN_CREATE_FLAGS_STARTAUTO = warden_arg(0x00000040, "--startauto")
WARDEN_CREATE_FLAGS_JAILTYPE = warden_arg(0x00000080, "--jailtype", True, "jailtype")
WARDEN_CREATE_FLAGS_LINUXJAIL = warden_arg(0x00000100, "--linuxjail", True, "script")
WARDEN_CREATE_FLAGS_ARCHIVE = warden_arg(0x00000200, "--archive", True, "archive")
WARDEN_CREATE_FLAGS_LINUXARCHIVE = warden_arg(0x00000400, "--linuxarchive", True, "linuxarchive")
WARDEN_CREATE_FLAGS_VERSION = warden_arg(0x00000800, "--version", True, "version")
WARDEN_CREATE_FLAGS_TEMPLATE = warden_arg(0x00001000, "--template", True, "template")
WARDEN_CREATE_FLAGS_SYSLOG = warden_arg(0x00002000, "--syslog")
WARDEN_CREATE_FLAGS_LOGFILE = warden_arg(0x00004000, "--logfile", True, "logfile")
WARDEN_CREATE_FLAGS = [
    WARDEN_CREATE_FLAGS_32BIT,
    WARDEN_CREATE_FLAGS_IPV4,
    WARDEN_CREATE_FLAGS_IPV6,
    WARDEN_CREATE_FLAGS_SRC,
    WARDEN_CREATE_FLAGS_PORTS,
    WARDEN_CREATE_FLAGS_VANILLA,
    WARDEN_CREATE_FLAGS_STARTAUTO,
    WARDEN_CREATE_FLAGS_JAILTYPE,
    WARDEN_CREATE_FLAGS_LINUXJAIL,
    WARDEN_CREATE_FLAGS_ARCHIVE,
    WARDEN_CREATE_FLAGS_LINUXARCHIVE,
    WARDEN_CREATE_FLAGS_VERSION,
    WARDEN_CREATE_FLAGS_TEMPLATE,
    WARDEN_CREATE_FLAGS_SYSLOG,
    WARDEN_CREATE_FLAGS_LOGFILE
]

WARDEN_DETAILS = "details"
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
WARDEN_GET_FLAGS_IPV4 = warden_arg(0x00000001, "ipv4")
WARDEN_GET_FLAGS_IPV6 = warden_arg(0x00000002, "ipv6")
WARDEN_GET_FLAGS_ALIAS_IPV4 = warden_arg(0x00000004, "alias-ipv4")
WARDEN_GET_FLAGS_ALIAS_IPV6 = warden_arg(0x00000008, "alias-ipv6")
WARDEN_GET_FLAGS_BRIDGE_IPV4 = warden_arg(0x00000010, "bridge-ipv4")
WARDEN_GET_FLAGS_BRIDGE_IPV6 = warden_arg(0x00000020, "bridge-ipv6")
WARDEN_GET_FLAGS_ALIAS_BRIDGE_IPV4 = warden_arg(0x00000040, "alias-bridge-ipv4")
WARDEN_GET_FLAGS_ALIAS_BRIDGE_IPV6 = warden_arg(0x00000080, "alias-bridge-ipv6")
WARDEN_GET_FLAGS_DEFAULTROUTER_IPV4 = warden_arg(0x00000100, "defaultrouter-ipv4")
WARDEN_GET_FLAGS_DEFAULTROUTER_IPV6 = warden_arg(0x00000200, "defaultrouter-ipv6")
WARDEN_GET_FLAGS_FLAGS = warden_arg(0x00000400, "flags")
WARDEN_GET_FLAGS_VNET = warden_arg(0x00000800, "vnet")
WARDEN_GET_FLAGS_NAT = warden_arg(0x00001000, "nat")
WARDEN_GET_FLAGS_MAC = warden_arg(0x00002000, "mac")
WARDEN_GET_FLAGS_IFACE = warden_arg(0x00004000, "iface")
WARDEN_GET_FLAGS = [
    WARDEN_GET_FLAGS_IPV4,
    WARDEN_GET_FLAGS_IPV6,
    WARDEN_GET_FLAGS_ALIAS_IPV4,
    WARDEN_GET_FLAGS_ALIAS_IPV6,
    WARDEN_GET_FLAGS_BRIDGE_IPV4,
    WARDEN_GET_FLAGS_BRIDGE_IPV6,
    WARDEN_GET_FLAGS_ALIAS_BRIDGE_IPV4,
    WARDEN_GET_FLAGS_ALIAS_BRIDGE_IPV6,
    WARDEN_GET_FLAGS_DEFAULTROUTER_IPV4,
    WARDEN_GET_FLAGS_DEFAULTROUTER_IPV6,
    WARDEN_GET_FLAGS_FLAGS,
    WARDEN_GET_FLAGS_VNET,
    WARDEN_GET_FLAGS_NAT,
    WARDEN_GET_FLAGS_MAC,
    WARDEN_GET_FLAGS_IFACE
]

WARDEN_IMPORT = "import"
WARDEN_IMPORT_FLAGS_IPV4 = warden_arg(0x00000001, "--ipv4", True, "ipv4")
WARDEN_IMPORT_FLAGS_IPV6 = warden_arg(0x00000002, "--ipv6", True, "ipv6")
WARDEN_IMPORT_FLAGS_HOST = warden_arg(0x00000004, "--host", True, "host")
WARDEN_IMPORT_FLAGS = [
    WARDEN_IMPORT_FLAGS_IPV4,
    WARDEN_IMPORT_FLAGS_IPV6,
    WARDEN_IMPORT_FLAGS_HOST
]

WARDEN_LIST = "list"
WARDEN_LIST_FLAGS_VERBOSE = warden_arg(0x00000001, "-v")
WARDEN_LIST_FLAGS = [
    WARDEN_LIST_FLAGS_VERBOSE
]

WARDEN_PKGS = "pkgs"
WARDEN_PKGS_FLAGS = []

WARDEN_PBIS = "pbis"
WARDEN_PBIS_FLAGS = []

WARDEN_SET = "set"
WARDEN_SET_FLAGS_IPV4 = warden_arg(0x00000001, "ipv4", True, "ipv4")
WARDEN_SET_FLAGS_IPV6 = warden_arg(0x00000002, "ipv6", True, "ipv6")
WARDEN_SET_FLAGS_ALIAS_IPV4 = warden_arg(0x00000004, "alias-ipv4", True, "alias-ipv4")
WARDEN_SET_FLAGS_ALIAS_IPV6 = warden_arg(0x00000008, "alias-ipv6", True, "alias-ipv6")
WARDEN_SET_FLAGS_BRIDGE_IPV4 = warden_arg(0x00000010, "bridge-ipv4", True, "bridge-ipv4",)
WARDEN_SET_FLAGS_BRIDGE_IPV6 = warden_arg(0x00000020, "bridge-ipv6", True, "bridge-ipv6")
WARDEN_SET_FLAGS_ALIAS_BRIDGE_IPV4 = warden_arg(0x00000040, "alias-bridge-ipv4", True, "alias-bridge-ipv4")
WARDEN_SET_FLAGS_ALIAS_BRIDGE_IPV6 = warden_arg(0x00000080, "alias-bridge-ipv6", True, "alias-bridge-ipv6")
WARDEN_SET_FLAGS_DEFAULTROUTER_IPV4 = warden_arg(0x00000100, "defaultrouter-ipv4", True, "defaultrouter-ipv4")
WARDEN_SET_FLAGS_DEFAULTROUTER_IPV6 = warden_arg(0x00000200, "defaultrouter-ipv6", True, "defaultrouter-ipv6")
WARDEN_SET_FLAGS_FLAGS = warden_arg(0x00000400, "flags", True, "jflags")
WARDEN_SET_FLAGS_VNET_ENABLE = warden_arg(0x00000800, "vnet-enable")
WARDEN_SET_FLAGS_VNET_DISABLE = warden_arg(0x00001000, "vnet-disable")
WARDEN_SET_FLAGS_NAT_ENABLE = warden_arg(0x00002000, "nat-enable")
WARDEN_SET_FLAGS_NAT_DISABLE = warden_arg(0x00004000, "nat-disable")
WARDEN_SET_FLAGS_MAC = warden_arg(0x00008000, "mac", True, "mac")
WARDEN_SET_FLAGS_IFACE = warden_arg(0x00010000, "iface", True, "iface")
WARDEN_SET_FLAGS = [
    WARDEN_SET_FLAGS_IPV4,
    WARDEN_SET_FLAGS_IPV6,
    WARDEN_SET_FLAGS_ALIAS_IPV4,
    WARDEN_SET_FLAGS_ALIAS_IPV6,
    WARDEN_SET_FLAGS_BRIDGE_IPV4,
    WARDEN_SET_FLAGS_BRIDGE_IPV6,
    WARDEN_SET_FLAGS_ALIAS_BRIDGE_IPV4,
    WARDEN_SET_FLAGS_ALIAS_BRIDGE_IPV6,
    WARDEN_SET_FLAGS_DEFAULTROUTER_IPV4,
    WARDEN_SET_FLAGS_DEFAULTROUTER_IPV6,
    WARDEN_SET_FLAGS_FLAGS,
    WARDEN_SET_FLAGS_VNET_ENABLE,
    WARDEN_SET_FLAGS_VNET_DISABLE,
    WARDEN_SET_FLAGS_NAT_ENABLE,
    WARDEN_SET_FLAGS_NAT_DISABLE,
    WARDEN_SET_FLAGS_MAC,
    WARDEN_SET_FLAGS_IFACE
]

WARDEN_START = "start"
WARDEN_START_FLAGS = []

WARDEN_STOP = "stop"
WARDEN_STOP_FLAGS = []

WARDEN_TYPE = "type"
WARDEN_TYPE_FLAGS_PORTJAIL = warden_arg(0x00000001, WARDEN_TYPE_PORTJAIL)
WARDEN_TYPE_FLAGS_PLUGINJAIL = warden_arg(0x00000002, WARDEN_TYPE_PLUGINJAIL)
WARDEN_TYPE_FLAGS_STANARD = warden_arg(0x00000004, WARDEN_TYPE_STANDARD)

WARDEN_TYPE_FLAGS = [
    WARDEN_TYPE_FLAGS_PORTJAIL,
    WARDEN_TYPE_FLAGS_PLUGINJAIL,
    WARDEN_TYPE_FLAGS_STANARD
]

WARDEN_TEMPLATE = "template"
WARDEN_TEMPLATE_FLAGS_CREATE = warden_arg(0x00000001, "create")
WARDEN_TEMPLATE_FLAGS_DELETE = warden_arg(0x00000002, "delete")
WARDEN_TEMPLATE_FLAGS_LIST = warden_arg(0x00000004, "list")
WARDEN_TEMPLATE_FLAGS = [
    WARDEN_TEMPLATE_FLAGS_CREATE,
    WARDEN_TEMPLATE_FLAGS_DELETE,
    WARDEN_TEMPLATE_FLAGS_LIST
]

WARDEN_TEMPLATE_CREATE = "create"
WARDEN_TEMPLATE_CREATE_FLAGS_FBSD = warden_arg(0x00000010, "-fbsd", True, "fbsd")
WARDEN_TEMPLATE_CREATE_FLAGS_TRUEOS = warden_arg(0x00000020, "-trueos", True, "trueos")
WARDEN_TEMPLATE_CREATE_FLAGS_ARCH = warden_arg(0x00000040, "-arch", True, "arch")
WARDEN_TEMPLATE_CREATE_FLAGS_TAR = warden_arg(0x00000080, "-tar", True, "tar")
WARDEN_TEMPLATE_CREATE_FLAGS_NICK = warden_arg(0x00000100, "-nick", True, "nick")
WARDEN_TEMPLATE_CREATE_FLAGS_LINUX = warden_arg(0x00000200, "-linuxjail", False)
WARDEN_TEMPLATE_CREATE_FLAGS_MTREE = warden_arg(0x00000400, "-mtree", True, "mtree")
WARDEN_TEMPLATE_CREATE_FLAGS = [
    WARDEN_TEMPLATE_CREATE_FLAGS_FBSD,
    WARDEN_TEMPLATE_CREATE_FLAGS_TRUEOS,
    WARDEN_TEMPLATE_CREATE_FLAGS_ARCH,
    WARDEN_TEMPLATE_CREATE_FLAGS_TAR,
    WARDEN_TEMPLATE_CREATE_FLAGS_NICK,
    WARDEN_TEMPLATE_CREATE_FLAGS_LINUX,
    WARDEN_TEMPLATE_CREATE_FLAGS_MTREE
]

WARDEN_TEMPLATE_DELETE = "delete"
WARDEN_TEMPLATE_DELETE_FLAGS = []

WARDEN_TEMPLATE_LIST = "list"
WARDEN_TEMPLATE_LIST_FLAGS_VERBOSE = warden_arg(0x00000001, "-v", False)
WARDEN_TEMPLATE_LIST_FLAGS = [
    WARDEN_TEMPLATE_LIST_FLAGS_VERBOSE
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


class WardenJail(object):
    def __init__(self, **kwargs):
        self.id = kwargs.get(WARDEN_KEY_ID)
        self.host = kwargs.get(WARDEN_KEY_HOST)
        self.ipv4 = kwargs.get(WARDEN_KEY_IP4)
        self.alias_ipv4 = kwargs.get(WARDEN_KEY_ALIASIP4)
        self.bridge_ipv4 = kwargs.get(WARDEN_KEY_BRIDGEIP4)
        self.alias_bridge_ipv4 = kwargs.get(WARDEN_KEY_ALIASBRIDGEIP4)
        self.defaultrouter_ipv4 = kwargs.get(WARDEN_KEY_DEFAULTROUTER4)
        self.ipv6 = kwargs.get(WARDEN_KEY_IP6)
        self.alias_ipv6 = kwargs.get(WARDEN_KEY_ALIASIP6)
        self.bridge_ipv6 = kwargs.get(WARDEN_KEY_BRIDGEIP6)
        self.alias_bridge_ipv6 = kwargs.get(WARDEN_KEY_ALIASBRIDGEIP6)
        self.defaultrouter_ipv6 = kwargs.get(WARDEN_KEY_DEFAULTROUTER6)
        self.autostart = kwargs.get(WARDEN_KEY_AUTOSTART)
        self.vnet = kwargs.get(WARDEN_KEY_VNET)
        self.nat = kwargs.get(WARDEN_KEY_NAT)
        self.mac = kwargs.get(WARDEN_KEY_MAC)
        self.status = kwargs.get(WARDEN_KEY_STATUS)
        self.type = kwargs.get(WARDEN_KEY_TYPE)
        self.flags = kwargs.get(WARDEN_KEY_FLAGS)
        self.iface = kwargs.get(WARDEN_KEY_IFACE)


class WardenTemplate(object):
    def __init__(self, **kwargs):
        self.nick = kwargs.get(WARDEN_TKEY_NICK)
        self.type = kwargs.get(WARDEN_TKEY_TYPE)
        self.version = kwargs.get(WARDEN_TKEY_VERSION)
        self.arch = kwargs.get(WARDEN_TKEY_ARCH)
        self.instances = kwargs.get(WARDEN_TKEY_INSTANCES)


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
        self.release = None

        if not hasattr(self, "jail"):
            self.jail = None
        if not hasattr(self, "args"):
            self.args = ""

        self.readconf()

        if objflags is None:
            objflags = []

        for obj in objflags:
            if self.flags & obj:
                if (
                    obj.arg is True and obj.argname is not None and
                    obj.argname in kwargs and kwargs[obj.argname] is not None
                ):
                    self.args += " %s" % self.ass(obj, kwargs[obj.argname])

                elif obj.arg is False:
                    self.args += " %s" % obj

        log.debug("warden_base.__init__: args = %s", self.args)

        self.pipe_func = None
        if "pipe_func" in kwargs and kwargs["pipe_func"] is not None:
            self.pipe_func = kwargs["pipe_func"]

        log.debug("warden_base.__init__: leave")

    def ass(self, key, val):
        return "%s='%s'" % (key, val)

    def run(self, jail=False, jid=0):
        log.debug("warden_base.run: enter")

        cmd = "%s %s" % (WARDEN, self.cmd)
        if self.args is not None:
            cmd += " %s" % self.args

        if jail is True and jid > 0:
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
        if not os.path.exists(WARDENCONF):
            return
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

            elif line.startswith("FREEBSD_RELEASE:"):
                parts = line.split(':')
                if len(parts) > 1:
                    self.release = parts[1].strip()

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

            elif line.startswith("FREEBSD_RELEASE:"):
                if self.release:
                    line = "FREEBSD_RELEASE: %s" % self.release

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

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail

        super(warden_auto, self).__init__(
            WARDEN_AUTO, WARDEN_AUTO_FLAGS, flags, **kwargs
        )

    def parse(self, thestuff):
        lines = thestuff[1].splitlines()
        for line in lines:
            line = line.strip()
            parts = line.split()
            return parts[0]
        return None


class warden_bspkgng(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail

        super(warden_bspkgng, self).__init__(
            WARDEN_BSPKGNG, WARDEN_BSPKGNG_FLAGS, flags, **kwargs
        )


class warden_checkup(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        if not ("jail" in kwargs and kwargs["jail"] is not None):
            flags |= WARDEN_CHECKUP_FLAGS_ALL

        super(warden_checkup, self).__init__(
            WARDEN_CHECKUP, WARDEN_CHECKUP_FLAGS, flags, **kwargs
        )


class warden_chroot(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail

        super(warden_chroot, self).__init__(
            WARDEN_CHROOT, WARDEN_CHROOT_FLAGS, flags, **kwargs
        )


class warden_create(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.ip = None
        self.jail = None

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail

        super(warden_create, self).__init__(
            WARDEN_CREATE, WARDEN_CREATE_FLAGS, flags, **kwargs
        )

    def ass(self, key, val):
        return "%s '%s'" % (key, val)


class warden_details(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail

        super(warden_details, self).__init__(
            WARDEN_DETAILS, WARDEN_DETAILS_FLAGS, flags, **kwargs
        )


class warden_delete(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail

        super(warden_delete, self).__init__(
            WARDEN_DELETE, WARDEN_DELETE_FLAGS, flags, **kwargs
        )


class warden_export(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail

        super(warden_export, self).__init__(
            WARDEN_EXPORT, WARDEN_EXPORT_FLAGS, flags, **kwargs
        )


class warden_get(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        super(warden_get, self).__init__(WARDEN_GET, WARDEN_GET_FLAGS, flags, **kwargs)

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail


class warden_import(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.file = kwargs["file"]
            self.args += " '%s'" % self.file

        super(warden_export, self).__init__(
            WARDEN_EXPORT, WARDEN_EXPORT_FLAGS, flags, **kwargs
        )


class warden_list(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        super(warden_list, self).__init__(
            WARDEN_LIST, WARDEN_LIST_FLAGS,
            flags | WARDEN_LIST_FLAGS_VERBOSE, **kwargs
        )

    def parse(self, thestuff):
        themap = {
            'id': WARDEN_KEY_ID,
            'host': WARDEN_KEY_HOST,
            'ipv4': WARDEN_KEY_IP4,
            'alias-ipv4': WARDEN_KEY_ALIASIP4,
            'bridge-ipv4': WARDEN_KEY_BRIDGEIP4,
            'alias-bridge-ipv4': WARDEN_KEY_ALIASBRIDGEIP4,
            'defaultrouter-ipv4': WARDEN_KEY_DEFAULTROUTER4,
            'ipv6': WARDEN_KEY_IP6,
            'alias-ipv6': WARDEN_KEY_ALIASIP6,
            'bridge-ipv6': WARDEN_KEY_BRIDGEIP6,
            'alias-bridge-ipv6': WARDEN_KEY_ALIASBRIDGEIP6,
            'defaultrouter-ipv6': WARDEN_KEY_DEFAULTROUTER6,
            'autostart': WARDEN_KEY_AUTOSTART,
            'vnet': WARDEN_KEY_VNET,
            'nat': WARDEN_KEY_NAT,
            'mac': WARDEN_KEY_MAC,
            'status': WARDEN_KEY_STATUS,
            'type': WARDEN_KEY_TYPE,
            'flags': WARDEN_KEY_FLAGS,
            'iface': WARDEN_KEY_IFACE
        }

        lines = thestuff[1].splitlines()

        jail = {}
        jails = []
        for line in lines:
            for k in themap:
                if line.startswith(k + ':'):
                    parts = line.split(':')
                    if k == 'id':
                        if jail:
                            jails.append(jail)
                        jail = {WARDEN_KEY_ID: parts[1].strip()}
                    else:
                        val = None
                        parts = line.split()
                        if len(parts) > 1:
                            val = string.join(parts[1:], ' ').strip()
                        jail[themap[k]] = val
        if jail:
            jails.append(jail)
        return jails


class warden_pkgs(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail

        super(warden_pkgs, self).__init__(
            WARDEN_PKGS, WARDEN_PKGS_FLAGS, flags, **kwargs
        )


class warden_pbis(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail

        super(warden_pbis, self).__init__(
            WARDEN_PBIS, WARDEN_PBIS_FLAGS, flags, **kwargs
        )


class warden_set(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        saved_flags = flags

        for wsf in WARDEN_SET_FLAGS:
            if flags & wsf:
                flags &= ~wsf

                if wsf in (
                    WARDEN_SET_FLAGS_VNET_ENABLE,
                    WARDEN_SET_FLAGS_VNET_DISABLE,
                    WARDEN_SET_FLAGS_NAT_ENABLE,
                    WARDEN_SET_FLAGS_NAT_DISABLE
                ):
                    self.args = wsf.string
                    break

                elif wsf.argname in kwargs and kwargs[wsf.argname] is not None:
                    self.args = wsf.string
                    break

        super(warden_set, self).__init__(WARDEN_SET, WARDEN_SET_FLAGS, flags, **kwargs)
        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail

        for wsf in WARDEN_SET_FLAGS:
            if saved_flags & wsf:
                if wsf.argname in kwargs and kwargs[wsf.argname] is not None:
                    self.args += " %s" % kwargs[wsf.argname]
                    break


class warden_start(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail

        super(warden_start, self).__init__(
            WARDEN_START, WARDEN_START_FLAGS, flags, **kwargs
        )


class warden_stop(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail

        super(warden_stop, self).__init__(
            WARDEN_STOP, WARDEN_STOP_FLAGS, flags, **kwargs
        )


class warden_type(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail

        super(warden_type, self).__init__(
            WARDEN_TYPE, WARDEN_TYPE_FLAGS, flags, **kwargs
        )


class warden_template(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        type = None
        tflags = None

        if flags & WARDEN_TEMPLATE_FLAGS_CREATE:
            type = WARDEN_TEMPLATE_CREATE
            tflags = WARDEN_TEMPLATE_CREATE_FLAGS
        elif flags & WARDEN_TEMPLATE_FLAGS_DELETE:
            type = WARDEN_TEMPLATE_DELETE
            tflags = WARDEN_TEMPLATE_DELETE_FLAGS
        elif flags & WARDEN_TEMPLATE_FLAGS_LIST:
            type = WARDEN_TEMPLATE_LIST
            tflags = WARDEN_TEMPLATE_LIST_FLAGS

        if "template" in kwargs and kwargs["template"] is not None:
            self.args += " '%s'" % kwargs['template']

        cmd = "%s %s" % (WARDEN_TEMPLATE, type)
        super(warden_template, self).__init__(
            cmd, tflags, flags | WARDEN_TEMPLATE_LIST_FLAGS_VERBOSE, **kwargs
        )

    def ass(self, key, val):
        return "%s '%s'" % (key, val)

    def parse(self, thestuff):
        themap = {
            'nick': WARDEN_TKEY_NICK,
            'type': WARDEN_TKEY_TYPE,
            'version': WARDEN_TKEY_VERSION,
            'arch': WARDEN_TKEY_ARCH,
            'instances': WARDEN_TKEY_INSTANCES
        }

        lines = thestuff[1].splitlines()

        template = {}
        templates = []
        for line in lines:
            for k in themap:
                if line.startswith(k + ':'):
                    parts = line.split(':')
                    if k == 'nick':
                        if template:
                            templates.append(template)
                        template = {WARDEN_TKEY_NICK: parts[1].strip()}
                    else:
                        val = None
                        parts = line.split()
                        if len(parts) > 1:
                            val = string.join(parts[1:], ' ').strip()
                        template[themap[k]] = val
        if template:
            templates.append(template)
        return templates


class warden_zfsmksnap(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail

        super(warden_zfsmksnap, self).__init__(
            WARDEN_ZFSMKSNAP, WARDEN_ZFSMKSNAP_FLAGS, flags, **kwargs
        )


class warden_zfslistclone(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail

        super(warden_zfslistclone, self).__init__(
            WARDEN_ZFSLISTCLONE, WARDEN_ZFSLISTCLONE_FLAGS, flags, **kwargs
        )


class warden_zfslistsnap(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail

        super(warden_zfslistsnap, self).__init__(
            WARDEN_ZFSLISTSNAP, WARDEN_ZFSLISTSNAP_FLAGS, flags, **kwargs
        )


class warden_zfsclonesnap(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None
        self.snap = None

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail

        if "snap" in kwargs and kwargs["snap"] is not None:
            self.snap = kwargs["snap"]
            self.args += " '%s'" % self.snap

        super(warden_zfsclonesnap, self).__init__(
            WARDEN_ZFSCLONESNAP, WARDEN_ZFSCLONESNAP_FLAGS, flags, **kwargs
        )


class warden_zfscronsnap(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None
        self.action = None
        self.freq = None
        self.days = None

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail

        if "action" in kwargs and kwargs["action"] is not None:
            self.action = kwargs["action"]
            self.args += " '%s'" % self.action

        if "freq" in kwargs and kwargs["freq"] is not None:
            self.freq = kwargs["freq"]
            self.args += " '%s'" % self.freq

        if "days" in kwargs and kwargs["days"] is not None:
            self.days = kwargs["days"]
            self.args += " '%s'" % self.days

        super(warden_zfscronsnap, self).__init__(
            WARDEN_ZFSCRONSNAP, WARDEN_ZFSCRONSNAP_FLAGS, flags, **kwargs
        )


class warden_zfsrevertsnap(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None
        self.snap = None

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail

        if "snap" in kwargs and kwargs["snap"] is not None:
            self.snap = kwargs["snap"]
            self.args += " '%s'" % self.snap

        super(warden_zfsrevertsnap, self).__init__(
            WARDEN_ZFSREVERTSNAP, WARDEN_ZFSREVERTSNAP_FLAGS, flags, **kwargs
        )


class warden_zfsrmclone(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None
        self.clone = None

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail

        if "clone" in kwargs and kwargs["clone"] is not None:
            self.clone = kwargs["clone"]
            self.args += " '%s'" % self.clone

        super(warden_zfsrmclone, self).__init__(
            WARDEN_ZFSRMCLONE, WARDEN_ZFSRMCLONE_FLAGS, flags, **kwargs
        )


class warden_zfsrmsnap(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.args = ""
        self.jail = None
        self.snap = None

        if "jail" in kwargs and kwargs["jail"] is not None:
            self.jail = kwargs["jail"]
            self.args += " '%s'" % self.jail

        if "snap" in kwargs and kwargs["snap"] is not None:
            self.snap = kwargs["snap"]
            self.args += " '%s'" % self.snap

        super(warden_zfsrmsnap, self).__init__(
            WARDEN_ZFSRMSNAP, WARDEN_ZFSRMSNAP, flags, **kwargs
        )


class Warden(warden_base):
    def __init__(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        self.flags = flags
        self.obj = None
        self.out = ""
        self.returncode = 0
        self._logfile = None
        self._syslog = False

    @property
    def logfile(self):
        return self._logfile

    @logfile.setter
    def logfile(self, val=None):
        if val:
            self._logfile = val
            os.environ["WARDEN_LOGFILE"] = val
        else:
            del os.environ["WARDEN_LOGFILE"]

    @property
    def syslog(self):
        return self._syslog

    @syslog.setter
    def syslog(self, val=None):
        if val:
            self._syslog = True
            os.environ["WARDEN_USESYSLOG"] = "TRUE"
        else:
            del os.environ["WARDEN_USESYSLOG"]

    def __call(self, obj):
        if obj is not None:
            tmp = None
            try:
                tmp = obj.run()
            except Exception as e:
                log.debug("Warden.__call: Failed with '%s'", e)
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

    def bspkgng(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_bspkgng(flags, **kwargs))

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

    def cached_list(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        wlistcached = cache.get('wardenList')

        if wlistcached is None:
                wlistcached = self.__call(warden_list(flags, **kwargs)) or []
                cache.set('wardenList', wlistcached, 1)
        else:
                # Reset cache timeout
                cache.set('wardenList', wlistcached, 1)

        return wlistcached

    def pkgs(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_pkgs(flags, **kwargs))

    def pbis(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_pbis(flags, **kwargs))

    def set(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        rv = self.__call(warden_set(flags, **kwargs))
        # Clear cache when config is changed, see #16335
        cache.delete('wardenList')
        return rv

    def start(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_start(flags, **kwargs))

    def stop(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_stop(flags, **kwargs))

    def type(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_type(flags, **kwargs))

    def types(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        types = [
            WARDEN_TYPE_STANDARD,
            WARDEN_TYPE_PORTJAIL,
            WARDEN_TYPE_PLUGINJAIL
        ]
        return types

    def template(self, flags=WARDEN_FLAGS_NONE, **kwargs):
        return self.__call(warden_template(flags, **kwargs))

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

    def getjails(self):
        jail_objects = []
        jails = self.list()
        for j in jails:
            jail_objects.append(WardenJail(**j))
        return jail_objects


def get_warden_template_abi_arch(template_path):
    abi_arch = None

    sysctl_path = "%s/sbin/sysctl" % template_path
    p = pipeopen("file -b '%s'" % sysctl_path, important=False)
    out = p.communicate()
    if p.returncode != 0:
        return None

    try:
        out = out[0]
        parts = out.split(',')
        out = parts[0].split()
        if out[1] == '64-bit':
            abi_arch = 'x64'
        else:
            abi_arch = 'x86'

    except:
        pass

    return abi_arch


def get_warden_template_abi_version(template_path):
    abi_version = None

    sysctl_path = "%s/sbin/sysctl" % template_path
    p = pipeopen("file -b '%s'" % sysctl_path, important=False)
    out = p.communicate()
    if p.returncode != 0:
        return None

    try:
        out = out[0]
        parts = out.split(',')
        out = parts[4].split()
        abi_version = "%s-RELEASE" % out[2]

    except:
        pass

    return abi_version
