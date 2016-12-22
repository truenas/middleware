#!/usr/bin/env python
#
# Copyright (c) 2015 iXsystems, Inc.
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

import logging
import os
import socket
import sys

sys.path.extend([
    '/usr/local/lib',
    '/usr/local/www',
    '/usr/local/www/freenasUI',
])

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from django.utils.translation import ugettext as _

from freenasOS import Configuration, Update
from freenasUI.common.system import get_sw_name, send_mail
from freenasUI.middleware.notifier import notifier
from freenasUI.system.models import Update as mUpdate
from middlewared.plugins.update import get_changelog

log = logging.getLogger('tools.update_check')


def main():

    try:
        updateobj = mUpdate.objects.order_by('-id')[0]
    except IndexError:
        updateobj = mUpdate.objects.create()

    if updateobj.upd_autocheck is False:
        return

    location = notifier().get_update_location()

    Update.DownloadUpdate(updateobj.get_train(), location)

    update = Update.CheckForUpdates(
        train=updateobj.get_train(),
        cache_dir=location,
    )

    if not update:
        return

    conf = Configuration.Configuration()
    sys_mani = conf.SystemManifest()
    if sys_mani:
        sequence = sys_mani.Sequence()
    else:
        sequence = ''

    changelog = get_changelog(
        updateobj.get_train(),
        start=sequence,
        end=update.Sequence(),
    )

    hostname = socket.gethostname()

    send_mail(
        subject='%s: %s' % (
            hostname,
            _('Update Available'),
        ),
        extra_headers={'X-Mailer': get_sw_name(),
                       'X-%s-Host' % get_sw_name(): socket.gethostname()},
        text=_('''A new update is available for the %(train)s train.

Version: %(version)s
Changelog:
%(changelog)s
''') % {
            'train': updateobj.get_train(),
            'version': update.Version(),
            'changelog': changelog,
        },
    )


if __name__ == '__main__':
    main()
