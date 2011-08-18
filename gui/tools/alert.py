#!/usr/bin/env python
#-
# Copyright (c) 2011 iXsystems, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#

import sys
sys.path.append('/usr/local/www')
sys.path.append('/usr/local/www/freenasUI')

from freenasUI import settings

from django.core.management import setup_environ
setup_environ(settings)

from django.contrib.auth.models import User, UNUSABLE_PASSWORD

import os
from freenasUI.common.system import send_mail
from freenasUI.storage.models import Volume

class Alert(object):

    LOG_OK = "OK"
    LOG_CRIT = "CRIT"
    LOG_WARN = "WARN"

    def __init__(self):
        self.__f = open('/var/tmp/alert', 'w')

    def log(self, level, msg):
        self.__f.write("%s: %s\n" % (level, msg) )

    def volumes_status(self):
        for vol in Volume.objects.filter(vol_fstype__in=['ZFS','UFS']):
            if vol.status == 'HEALTHY':
                self.log(self.LOG_OK, "The volume %s status is HEALTHY" % vol)
            elif vol.status == 'DEGRADED':
                self.log(self.LOG_CRIT, "The volume %s status is DEGRADED" % vol)
            else:
                self.log(self.LOG_WARN, "The volume %s status is %s" % (vol, vol.status))

    def admin_password(self):
        user = User.objects.filter(password=UNUSABLE_PASSWORD)
        if user.exists():
            self.log(self.LOG_CRIT, "You have to change the password for the admin user (currently no password is required to login)")

    def __del__(self):
        self.__f.close()

if __name__ == "__main__":
    alert = Alert()
    alert.volumes_status()
    alert.admin_password()
