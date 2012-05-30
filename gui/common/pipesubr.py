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

from shlex import split as shlex_split
from subprocess import Popen, PIPE
from os import system as __system
import logging

logging.NOTICE = 60
logging.addLevelName(logging.NOTICE, "NOTICE")
logging.ALERT = 70
logging.addLevelName(logging.ALERT, "ALERT")
log = logging.getLogger('common.pipesubr')


def pipeopen(command, important=True, logger=log):
    logger.log(logging.NOTICE if important else logging.DEBUG,
        "Popen()ing: " + command)
    args = shlex_split(command)
    return Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True)


def system(command, important=True, logger=log):
    logger.log(logging.NOTICE if important else logging.DEBUG,
        "Executing: " + command)
    __system("(" + command + ") 2>&1 | logger -p daemon.notice -t %s" % (
        logger.name, ))
    logger.log(logging.INFO if important else logging.DEBUG,
        "Executed: " + command)
