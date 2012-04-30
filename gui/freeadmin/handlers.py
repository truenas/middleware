#+
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
import syslog


class SysLogHandler(logging.Handler):

    priority_names = {
        "alert":    syslog.LOG_ALERT,
        "crit":     syslog.LOG_CRIT,
        "critical": syslog.LOG_CRIT,
        "debug":    syslog.LOG_DEBUG,
        "emerg":    syslog.LOG_EMERG,
        "err":      syslog.LOG_ERR,
        "error":    syslog.LOG_ERR,        # DEPRECATED
        "info":     syslog.LOG_INFO,
        "notice":   syslog.LOG_NOTICE,
        "panic":    syslog.LOG_EMERG,      # DEPRECATED
        "warn":     syslog.LOG_WARNING,    # DEPRECATED
        "warning":  syslog.LOG_WARNING,
        }

    def __init__(self, facility=syslog.LOG_USER):
        self.facility = facility
        super(SysLogHandler, self).__init__()

    def emit(self, record):
        hand = syslog.openlog(facility=self.facility)
        msg = self.format(record)
        syslog.syslog(
            self.priority_names.get(record.levelname.lower(), "debug"),
            msg)
        syslog.closelog()
