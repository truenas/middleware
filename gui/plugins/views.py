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
import json
import os
import socket
import urllib2
import middlewared.logger

from django.shortcuts import render
from django.http import Http404, HttpResponse
from django.utils.translation import ugettext as _

import eventlet
from freenasUI.common.warden import (
    Warden,
    WardenJail,
    WARDEN_STATUS_RUNNING,
    WARDEN_STATUS_STOPPED,
    WARDEN_EXTRACT_STATUS_FILE
)
from freenasUI.freeadmin.middleware import public
from freenasUI.freeadmin.views import JsonResp
from freenasUI.jails.models import (
    Jails,
    JailsConfiguration
)
from freenasUI.jails.utils import (
    jail_path_configured,
    jail_auto_configure,
    guess_addresses,
    new_default_plugin_jail
)
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier
from freenasUI.network.models import GlobalConfiguration
from freenasUI.plugins import models, forms, availablePlugins
from freenasUI.plugins.plugin import PROGRESS_FILE
from freenasUI.plugins.utils import (
    get_base_url,
    get_plugin_status,
    get_plugin_stop
)
from freenasUI.plugins.utils.fcgi_client import FCGIApp

import freenasUI.plugins.api_calls

log = middlewared.logger.Logger('plugins.views')


def safe_unlink(path):
    if os.path.exists(path):
        os.unlink(path)


def reset_plugin_progress():

    if not jail_path_configured():
        jail_auto_configure()

    jc = JailsConfiguration.objects.order_by("-id")[0]
    logfile = '%s/warden.log' % jc.jc_path

    safe_unlink(logfile)
    safe_unlink(WARDEN_EXTRACT_STATUS_FILE)
    safe_unlink("/tmp/.plugin_upload_install")
    safe_unlink("/tmp/.jailcreate")
    safe_unlink(PROGRESS_FILE)
    safe_unlink("/tmp/.fetchmtree")
    safe_unlink("/tmp/.checkmtree")


def home(request):

    try:
        default_iface = notifier().get_default_interface()
        conf = models.Configuration.objects.latest('id')

        reset_plugin_progress()
    except MiddlewareError as e:
        error = e.value
        return render(request, "plugins/index_error.html", {
            'error': error,
        })

    return render(request, "plugins/index.html", {
        'conf': conf,
        'default_iface': default_iface
    })


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

    args = map(lambda y: (y, host, request), plugins)

    pool = eventlet.GreenPool(20)
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

        plugin.update_available = availablePlugins.get_update_status(plugin.id)

    return render(request, "plugins/plugins.html", {
        'plugins': plugins,
    })


def plugin_edit(request, plugin_id):
    plugin = models.Plugins.objects.filter(id=plugin_id)[0]

    if request.method == 'POST':
        plugins_form = forms.PluginsForm(request.POST, instance=plugin)
        if plugins_form.is_valid():
            plugins_form.save()
            return JsonResp(request, message=_("Plugin successfully updated."))
        else:
            plugin = None

    else:
        plugins_form = forms.PluginsForm(instance=plugin)

    return render(request, 'plugins/plugin_edit.html', {
        'plugin_id': plugin_id,
        'form': plugins_form
    })


def plugin_info(request, plugin_id):
    plugin = models.Plugins.objects.filter(id=plugin_id)[0]
    return render(request, 'plugins/plugin_info.html', {
        'plugin': plugin,
    })


def plugin_update(request, oid):
    host = get_base_url(request)

    reset_plugin_progress()

    iplugin = models.Plugins.objects.filter(id=oid)
    if not iplugin:
        raise MiddlewareError(_("Plugin not installed"))
    iplugin = iplugin[0]

    rplugin = None
    for rp in availablePlugins.get_remote(cache=True):
        if rp.name.lower() == iplugin.plugin_name.lower():
            rplugin = rp
            break

    if not rplugin:
        raise MiddlewareError(_("Invalid plugin"))

    (p, js, jail_status) = get_plugin_status([iplugin, host, request])
    if js and js['status'] == 'RUNNING':
        (p, js, jail_status) = get_plugin_stop([iplugin, host, request])

    if request.method == "POST":
        plugin_upload_path = notifier().get_plugin_upload_path()
        notifier().change_upload_location(plugin_upload_path)

        if not rplugin.download("/var/tmp/firmware/pbifile.pbi"):
            raise MiddlewareError(_("Failed to download plugin"))

        jail = Jails.objects.filter(jail_host=iplugin.plugin_jail)
        if not jail:
            raise MiddlewareError(_("Jail does not exist"))

        if notifier().update_pbi(plugin=iplugin):
            notifier()._start_plugins(
                jail=iplugin.plugin_jail,
                plugin=iplugin.plugin_name,
            )

        else:
            raise MiddlewareError(_("Failed to update plugin"))

        return JsonResp(
            request,
            message=_("Plugin successfully updated"),
            events=['reloadHttpd()'],
        )

    return render(request, "plugins/plugin_update.html", {
        'plugin': rplugin,
    })


