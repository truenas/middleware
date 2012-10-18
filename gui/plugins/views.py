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

from django.shortcuts import render
from django.http import HttpResponse, Http404
from django.utils.translation import ugettext as _

from freenasUI.freeadmin.middleware import public
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware.notifier import notifier
from freenasUI.plugins import models, forms
from freenasUI.plugins.utils.fcgi_client import FCGIApp
from freenasUI.services.models import PluginsJail

import freenasUI.plugins.api_calls


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
    pj = PluginsJail.objects.order_by("-id")[0]
    notifier().change_upload_location(pj.plugins_path)
    if request.method == "POST":
        form = forms.PBIUpdateForm(request.POST, request.FILES)
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
        form = forms.PBIUpdateForm()

    return render(request, "plugins/plugin_update.html", {
        'form': form,
        })


def plugin_install(request):
    pj = PluginsJail.objects.order_by("-id")[0]
    notifier().change_upload_location(pj.plugins_path)
    if request.method == "POST":
        form = forms.PBIUploadForm(request.POST, request.FILES)
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
        form = forms.PBIUploadForm()

    return render(request, "plugins/plugin_install.html", {
        'form': form,
        })


@public
def plugin_fcgi_client(request, name, path):
    """
    This is a view that works as a FCGI client
    It is used for development server (no nginx) for easier development
    """
    qs = models.Plugins.objects.filter(plugin_name=name)
    if not qs.exists():
        raise Http404

    plugin = qs[0]
    jail_ip = PluginsJail.objects.order_by('-id')[0].jail_ipv4address

    app = FCGIApp(host=str(jail_ip), port=plugin.plugin_port)
    env = request.META.copy()
    env.pop('wsgi.file_wrapper', None)
    env.pop('wsgi.version', None)
    env.pop('wsgi.input', None)
    env.pop('wsgi.errors', None)
    env.pop('wsgi.multiprocess', None)
    env.pop('wsgi.run_once', None)
    env['SCRIPT_NAME'] = env['PATH_INFO']
    args = request.POST if request.method == "POST" else request.GET
    status, headers, body, raw = app(env, args=args)

    resp = HttpResponse(body)
    for header, value in headers:
        resp[header] = value
    return resp


def plugins_jail_import(request):
    if request.method == "POST":
        form = forms.JailImportForm(request.POST)

        if form.is_valid():
            jail_path = form.cleaned_data["jail_path"]
            jail_ipv4address = form.cleaned_data["jail_ipv4address"]
            jail_ipv4netmask = form.cleaned_data["jail_ipv4netmask"]
            plugins_path = form.cleaned_data["plugins_path"]

            if not notifier().import_jail(jail_path,
                jail_ipv4address,
                jail_ipv4netmask,
                plugins_path):
                return JsonResp(request,
                    message=_("There was a problem importing the jail."))
            else:
                return JsonResp(request,
                    message=_("Jail successfully imported."))

        else:
            return JsonResp(request, form=form)

    else:
        form = forms.JailImportForm()
        return render(request, "plugins/jail_import.html", {
            "form": form,
            })
