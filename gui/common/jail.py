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
import json
import logging

log = logging.getLogger('common.jail')

from freenasUI.common.cmd import cmd_arg, cmd_pipe


class jail_arg(cmd_arg):
    pass


class jail_pipe(cmd_pipe):
    pass


class jail_exception(Exception):
    pass


JAIL_PATH = "/usr/sbin/jail"

JEXEC_PATH = "/usr/sbin/jexec"
JEXEC_FLAGS_NONE = jail_arg(0x00000000, None)
JEXEC_FLAGS_HOST_USERNAME = jail_arg(0x00000001, "-u", True, "host_username")
JEXEC_FLAGS_JAIL_USERNAME = jail_arg(0x00000002, "-U", True, "jail_username")
JEXEC_FLAGS = [
    JEXEC_FLAGS_HOST_USERNAME,
    JEXEC_FLAGS_JAIL_USERNAME
]

JLS_PATH = "/usr/sbin/jls"
JLS_FLAGS_NONE = jail_arg(0x00000000, None)
JLS_FLAGS_LIST_DYING = jail_arg(0x00000001, "-j")
JLS_FLAGS_PRINT_HEADER = jail_arg(0x00000002, "-h")
JLS_FLAGS_PRINT_PARAMETERS = jail_arg(0x00000004, "-n")
JLS_FLAGS_QUOTE = jail_arg(0x00000008, "-q")
JLS_FLAGS_JAIL_PARAMETERS = jail_arg(0x00000010, "-s")
JLS_FLAGS_SUMMARY = jail_arg(0x00000020, "-v")
JLS_FLAGS_JID = jail_arg(0x00000040, "-j", True, "jid")
JLS_FLAGS_JSON = jail_arg(0x00000080, "--libxo=json")
JLS_FLAGS = [
    JLS_FLAGS_LIST_DYING,
    JLS_FLAGS_PRINT_HEADER,
    JLS_FLAGS_PRINT_PARAMETERS,
    JLS_FLAGS_QUOTE,
    JLS_FLAGS_JAIL_PARAMETERS,
    JLS_FLAGS_SUMMARY,
    JLS_FLAGS_JID,
    JLS_FLAGS_JSON,
]


class Jail_bait(object):
    def __init__(self, path, objflags, flags=JEXEC_FLAGS_NONE, **kwargs):
        log.debug("Jail_bait.__init__: enter")
        log.debug("Jail_bait.__init__: path = %s", path)
        log.debug("Jail_bait.__init__: flags = 0x%08x", flags + 0)

        self.path = path
        self.flags = flags
        self.args = ""
        self.pipeopen_kwargs = kwargs.get('pipeopen_kwargs') or {}

        if objflags is None:
            objflags = []

        for obj in objflags:
            if self.flags & obj:
                if (
                    obj.arg is True and obj.argname is not None and
                    obj.argname in kwargs and kwargs[obj.argname] is not None
                ):
                    self.args += " %s %s" % (obj, kwargs[obj.argname])

                elif obj.arg is False:
                    self.args += " %s" % obj

        log.debug("Jail_bait.__init__: args = %s", self.args)

        self.pipe_func = None
        if "pipe_func" in kwargs and kwargs["pipe_func"] is not None:
            self.pipe_func = kwargs["pipe_func"]

        log.debug("Jail_bait.__init__: leave")

    def run(self):
        log.debug("Jail_bait.run: enter")

        cmd = self.path
        if self.args is not None:
            cmd += " %s" % self.args

        log.debug("Jail_bait.cmd = %s", cmd)
        pobj = jail_pipe(cmd, self.pipe_func, pipeopen_kwargs=self.pipeopen_kwargs)
        self.error = pobj.error

        log.debug("Jail_bait.run: leave")
        return (pobj.returncode, str(pobj))


class Jexec(Jail_bait):
    def __init__(self, flags=JEXEC_FLAGS_NONE, **kwargs):
        log.debug("Jexec.__init__: enter")

        super(Jexec, self).__init__(JEXEC_PATH, JEXEC_FLAGS, flags, **kwargs)

        self.jid = None
        if "jid" in kwargs and kwargs["jid"] is not None:
            self.jid = int(kwargs["jid"])
            self.args += " %s" % str(self.jid)

        if "command" in kwargs and kwargs["command"] is not None:
            self.args += " %s" % kwargs["command"]

        log.debug("Jexec.__init__: leave")


class JailObject(object):
    def __init__(self, **kwargs):
        self.jid = -1
        self.ip = None
        self.hostname = None
        self.path = None

        for key in kwargs:
            if key in ('jid', 'ip', 'hostname', 'path'):
                if key == 'jid':
                    self.jid = int(kwargs[key])
                else:
                    self.__dict__[key] = kwargs[key]


class Jls(Jail_bait):
    def __init__(self, flags=JLS_FLAGS_JSON, **kwargs):
        log.debug("Jls.__init__: enter")

        super(Jls, self).__init__(JLS_PATH, JLS_FLAGS, flags, **kwargs)
        self.__jails = []

        if "parameter" in kwargs and kwargs["parameter"] is not None:
            self.args += " %s" % kwargs["parameter"]
        else:
            for i in range(0, 1024):
                if "parameter%d" % i in kwargs and kwargs["parameter%d" % i] is not None:
                    self.args += " %s" % kwargs["parameter%d" % i]

        self._load()
        log.debug("Jls.__init__: leave")

    def _load(self):
        out = super(Jls, self).run()
        code = out[0]
        if code == 0:
            out = out[1]
            jails = json.loads(out)['jail-information']['jail']
            for jail in jails:
                self.__jails.append(JailObject(
                    jid=jail['jid'],
                    ip=jail['ipv4'],
                    hostname=jail['hostname'],
                    path=jail['path'],
                ))

    def __len__(self):
        return len(self.__jails)

    def __iter__(self):
        for j in self.__jails:
            yield j
