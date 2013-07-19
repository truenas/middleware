#+
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
import logging

from django.shortcuts import render
from django.http import HttpResponse, Http404
from django.utils.translation import ugettext as _

from freenasUI.common import warden
from freenasUI.freeadmin.middleware import public
from freenasUI.freeadmin.views import JsonResp
from freenasUI.jails.models import Jails, JailsConfiguration
from freenasUI.middleware.notifier import notifier
from freenasUI.plugins import models, forms, availablePlugins
from freenasUI.plugins.utils.fcgi_client import FCGIApp

import freenasUI.plugins.api_calls

log = logging.getLogger('plugins.views')

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


def plugin_delete(request, plugin_id):
    plugin_id = int(plugin_id)
    plugin = models.Plugins.objects.get(id=plugin_id)

    if request.method == 'POST':
        notifier()._stop_plugins(plugin.plugin_name)
        if notifier().delete_pbi(plugin):
            return JsonResp(request,
                message=_("Plugin successfully removed."),
                events=['reloadHttpd()']
                )
        else:
            return JsonResp(request,
                error=True,
                message=_("Unable to remove plugin."))
    else:
        return render(request, 'plugins/plugin_confirm_delete.html', {
            'plugin': plugin,
        })


def plugin_update(request, plugin_id):
    plugin_id = int(plugin_id)
    plugin = models.Plugins.objects.get(id=plugin_id)

    plugin_upload_path = notifier().get_plugin_upload_path()
    notifier().change_upload_location(plugin_upload_path)

    if request.method == "POST":
        form = forms.PBIUpdateForm(request.POST, request.FILES, plugin=plugin)
        if form.is_valid():
            form.done()
            return JsonResp(request,
                message=_('Plugin successfully updated'),
                events=['reloadHttpd()'],
                )
        else:
            resp = render(request, "plugins/plugin_update.html", {
                'form': form,
            })
            resp.content = (
                "<html><body><textarea>"
                + resp.content +
                "</textarea></boby></html>"
                )
            return resp
    else:
        form = forms.PBIUpdateForm(plugin=plugin)

    return render(request, "plugins/plugin_update.html", {
        'form': form,
        })


def available_browse(request):
    if request.method == "POST":
        form = forms.AvailableBrowse(request.POST)
        if form.is_valid():
            url = form.cleaned_data.get("url")
            if url:
                request.session['plugins_browse_url'] = url
        return JsonResp(request, form=form)
    else:
        url = request.session.get('plugins_browse_url')
        if not url:
            url = models.PLUGINS_INDEX
        form = forms.AvailableBrowse(initial={'url': url})
    return render(request, "plugins/available_browse.html", {
        'form': form,
    })


def plugin_install_available(request, oid):

    plugin = None
    url = request.session.get('plugins_browse_url')
    if not url:
        url = models.PLUGINS_INDEX
    for p in availablePlugins.get_remote(url=url):
        if p.id == oid:
            plugin = p
            break

    if not plugin:
        raise MiddlewareError(_("Invalid plugin"))

    jailname = None
    for i in xrange(1, 1000):
        tmpname = "%s_%d" % (plugin.name.lower(), i)
        jails = Jails.objects.filter(jail_host=tmpname)
        if not jails:
            jailname = tmpname
            break

    w = warden.Warden()
    w.create(
        jail=jailname,
        ipv4="192.168.3.50",  #FIXME
        flags=(
            warden.WARDEN_CREATE_FLAGS_PLUGINJAIL |
            warden.WARDEN_CREATE_FLAGS_SYSLOG |
            warden.WARDEN_CREATE_FLAGS_IPV4
        ),
    )
    w.set(
        jail=jailname,
        flags=(
            warden.WARDEN_SET_FLAGS_VNET_ENABLE
        )
    )
    w.start(jail=jailname)

    newplugin = []
    if notifier().install_pbi(jailname, newplugin):
        newplugin = newplugin[0]
        notifier()._restart_plugins(
            newplugin.plugin_jail,
            newplugin.plugin_name,
        )
    else:
        #FIXME
        pass

    return JsonResp(
        request,
        message=_("Plugin successfully installed"),
    )


def plugin_install(request, jail_id=-1):
    plugin_upload_path = notifier().get_plugin_upload_path()
    notifier().change_upload_location(plugin_upload_path)

    jail = None
    if jail_id > 0:
        try:
            jail = Jails.objects.filter(pk=jail_id)[0]

        except Exception, e: 
            jail = None

    if request.method == "POST":
        form = forms.PBIUploadForm(request.POST, request.FILES, jail=jail)
        if form.is_valid():
            form.done()
            return JsonResp(request,
                message=_('Plugin successfully installed'),
                events=['reloadHttpd()'],
                )
        else:
            resp = render(request, "plugins/plugin_install.html", {
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

    return render(request, "plugins/plugin_install.html", {
        'form': form,
        })

def plugin_install_nojail(request):
    return plugin_install(request)


@public
def plugin_fcgi_client(request, name, path):
    log.debug("XXX: plugin_fcgi_client: reqest = %s", request)
    log.debug("XXX: plugin_fcgi_client: name = %s", name)
    log.debug("XXX: plugin_fcgi_client: path = %s", path)
#    """
#    This is a view that works as a FCGI client
#    It is used for development server (no nginx) for easier development
#
#    XXX
#    XXX - This will no longer work with multiple jail model
#    XXX
#    """
#    qs = models.Plugins.objects.filter(plugin_name=name)
#    if not qs.exists():
#        raise Http404
#
#    plugin = qs[0]
#    jail_ip = PluginsJail.objects.order_by('-id')[0].jail_ipv4address
#
#    app = FCGIApp(host=str(jail_ip), port=plugin.plugin_port)
#    env = request.META.copy()
#    env.pop('wsgi.file_wrapper', None)
#    env.pop('wsgi.version', None)
#    env.pop('wsgi.input', None)
#    env.pop('wsgi.errors', None)
#    env.pop('wsgi.multiprocess', None)
#    env.pop('wsgi.run_once', None)
#    env['SCRIPT_NAME'] = env['PATH_INFO']
#    args = request.POST if request.method == "POST" else request.GET
#    status, headers, body, raw = app(env, args=args)
#
#    resp = HttpResponse(body)
#    for header, value in headers:
#        resp[header] = value
#    return resp
