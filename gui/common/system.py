#
# Copyright 2010 iXsystems, Inc.
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
import json
import logging
import requests
import time
from datetime import datetime, timedelta

from freenasUI.middleware.client import client

VERSION_FILE = '/etc/version'
_VERSION = None
log = logging.getLogger("common.system")


def get_sw_version(strip_build_num=False):
    """Return the full version string, e.g. FreeNAS-8.1-r7794-amd64."""
    try:
        from freenasOS import Configuration
    except ImportError:
        Configuration = None

    global _VERSION

    if _VERSION is None:
        # See #9113
        if Configuration:
            conf = Configuration.Configuration()
            sys_mani = conf.SystemManifest()
            if sys_mani:
                _VERSION = sys_mani.Sequence()
        if _VERSION is None:
            with open(VERSION_FILE) as fd:
                _VERSION = fd.read().strip()
    if strip_build_num:
        return _VERSION.split(' ')[0]
    return _VERSION


def get_sw_login_version():
    """Return a shortened version string, e.g. 8.0.1-RC1, 8.1, etc. """

    return '-'.join(get_sw_version(strip_build_num=True).split('-')[1:-2])


def get_sw_name():
    """Return the software name, e.g. FreeNAS"""

    return get_sw_version().split('-')[0]


def get_sw_year():
    return str(datetime.now().year)


def send_mail(
    subject=None, text=None, interval=None, channel=None,
    to=None, extra_headers=None, attachments=None, timeout=300,
    queue=True,
):

    if isinstance(interval, timedelta):
        interval = int(interval.total_seconds())
    try:
        data = {
            'subject': subject,
            'text': text,
            'interval': interval,
            'channel': channel,
            'to': to,
            'timeout': timeout,
            'queue': queue,
            'extra_headers': extra_headers,
            'attachments': bool(attachments),
        }
        if not attachments:
            with client as c:
                c.call('mail.send', data, job=True)
        else:
            # FIXME: implement upload via websocket
            with client as c:
                token = c.call('auth.generate_token')
                files = []
                for attachment in attachments:
                    entry = {'headers': []}
                    for k, v in attachment.items():
                        entry['headers'].append({'name': k, 'value': v})
                    entry['content'] = attachment.get_payload()
                    files.append(entry)

                r = requests.post(
                    f'http://localhost:6000/_upload?auth_token={token}',
                    files={
                        'data': json.dumps({'method': 'mail.send', 'params': [data]}),
                        'file': json.dumps(files),
                    },
                )
                if r.status_code != 200:
                    return True, r.text
                res = r.json()
                while True:
                    job = c.call('core.get_jobs', [('id', '=', res['job_id'])])[0]
                    if job['state'] in ('SUCCESS', 'FAILED', 'ABORTED'):
                        break
                    time.sleep(1)
                if job['state'] != 'SUCCESS':
                    return True, job['error']

    except Exception as e:
        return True, str(e)
    return False, ''


def ldap_enabled():
    from freenasUI.directoryservice.models import LDAP

    enabled = False
    try:
        ldap = LDAP.objects.all()[0]
        enabled = ldap.ldap_enable

    except Exception:
        enabled = False

    return enabled


def activedirectory_enabled():
    from freenasUI.directoryservice.models import ActiveDirectory

    enabled = False
    try:
        ad = ActiveDirectory.objects.all()[0]
        enabled = ad.ad_enable

    except Exception:
        enabled = False

    return enabled


def nis_enabled():
    from freenasUI.directoryservice.models import NIS

    enabled = False
    try:
        nis = NIS.objects.all()[0]
        enabled = nis.nis_enable

    except Exception:
        enabled = False

    return enabled
