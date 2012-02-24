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

class jail_arg(object):
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

JAIL_PATH = "/usr/sbin/jail"

JEXEC_PATH = "/usr/sbin/jexec"
JEXEC_FLAGS_NONE          = jail_arg(0x00000000, None)
JEXEC_FLAGS_HOST_USERNAME = jail_arg(0x00000001, "-u", True, "host_username")
JEXEC_FLAGS_JAIL_USERNAME = jail_arg(0x00000002, "-U", True, "jail_username")
JEXEC_FLAGS = [
    JEXEC_FLAGS_HOST_USERNAME,
    JEXEC_FLAGS_JAIL_USERNAME
]

JLS_PATH = "/usr/sbin/jls"
JLS_FLAGS_NONE             = jail_arg(0x00000000, None)
JLS_FLAGS_LIST_DYING       = jail_arg(0x00000001, "-j")
JLS_FLAGS_PRINT_HEADER     = jail_arg(0x00000002, "-h")
JLS_FLAGS_PRINT_PARAMETERS = jail_arg(0x00000004, "-n")
JLS_FLAGS_QUOTE            = jail_arg(0x00000008, "-q")
JLS_FLAGS_JAIL_PARAMETERS  = jail_arg(0x00000010, "-s")
JLS_FLAGS_SUMMARY          = jail_arg(0x00000020, "-v")
JLS_FLAGS_JID              = jail_arg(0x00000040, "-j", True, "jid")
JLS_FLAGS = [
    JLS_FLAGS_LIST_DYING,
    JLS_FLAGS_PRINT_HEADER,
    JLS_FLAGS_PRINT_PARAMETERS,
    JLS_FLAGS_QUOTE,
    JLS_FLAGS_JAIL_PARAMETERS,
    JLS_FLAGS_SUMMARY,
    JLS_FLAGS_JID
]

class Jail_exception(Exception):
    def __init__(self, msg = None):
        syslog(LOG_DEBUG, "Jail_exception.__init__: enter")
        if msg:
            syslog(LOG_DEBUG, "Jail_exception.__init__: error = %s" % msg)
        syslog(LOG_DEBUG, "Jail_exception.__init__: leave")


class Jail_pipe(object):
    def __init__(self, cmd, func=None, **kwargs):
        syslog(LOG_DEBUG, "Jail_pipe.__init__: enter") 
        syslog(LOG_DEBUG, "Jail_pipe.__init__: cmd = %s" % cmd) 

        self.error = None
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
        syslog(LOG_DEBUG, "Jail_pipe.__init__: out = %s" % self.__out)

        if self.__pipe.returncode != 0:
            self.error = self.__out 

        self.returncode = self.__pipe.returncode
        syslog(LOG_DEBUG, "Jail_pipe.__init__: leave")

    def __str__(self):
        return self.__out

    def __iter__(self):
        lines = self.__out.splitlines()
        for line in lines:
            yield line

class Jail_bait(object):
    def __init__(self, path, objflags, flags=JEXEC_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "Jail_bait.__init__: enter")
        syslog(LOG_DEBUG, "Jail_bait.__init__: path = %s" % path)
        syslog(LOG_DEBUG, "Jail_bait.__init__: flags = 0x%08x" % (flags + 0))

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

        syslog(LOG_DEBUG, "Jail_bait.__init__: args = %s" % self.args)

        self.pipe_func = None
        if kwargs.has_key("pipe_func") and kwargs["pipe_func"] is not None:
            self.pipe_func = kwargs["pipe_func"]

        syslog(LOG_DEBUG, "Jail_bait.__init__: leave")

    def run(self):
        syslog(LOG_DEBUG, "Jail_bait.run: enter")

        cmd = self.path
        if self.args is not None:
            cmd += " %s" % self.args

        syslog(LOG_DEBUG, "Jail_bait.cmd = %s" % cmd)
        pobj = Jail_pipe(cmd, self.pipe_func)
        self.error = pobj.error

        syslog(LOG_DEBUG, "Jail_bait.run: leave")
        return (pobj.returncode, str(pobj))


class Jexec(Jail_bait):
    def __init__(self, flags=JEXEC_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "Jexec.__init__: enter")

        super(Jexec, self).__init__(JEXEC_PATH, JEXEC_FLAGS, flags, **kwargs)

        self.jid = None
        if kwargs.has_key("jid") and kwargs["jid"] is not None:
            self.jid = int(kwargs["jid"])
            self.args += " %s" % str(self.jid)

        if kwargs.has_key("command") and kwargs["command"] is not None:
            self.args += " %s" % kwargs["command"]

        syslog(LOG_DEBUG, "Jexec.__init__: leave")


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
    def __init__(self, flags=JLS_FLAGS_NONE, **kwargs):
        syslog(LOG_DEBUG, "Jls.__init__: enter")

        super(Jls, self).__init__(JLS_PATH, JLS_FLAGS, flags, **kwargs)
        self.__jails = []

        if kwargs.has_key("parameter") and kwargs["parameter"] is not None:
            self.args += " %s" % kwargs["parameter"]
        else:
            for i in range(0, 1024):
                if kwargs.has_key("parameter%d" % i) and kwargs["parameter%d" % i] is not None:
                    self.args += " %s" % kwargs["parameter%d" % i]
         
        self._load()
        syslog(LOG_DEBUG, "Jls.__init__: leave")

    def _load(self):
        out = super(Jls, self).run()
        code = out[0]
        if code == 0:
            index = 0
            out = out[1]
            for line in out.splitlines():
                if index > 0:
                    parts = line.split()
                    if len(parts) == 4:
                        self.__jails.append(JailObject(jid=parts[0],
                            ip=parts[1], hostname=parts[2], path=parts[3]))
                index += 1

    def __len__(self):
        return len(self.__jails)

    def __iter__(self):
        for j in self.__jails:
            yield j