def install_available(request, oid):

    try:
        jc = JailsConfiguration.objects.all()[0]
    except IndexError:
        jc = JailsConfiguration.objects.create()

    try:
        if not jail_path_configured():
            jail_auto_configure()

        if not jc.jc_ipv4_dhcp:
            addrs = guess_addresses()
            if not addrs['high_ipv4']:
                raise MiddlewareError(_("No available IP addresses"))

    except MiddlewareError, e:
        return render(request, "plugins/install_error.html", {
            'error': e.value,
        })

    if os.path.exists("/tmp/.plugin_upload_update"):
        os.unlink("/tmp/.plugin_upload_update")
    if os.path.exists(PROGRESS_FILE):
        os.unlink(PROGRESS_FILE)

    plugin = None
    for p in availablePlugins.get_remote(cache=True):
        if p.id == oid:
            plugin = p
            break

    if not plugin:
        raise MiddlewareError(_("Invalid plugin"))

    if request.method == "POST":

        plugin_upload_path = notifier().get_plugin_upload_path()
        notifier().change_upload_location(plugin_upload_path)

        if not plugin.download("/var/tmp/firmware/pbifile.pbi"):
            raise MiddlewareError(_("Failed to download plugin"))

        try:
            jail = new_default_plugin_jail(plugin.unixname)
        except IOError, e:
            raise MiddlewareError(unicode(e))
        except MiddlewareError, e:
            raise e
        except Exception as e:
            raise MiddlewareError(unicode(e))

        newplugin = []
        if notifier().install_pbi(jail.jail_host, newplugin):
            newplugin = newplugin[0]
            notifier()._restart_plugins(
                jail=newplugin.plugin_jail,
                plugin=newplugin.plugin_name,
            )
        else:
            jail.delete()

        return JsonResp(
            request,
            message=_("Plugin successfully installed"),
            events=['reloadHttpd()'],
        )

    return render(request, "plugins/available_install.html", {
        'plugin': plugin,
    })


#
# XXX This needs a better implementation.. but will do for now ;-)
#
def install_progress(request):
    jc = JailsConfiguration.objects.order_by("-id")[0]
    logfile = '%s/warden.log' % jc.jc_path
    data = {}
    if os.path.exists(PROGRESS_FILE):
        data = {'step': 1}
        with open(PROGRESS_FILE, 'r') as f:
            try:
                current = int(f.readlines()[-1].strip())
            except:
                pass
        data['percent'] = current
        if current == 100:
            safe_unlink(PROGRESS_FILE)

    if os.path.exists("/tmp/.fetchmtree"):
        data = {'step': 2}

    if os.path.exists(WARDEN_EXTRACT_STATUS_FILE):
        data = {'step': 3}
        percent = 0
        with open(WARDEN_EXTRACT_STATUS_FILE, 'r') as f:
            try:
                buf = f.readlines()[-1].strip()
                parts = buf.split()
                size = len(parts)
                if size > 2:
                    nbytes = float(parts[1])
                    total = float(parts[2])
                    percent = int((nbytes / total) * 100)
            except Exception:
                pass
        data['percent'] = percent

    if os.path.exists("/tmp/.checkmtree"):
        safe_unlink(WARDEN_EXTRACT_STATUS_FILE)
        data = {'step': 4}

    if os.path.exists(logfile):
        data = {'step': 5}
        percent = 0
        with open(logfile, 'r') as f:
            for line in f.xreadlines():
                if line.startswith('====='):
                    parts = line.split()
                    if len(parts) > 1:
                        try:
                            percent = int(parts[1][:-1])
                        except:
                            pass

        if not percent:
            percent = 0
        data['percent'] = percent

    if os.path.exists("/tmp/.plugin_upload_install"):
        data = {'step': 6}

    content = json.dumps(data)
    return HttpResponse(content, content_type='application/json')


def update_progress(request):
    data = {}

    if os.path.exists(PROGRESS_FILE):
        data = {'step': 1}
        with open(PROGRESS_FILE, 'r') as f:
            try:
                current = int(f.readlines()[-1].strip())
            except:
                pass
        data['percent'] = current

    if os.path.exists("/tmp/.plugin_upload_update"):
        data = {'step': 2}

    content = json.dumps(data)
    return HttpResponse(content, content_type='application/json')


