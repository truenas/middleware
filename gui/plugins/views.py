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
from collections import namedtuple

import ipaddress
import logging
import os
import socket
import urllib.request

from django.shortcuts import render
from django.http import Http404, HttpResponse

from freenasUI.common.warden import (
    Warden,
    WardenJail,
    WARDEN_STATUS_RUNNING,
    WARDEN_STATUS_STOPPED,
)
from freenasUI.freeadmin.middleware import public
from freenasUI.jails.models import (
    Jails,
    JailsConfiguration
)
from freenasUI.middleware.notifier import notifier
from freenasUI.network.models import GlobalConfiguration
from freenasUI.plugins import models
from freenasUI.plugins.utils import (
    get_base_url,
    get_plugin_status,
)
from freenasUI.plugins.utils.fcgi_client import FCGIApp

from multiprocessing.pool import ThreadPool

import freenasUI.plugins.api_calls

log = logging.getLogger('plugins.views')


def home(request):

    try:
        models.Configuration.objects.latest('id')
    except Exception as e:
        models.Configuration.objects.create()

    return render(request, "plugins/index.html")


def plugins(request):
    jc_path = None
    try:
        jc = JailsConfiguration.objects.order_by("-id")[0]
        jc_path = jc.jc_path

    except:
        jc_path = None

    Service = namedtuple('Service', [
        'name',
        'status',
        'pid',
        'start_url',
        'stop_url',
        'status_url',
        'jail_status',
    ])

    host = get_base_url(request)

    plugins = []
    temp = models.Plugins.objects.filter(plugin_enabled=True)
    if jc_path:
        for t in temp:
            if os.path.exists("%s/%s" % (jc_path, t.plugin_jail)):
                plugins.append(t)

    args = [(y, host, request) for y in plugins]

    with ThreadPool(10) as pool:
        for plugin, _json, jail_status in pool.imap(get_plugin_status, args):
            if not _json:
                _json = {}
                _json['status'] = None

            plugin.service = Service(
                name=plugin.plugin_name,
                status=_json['status'],
                pid=_json.get("pid", None),
                start_url="/plugins/%s/%d/_s/start" % (
                    plugin.plugin_name, plugin.id
                ),
                stop_url="/plugins/%s/%d/_s/stop" % (
                    plugin.plugin_name, plugin.id
                ),
                status_url="/plugins/%s/%d/_s/status" % (
                    plugin.plugin_name, plugin.id
                ),
                jail_status=jail_status,
            )

    return render(request, "plugins/plugins.html", {
        'plugins': plugins,
    })


def default_icon():
    default = (
        "/usr/local/www/freenasUI/freeadmin/static/images/ui/menu/plugins.png"
    )
    try:
        icon_path = default
        with open(icon_path, "r") as f:
            icon = f.read()
            f.close()
    except:
        icon = None

    return icon


def plugin_installed_icon(request, plugin_name, oid):
    icon = None
    plugin = models.Plugins.objects.get(pk=oid)
    for wo in Warden().cached_list():
        wj = WardenJail(**wo)
        if wj.host == plugin.plugin_jail and wj.status == WARDEN_STATUS_STOPPED:
            icon = default_icon()
            break
        if wj.host == plugin.plugin_jail and wj.status == WARDEN_STATUS_RUNNING:
            url = "%s/plugins/%s/%d/treemenu-icon" % \
                (get_base_url(request), plugin_name, int(oid))
            try:
                response = urllib.request.urlopen(url, timeout=15)
                icon = response.read()
            except:
                pass
            break

    if not icon:
        icon = default_icon()

    return HttpResponse(icon, content_type="image/png")

#
# Get the primary IPv4 address of this host. We
# assume that there will always be an IPv4 address and
# we also assume that plugins will always have an IPv4
# address, and that is how we communicate with them.
#
def get_ipv4_addr():
    def hex_to_cidr(num):
        cidr = 0
        while num:
            cidr += (num & 0x01)
            num >>= 1
        return cidr

    gc = GlobalConfiguration.objects.all()[0]

    ipv4gateway = gc.gc_ipv4gateway
    if not ipv4gateway:
        return
    ipv4gateway_obj = ipaddress.ip_interface(ipv4gateway)

    _n = notifier()
    iface = _n.get_default_interface()
    ii = _n.get_interface_info(iface)
    if 'ipv4' in ii:
        ipv4_info = ii['ipv4']
        for i in ipv4_info:
            ipv4addr = str(i['inet'])
            netmask = str(hex_to_cidr(int(i['netmask'], 0)))
            ipv4_obj = ipaddress.ip_interface('%s/%s' % (ipv4addr, netmask))
            ipv4_network = ipv4_obj.network
            if ipv4gateway_obj in ipv4_network:
                return ipv4addr


@public
def plugin_fcgi_client(request, name, oid, path):
    """
    This is a view that works as a FCGI client
    It is used for development server (no nginx) for easier development
    """
    jc = JailsConfiguration.objects.all()
    if not jc.exists():
        raise Http404

    jc = jc[0]

    qs = models.Plugins.objects.filter(id=oid, plugin_name=name)
    if not qs.exists():
        raise Http404

    plugin = qs[0]
    try:
        jail = Jails.objects.filter(jail_host=plugin.plugin_jail)[0]
    except IndexError:
        raise Http404
    jail_ip = jail.jail_ipv4_addr

    fastcgi_env_path = "%s/%s/%s/fastcgi_env" % (
        jc.jc_path, jail.jail_host, plugin.plugin_path
    )

    app = FCGIApp(host=str(jail_ip), port=plugin.plugin_port)
    env = request.META.copy()

    try:
        if os.path.exists(fastcgi_env_path):
            plugin_fascgi_env = {}
            exec(compile(open(fastcgi_env_path).read(), fastcgi_env_path, 'exec'), {}, plugin_fascgi_env)
            env.update(plugin_fascgi_env)

    except Exception as e:
        log.debug("Failed to update CGI headers: %s", e)

    env.pop('wsgi.file_wrapper', None)
    env.pop('wsgi.version', None)
    env.pop('wsgi.input', None)
    env.pop('wsgi.errors', None)
    env.pop('wsgi.multiprocess', None)
    env.pop('wsgi.run_once', None)
    env['SCRIPT_NAME'] = env['PATH_INFO']
    if request.is_secure():
        env['HTTPS'] = 'on'

    # Always use Ipv4 to talk to plugins
    try:
        host_ip = get_ipv4_addr()
        if host_ip:
            env['SERVER_ADDR'] = host_ip
            env['HTTP_HOST'] = host_ip
    except:
        log.debug('Failed to get default ipv4 for plugin comm', exc_info=True)

    args = request.POST if request.method == "POST" else request.GET
    try:
        status, headers, body, err = app(env, args=args)
    except socket.error as e:
        resp = HttpResponse(str(e))
        resp.status_code = 503
        return resp

    if err:
        log.debug('Error in FastCGI proxy call %r', err)

    resp = HttpResponse(body)
    for header, value in headers:
        resp[header] = value
    return resp
