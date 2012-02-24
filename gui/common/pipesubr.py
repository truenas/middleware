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
#####################################################################

import syslog
from shlex import split as shlex_split
from subprocess import Popen, PIPE, STDOUT
from os import system as __system

class info(object):
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(info, cls).__new__(cls, *args, **kwargs)
            cls._instance.name = 'middleware'
        return cls._instance
    def setname(self, name):
        self.name = name
    def getname(self):
        return self.name

def pipeopen(command, important=True):
    pipeinfo = info()
    syslog.openlog(pipeinfo.getname(), syslog.LOG_CONS | syslog.LOG_PID)
    syslog.syslog(syslog.LOG_NOTICE if important else syslog.LOG_DEBUG, "Popen()ing: " + command)
    args = shlex_split(command)
    return Popen(args, stdin = PIPE, stdout = PIPE, stderr = PIPE, close_fds = True)

def system(command, important=True):
    pipeinfo = info()
    syslog.openlog(pipeinfo.getname(), syslog.LOG_CONS | syslog.LOG_PID)
    syslog.syslog(syslog.LOG_NOTICE if important else syslog.LOG_DEBUG, "Executing: " + command)
    __system("(" + command + ") 2>&1 | logger -p daemon.notice -t %s" % (pipeinfo.name, ))
    syslog.syslog(syslog.LOG_INFO if important else syslog.LOG_DEBUG, "Executed: " + command)

def setname(name):
    pipeinfo = info()
    pipeinfo.setname(name)
