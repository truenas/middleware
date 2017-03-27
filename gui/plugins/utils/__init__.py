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
import json
import logging
import re

from django.utils.translation import ugettext as _

from freenasUI.middleware.notifier import notifier

from ipaddr import IPv6Address

log = logging.getLogger('plugins.utils')


def get_base_url(request=None):
    proto = 'https' if request.is_secure() else 'http'
    addr = request.META.get("SERVER_ADDR")
    if not addr:
        addr = request.get_host()
    else:
        port = int(request.META.get("SERVER_PORT", 80))
        if (
            (proto == 'http' and port != 80) or
            (proto == 'https' and port != 443)
        ):
            addr = "%s:%d" % (addr, port)

    try:
        IPv6Address(addr)
        addr = "[%s]" % addr
    except:
        pass

    return "%s://%s" % (proto, addr)


def get_plugin_status(args):
    plugin, host, request = args
    if re.match('^.+\[.+\]', host, re.I):
        import urllib.request as urllib_request
    else:
        from eventlet.green.urllib import request as urllib_request

    url = "%s/plugins/%s/%d/_s/status" % (
        host,
        plugin.plugin_name,
        plugin.id)
    data = None

    jail_status = notifier().pluginjail_running(pjail=plugin.plugin_jail)
    if not jail_status:
        return plugin, data, jail_status

    try:
        opener = urllib_request.build_opener()
        opener.addheaders = [
            ('Cookie', 'sessionid=%s' % (
                request.COOKIES.get("sessionid", ''),
            ))
        ]
        # TODO: Increase timeout based on number of plugins
        response = opener.open(url, None).read()
        data = json.loads(response)
    except Exception as e:
        log.warn(_("Couldn't retrieve %(url)s: %(error)s") % {
            'url': url,
            'error': e,
        })
    return plugin, data, jail_status


def get_plugin_start(args):
    plugin, host, request = args
    if re.match('^.+\[.+\]', host, re.I):
        import urllib.request as urllib_request
    else:
        from eventlet.green.urllib import request as urllib_request

    url = "%s/plugins/%s/%d/_s/start" % (
        host,
        plugin.plugin_name,
        plugin.id)
    data = None

    jail_status = notifier().pluginjail_running(pjail=plugin.plugin_jail)
    if not jail_status:
        return plugin, data, jail_status

    try:
        opener = urllib_request.build_opener()
        opener.addheaders = [
            ('Cookie', 'sessionid=%s' % (
                request.COOKIES.get("sessionid", ''),
            ))
        ]
        # TODO: Increase timeout based on number of plugins
        response = opener.open(url, None).read()
        data = json.loads(response)
    except Exception as e:
        log.warn(_("Couldn't retrieve %(url)s: %(error)s") % {
            'url': url,
            'error': e,
        })
    return plugin, data, jail_status


def get_plugin_stop(args):
    plugin, host, request = args
    if re.match('^.+\[.+\]', host, re.I):
        import urllib.request as urllib_request
    else:
        from eventlet.green.urllib import request as urllib_request

    url = "%s/plugins/%s/%d/_s/stop" % (
        host,
        plugin.plugin_name,
        plugin.id)
    data = None

    jail_status = notifier().pluginjail_running(pjail=plugin.plugin_jail)
    if not jail_status:
        return plugin, data, jail_status

    try:
        opener = urllib_request.build_opener()
        opener.addheaders = [
            ('Cookie', 'sessionid=%s' % (
                request.COOKIES.get("sessionid", ''),
            ))
        ]
        # TODO: Increase timeout based on number of plugins
        response = opener.open(url, None).read()
        data = json.loads(response)
    except Exception as e:
        log.warn(_("Couldn't retrieve %(url)s: %(error)s") % {
            'url': url,
            'error': e,
        })
    return plugin, data, jail_status
