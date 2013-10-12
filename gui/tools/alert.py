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

from cStringIO import StringIO
import hashlib
import os
import re
import subprocess
import sys

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI'
])

from freenasUI import settings

from django.core.management import setup_environ
setup_environ(settings)

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from django.contrib.auth.models import User, UNUSABLE_PASSWORD
from django.utils.translation import ugettext_lazy as _

from freenasUI.common.system import send_mail
from freenasUI.freeadmin.hook import HookMetaclass
from freenasUI.freeadmin.utils import set_language
from freenasUI.middleware.notifier import notifier
from freenasUI.storage.models import Volume
from freenasUI.system.models import Alert as mAlert, Settings

ALERT_FILE = '/var/tmp/alert'
LAST_ALERT_FILE = '/var/tmp/alert.last'
PORTAL_IP_FILE = '/var/tmp/iscsi_portal_ip'


class Message(object):

    def __init__(self, message, msgid=None):
        self._message = message
        self._msgid = msgid

    def __repr__(self):
        return repr(self._message)

    def __str__(self):
        return str(self._message)

    def __unicode__(self):
        return self._message.decode('utf8')


class Alert(object):

    __metaclass__ = HookMetaclass

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

    def log(self, level, msg, msgid=None):
        msg = msg.encode('utf-8')
        if msgid is None:
            msgid = hashlib.md5(msg).hexdigest()
        msg = Message(msg, msgid)
        self.__logs[level].append(msg)
        self.__s.write('%s[%s]: %s\n' % (level, msgid, msg, ))

    def volumes_status(self):
        for vol in Volume.objects.filter(vol_fstype__in=['ZFS', 'UFS']):
            if not vol.is_decrypted():
                continue
            status = vol.status
            message = ""
            if  vol.vol_fstype == 'ZFS':
                p1 = subprocess.Popen(["zpool", "status", "-x", vol.vol_name],
                        stdout=subprocess.PIPE)
                stdout = p1.communicate()[0]
                if stdout.find("pool '%s' is healthy" % vol.vol_name) != -1:
                    status = 'HEALTHY'
                else:
                    reg1 = re.search('^\s*state: (\w+)', stdout, re.M)
                    if reg1:
                        status = reg1.group(1)
                    else:
                        # The default case doesn't print out anything helpful,
                        # but instead coredumps ;).
                        status = 'UNKNOWN'
                    reg1 = re.search(r'^\s*status: (.+)\n\s*action+:',
                                     stdout, re.S | re.M)
                    reg2 = re.search(r'^\s*action: ([^:]+)\n\s*\w+:',
                                     stdout, re.S | re.M)
                    if reg1:
                        msg = reg1.group(1)
                        msg = re.sub(r'\s+', ' ', msg)
                        message += msg
                    if reg2:
                        msg = reg2.group(1)
                        msg = re.sub(r'\s+', ' ', msg)
                        message += msg

            if status == 'HEALTHY':
                self.log(self.LOG_OK,
                         _('The volume %s status is HEALTHY') % (vol, ))
            elif status == 'DEGRADED':
                self.log(self.LOG_CRIT,
                         _('The volume %s status is DEGRADED') % (vol, ))
            else:
                if message:
                    self.log(self.LOG_WARN,
                             _('The volume %(volume)s status is %(status)s:'
                                ' %(message)s') % {
                                    'volume': vol,
                                    'status': status,
                                    'message': message,
                                    })
                else:
                    self.log(self.LOG_WARN,
                        _('The volume %(volume)s status is %(status)s') % {
                            'volume': vol,
                            'status': status,
                            })

    def admin_password(self):
        user = User.objects.filter(password=UNUSABLE_PASSWORD)
        if user.exists():
            self.log(self.LOG_CRIT, _('You have to change the password for '
                                      'the admin user (currently no password '
                                      'is required to login)'))

    def httpd_bindaddr(self):
        address = Settings.objects.all().order_by('-id')[0].stg_guiaddress
        with open('/usr/local/etc/nginx/nginx.conf') as f:
            # XXX: this is parse the file instead of slurping in the contents
            # (or in reality, just be moved somewhere else).
            if f.read().find('0.0.0.0') != -1 and address not in ('0.0.0.0', ''):
                # XXX: IPv6
                self.log(self.LOG_WARN,
                    _('The WebGUI Address could not bind to %s; using '
                        'wildcard') % (address,))

    def iscsi_portal_ips(self):
        if not os.path.exists(PORTAL_IP_FILE):
            return None
        with open(PORTAL_IP_FILE) as f:
            ips = f.read().split('\n')
            ips = filter(lambda y: bool(y), ips)
            self.log(self.LOG_WARN,
                _('The following IPs are bind to iSCSI Portal but were not '
                'found in the system: %s') % (', '.join(ips))
                )

    def multipaths_status(self):
        not_optimal = []
        for mp in notifier().multipath_all():
            if mp.status != 'OPTIMAL':
                not_optimal.append(mp.name)

        if not_optimal:
            self.log(self.LOG_CRIT,
                _('The following multipaths are not optimal: %s') % (
                    ', '.join(not_optimal),
                    )
                )

    def perform(self):
        self.volumes_status()
        self.admin_password()
        self.httpd_bindaddr()
        self.iscsi_portal_ips()
        self.multipaths_status()
        super(Alert, self).perform()

    def write(self):
        with open(ALERT_FILE, 'w') as f:
            f.write(self.__s.getvalue())

    def email(self):
        """
        Use alert.last to hold a sha256 hash of the last sent alerts
        If the hash is the same do not resend the email
        """
        dismisseds = [a.message_id
            for a in mAlert.objects.filter(dismiss=True)
            ]
        msgs = []
        for msg in self.__logs[self.LOG_CRIT]:
            if msg._msgid not in dismisseds:
                msgs.append(unicode(msg))
        if len(msgs) == 0:
            if os.path.exists(LAST_ALERT_FILE):
                os.unlink(LAST_ALERT_FILE)
            return
        try:
            with open(LAST_ALERT_FILE) as f:
                sha256 = f.read()
        except:
            sha256 = ''
        newsha = hashlib.sha256(repr(msgs)).hexdigest()
        if newsha != sha256:
            send_mail(subject=_("Critical Alerts"),
                      text='\n'.join(msgs))
            with open(LAST_ALERT_FILE, 'w') as f:
                f.write(newsha)

    def __del__(self):
        self.__s.close()

if __name__ == '__main__':
    set_language()
    alert = Alert()
    alert.perform()
    alert.email()
    alert.write()
