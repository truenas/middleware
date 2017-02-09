# Copyright 2012 iXsystems, Inc.
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
import math
import syslog

from django.utils import translation


class SysLogHandler(logging.Handler):

    priority_names = {
        "alert": syslog.LOG_ALERT,
        "crit": syslog.LOG_CRIT,
        "critical": syslog.LOG_CRIT,
        "debug": syslog.LOG_DEBUG,
        "emerg": syslog.LOG_EMERG,
        "err": syslog.LOG_ERR,
        "error": syslog.LOG_ERR,  # DEPRECATED
        "info": syslog.LOG_INFO,
        "notice": syslog.LOG_NOTICE,
        "panic": syslog.LOG_EMERG,  # DEPRECATED
        "warn": syslog.LOG_WARNING,  # DEPRECATED
        "warning": syslog.LOG_WARNING,
    }

    def __init__(self, facility=syslog.LOG_USER):
        self.facility = facility
        super(SysLogHandler, self).__init__()

    def emit(self, record):
        syslog.openlog(facility=self.facility)
        # Log everything in english for now as console is not unicode ready
        with translation.override('en'):
            if hasattr(record.msg, '_proxy____kw'):
                record.msg = str(record.msg)
            msg = self.format(record)
        if isinstance(msg, str):
            msg = msg.encode('utf-8')
        """
        syslog has a character limit per message
        split the message in chuncks

        The value of 950 is a guess based on tests,
        it could be a little higher.
        """
        num_msgs = int(math.ceil(len(msg) / 950.0))
        for i in range(num_msgs):
            if num_msgs == i - 1:
                _msg = msg[950 * i:]
            else:
                _msg = msg[950 * i:950 * (i + 1)]
            syslog.syslog(
                self.priority_names.get(record.levelname.lower(), "debug"),
                _msg)
        syslog.closelog()
