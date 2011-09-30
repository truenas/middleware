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

import hashlib
import os
import sys
import subprocess
from cStringIO import StringIO

sys.path.append('/usr/local/www')
sys.path.append('/usr/local/www/freenasUI')

from freenasUI import settings

from django.core.management import setup_environ
setup_environ(settings)

from django.contrib.auth.models import User, UNUSABLE_PASSWORD
from django.utils.translation import ugettext_lazy as _

from freenasUI.common.system import send_mail
from freenasUI.storage.models import Volume
from freenasUI.system.models import Settings

class Alert(object):

    LOG_OK = "OK"
    LOG_CRIT = "CRIT"
    LOG_WARN = "WARN"

    def __init__(self):
        self.__s = StringIO()
        self.__logs = {
            self.LOG_OK: [],
            self.LOG_CRIT: [],
            self.LOG_WARN: [],
        }

    def log(self, level, msg):
        self.__logs[level].append(msg)
        self.__s.write("%s: %s\n" % (level, msg) )

    def volumes_status(self):
        for vol in Volume.objects.filter(vol_fstype__in=['ZFS','UFS']):
            if vol.status == 'HEALTHY':
                self.log(self.LOG_OK, _("The volume %s status is HEALTHY") % vol)
            elif vol.status == 'DEGRADED':
                self.log(self.LOG_CRIT, _("The volume %s status is DEGRADED") % vol)
            else:
                self.log(self.LOG_WARN, _("The volume %s status is %s") % (vol, vol.status))

    def admin_password(self):
        user = User.objects.filter(password=UNUSABLE_PASSWORD)
        if user.exists():
            self.log(self.LOG_CRIT, _("You have to change the password for the admin user (currently no password is required to login)"))

    def lighttpd_bindaddr(self):
        address = Settings.objects.all().order_by('-id')[0].stg_guiaddress
        with open('/usr/local/etc/lighttpd/lighttpd.conf') as f:
            if f.read().find('0.0.0.0') != -1 and address not in ('0.0.0.0', ''):
                self.log(self.LOG_WARN, _("The WebGUI Address could not be bind to %s, using wildcard") % (address,))

    def perform(self):
        self.volumes_status()
        self.admin_password()
        self.lighttpd_bindaddr()

    def write(self):
        f = open('/var/tmp/alert', 'w')
        f.write(self.__s.getvalue())
        f.close()

    def email(self):
        """
        Use alert.last to hold a sha256 hash of the last sent alerts
        If the hash is the same do not resend the email
        """
        if len(self.__logs[self.LOG_CRIT]) == 0:
            if os.path.exists('/var/tmp/alert.last'):
                os.unlink('/var/tmp/alert.last')
            return
        try:
            with open('/var/tmp/alert.last', 'r') as f:
                sha256 = f.read()
        except:
            sha256 = ''
        newsha = hashlib.sha256(repr(self.__logs[self.LOG_CRIT])).hexdigest()
        if newsha != sha256:
            send_mail(subject=_("Critical Alerts"), text="\n".join(self.__logs[self.LOG_CRIT]))
            with open('/var/tmp/alert.last', 'w+') as f:
                f.write(newsha)

    def __del__(self):
        self.__s.close()

if __name__ == "__main__":
    alert = Alert()
    alert.perform()
    alert.email()
    alert.write()
