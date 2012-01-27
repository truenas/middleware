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
from django.http import HttpResponseRedirect, HttpResponse
from django.utils import simplejson
from django.utils.translation import ugettext as _

from freenasUI.plugins import models, forms
from freenasUI.middleware.notifier import notifier
from freeadmin.views import JsonResponse, JsonResp

from freenasUI.common.pbi import pbi_delete
from freenasUI.common.jail import Jls, Jexec
from freenasUI.plugins.api_calls import plugins_api_get_info


def plugins_home(request):
    plugins_list = models.Plugins.objects.all()
    return render(request, "plugins/index.html", {
        "plugins_list": plugins_list,
    })


def plugin_edit(request, plugin_id):
    plugin = models.Plugins.objects.filter(id=plugin_id)[0]

    if request.method == 'POST':
        plugins_form = forms.PluginsForm(request.POST, instance=plugin)
        if plugins_form.is_valid():
            plugins_form.save()
            return JsonResponse(message=_("Plugin successfully updated."))
        else:
            plugin = None

    else:
        plugins_form = forms.PluginsForm(instance=plugin)

    return render(request, 'plugins/plugin_edit.html', {
        'plugin_id': plugin_id,
        'form': plugins_form
    })

def plugin_delete(request, plugin_id):
    plugin_id = int(plugin_id)
    plugin = models.Plugins.objects.get(id=plugin_id)

    if request.method == 'POST':
        notifier()._stop_plugins(plugin.plugin_name)
        if notifier().delete_pbi(plugin_id):
            return JsonResp(request,
                message=_("Plugin successfully removed."),
                events=['restartHttpd()']
                )
        else:
            return JsonResp(request, error=True, message=_("Unable to remove plugin."))
    else:
        return render(request, 'plugins/plugin_confirm_delete.html', {
            'plugin': plugin,
        })


def plugin_api_call(request, api_func):
    kwargs = {}
    out = None

    for key in request.GET:
        kwargs[key] = request.GET[key]

    info = plugins_api_get_info(api_func)
    if info[1]:
        out = info[0](info[1], request, **kwargs)

    else: 
        out = info[0](request, **kwargs)

    return HttpResponse(out, mimetype="application/json")
