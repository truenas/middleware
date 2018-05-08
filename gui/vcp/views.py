#+
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

import freenasUI.vcp.utils as utils

from django.shortcuts import render
from django.utils.translation import ugettext as _
from freenasUI.freeadmin.views import JsonResp
from freenasUI.vcp.forms import VcenterConfigurationForm, VcenterAuxSettingsForm
from freenasUI.vcp import models
from django.http import HttpResponseRedirect

from freenasUI.system.models import (
    Settings,
)

# TODO: CHANGE ALL OBJECTS.LATEST TO .GET(PK=1)
# VCENTER MODEL FIELDS - vc_management_ip, vc_ip, vc_port, vc_username, vc_password, vc_version, vc_state
def vcp_home(request):
    aux_enable_https = models.VcenterAuxSettings.objects.latest('id')
    obj = models.VcenterConfiguration.objects.latest('id')
    if request.method == 'POST':
        form = VcenterConfigurationForm(request.POST, instance=obj)
        if form.is_valid():

            if form.install_plugin():
                obj.vc_management_ip = form.cleaned_data.get('vc_management_ip')
                obj.vc_ip = form.cleaned_data.get('vc_ip')
                obj.vc_port = form.cleaned_data.get('vc_port')
                obj.vc_username = form.cleaned_data.get('vc_username')
                obj.vc_password = form.cleaned_data.get('vc_password')
                obj.vc_version = utils.get_plugin_version()
                obj.vc_state = 'INSTALLED'
                obj.save()
            else:
                return JsonResp(
                    request, error=True, message=_(
                        form.vcp_status))
        else:
            form.is_update_needed()
            return render(
                request,
                "vcp/index.html",
                {
                    'form': form,
                    'aux_enable_https': aux_enable_https,
                }
            )

    form = VcenterConfigurationForm(instance=obj)
    if obj.vc_state == 'INSTALLED':
        form.fields['vc_ip'].widget.attrs['readonly'] = True
    form.is_update_needed()

    return render(
        request,
        "vcp/index.html",
        {
            'form': form,
            'aux_enable_https': aux_enable_https,
        }
    )


def vcp_vcenterauxsettings(request):
    vcpaux = models.VcenterAuxSettings.objects.latest('id')

    if request.method == "POST":
        form = VcenterAuxSettingsForm(request.POST, instance=vcpaux)
        if form.is_valid():
            form.save()
            events = []
            form.done(request, events)
            return JsonResp(
                request,
                message=_("vCenter Auxiliary Settings successfully edited."),
                events=events,
            )
        else:
            return JsonResp(request, form=form)
    else:
        form = VcenterAuxSettingsForm(instance=vcpaux)
    return render(request, 'vcp/aux_settings.html', {'form': form})


def vcp_upgrade(request):
    if request.method == 'POST':
        form = VcenterConfigurationForm(request.POST)
        if form.is_valid():
            form.is_update_needed()
            if form.vcp_is_update_available is False:
                return JsonResp(
                    request, error=True, message=_(
                        "There are No updates available at this time."))
            if form.upgrade_plugin():
                return HttpResponseRedirect("/legacy/vcp/home")
            else:
                return JsonResp(
                    request, error=True, message=_(
                        form.vcp_status))
        else:
            form.is_update_needed()
            form.fields['vc_ip'].widget.attrs['readonly'] = True
    return render(request, "vcp/index.html", {'form': form})


def vcp_uninstall(request):
    if request.method == 'POST':
        form = VcenterConfigurationForm(request.POST)
        if form.is_valid():
            if form.uninstall_plugin():
                return HttpResponseRedirect("/legacy/vcp/home")
            else:
                return JsonResp(
                    request, error=True, message=_(
                        form.vcp_status))
        else:
            form.is_update_needed()
            form.fields['vc_ip'].widget.attrs['readonly'] = True
    return render(request, "vcp/index.html", {'form': form})


def vcp_repair(request):
    if request.method == 'POST':
        form = VcenterConfigurationForm(request.POST)
        if form.is_valid():
            if form.repair_plugin():
                return HttpResponseRedirect("/legacy/vcp/home")
            else:
                return JsonResp(
                    request, error=True, message=_(
                        form.vcp_status))
        else:
            form.is_update_needed()
            form.fields['vc_ip'].widget.attrs['readonly'] = True
    return render(request, "vcp/index.html", {'form': form})