def upload(request, jail_id=-1):
    try:
        jc = JailsConfiguration.objects.all()[0]
    except:
        jc = None

    # FIXME: duplicated code with available_install
    try:
        if not jail_path_configured():
            jail_auto_configure()

        if not jc:
            jc = JailsConfiguration.objects.all()[0]

        if not jc.jc_ipv4_dhcp:
            addrs = guess_addresses()
            if not addrs['high_ipv4']:
                raise MiddlewareError(_("No available IP addresses"))

    except MiddlewareError, e:
        return render(request, "plugins/install_error.html", {
            'error': e.value,
        })

    plugin_upload_path = notifier().get_plugin_upload_path()
    notifier().change_upload_location(plugin_upload_path)

    jail = None
    if jail_id > 0:
        try:
            jail = Jails.objects.filter(pk=jail_id)[0]

        except Exception, e:
            log.debug("Failed to get jail %d: %s", jail_id, repr(e))
            jail = None

    if request.method == "POST":
        jc = JailsConfiguration.objects.order_by("-id")[0]
        logfile = '%s/warden.log' % jc.jc_path
        if os.path.exists(logfile):
            os.unlink(logfile)
        if os.path.exists(WARDEN_EXTRACT_STATUS_FILE):
            os.unlink(WARDEN_EXTRACT_STATUS_FILE)
        if os.path.exists("/tmp/.plugin_upload_install"):
            os.unlink("/tmp/.plugin_upload_install")
        if os.path.exists("/tmp/.jailcreate"):
            os.unlink("/tmp/.jailcreate")

        form = forms.PBIUploadForm(request.POST, request.FILES, jail=jail)
        if form.is_valid():
            form.done()
            return JsonResp(
                request,
                message=_('Plugin successfully installed'),
                events=['reloadHttpd()'],
            )
        else:
            resp = render(request, "plugins/upload.html", {
                'form': form,
            })
            resp.content = (
                "<html><body><textarea>"
                + resp.content +
                "</textarea></boby></html>"
            )
            return resp
    else:
        form = forms.PBIUploadForm(jail=jail)

    return render(request, "plugins/upload.html", {
        'form': form,
    })


def upload_nojail(request):
    return upload(request)


def upload_progress(request):
    jc = JailsConfiguration.objects.order_by("-id")[0]
    logfile = '%s/warden.log' % jc.jc_path

    data = {}
    if os.path.exists(logfile):
        data['step'] = 2
        percent = 0
        with open(logfile, 'r') as f:
            for line in f.xreadlines():
                if line.startswith('====='):
                    parts = line.split()
                    if len(parts) > 1:
                        try:
                            percent = int(parts[1][:-1])
                        except:
                            pass

        if not percent:
            percent = 0
        data['percent'] = percent

    if os.path.exists("/tmp/.plugin_upload_install"):
        data = {'step': 3}

    content = json.dumps(data)
    return HttpResponse(content, content_type='application/json')


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


def plugin_available_icon(request, oid):
    icon = availablePlugins.get_icon(None, oid)
    if not icon:
        icon = default_icon()

    return HttpResponse(icon, content_type="image/png")


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
                response = urllib2.urlopen(url, timeout=15)
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
    ipv4gateway_obj = ipaddress.ip_interface(ipv4gateway)

    _n = notifier()
    iface = _n.get_default_interface()
    ii = _n.get_interface_info(iface)
    if 'ipv4' in ii:
        ipv4_info = ii['ipv4']
        for i in ipv4_info:
            ipv4addr =  unicode(i['inet'])
            netmask = unicode(hex_to_cidr(int(i['netmask'], 0)))
            ipv4_obj = ipaddress.ip_interface('%s/%s' % (ipv4addr, netmask))
            ipv4_network = ipv4_obj.network
            if ipv4gateway in ipv4_network:
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
    jail = Jails.objects.filter(jail_host=plugin.plugin_jail)[0]
    jail_ip = jail.jail_ipv4_addr

    fastcgi_env_path = "%s/%s/%s/fastcgi_env" % (
        jc.jc_path, jail.jail_host, plugin.plugin_path
    )

    app = FCGIApp(host=str(jail_ip), port=plugin.plugin_port)
    env = request.META.copy()

    try:
        if os.path.exists(fastcgi_env_path):
            plugin_fascgi_env = { }
            execfile(fastcgi_env_path, {}, plugin_fascgi_env)
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
        env['SERVER_ADDR'] = host_ip
        env['HTTP_HOST'] = host_ip
    except:
        pass

    args = request.POST if request.method == "POST" else request.GET
    try:
        status, headers, body, raw = app(env, args=args)
    except socket.error as e:
        resp = HttpResponse(str(e))
        resp.status_code = 503
        return resp

    resp = HttpResponse(body)
    for header, value in headers:
        resp[header] = value
    return resp
