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
import socket
import struct

from subprocess import Popen, PIPE

from django.shortcuts import render
from django.utils.translation import ugettext as _
from django.http import HttpResponse

from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware.notifier import notifier
from freenasUI.middleware.connector import connection as dispatcher
from freenasUI.network import models
from freenasUI.network.forms import HostnameForm, IPMIForm, InterfacesForm, AliasFormSet


def hostname(request):
    general = dispatcher.call_sync('system.general.get_config')
    form = HostnameForm(initial={'hostname': general['hostname']}, data=request.POST)

    if form.is_valid():
        form.save()

    return JsonResp(
        request,
        form=form,
    )


def empty_alias_formset(request):
    form = AliasFormSet()
    return render(request, 'network/alias_empty_form.html', {
        'form': form
    })


def editinterface(request, interface_name):
    from freenasUI.middleware.connector import connection as dispatcher

    if request.method == "POST":
        form = InterfacesForm(data=request.POST)
        aliases = AliasFormSet(data=request.POST)

        if form.is_valid():
            form.save(method='network.interface.configure')

        import logging
        logging.warning(aliases.cleaned_data)

        def convert_alias(alias):
            return {
                'address': str(alias['address']),
                'netmask': alias['netmask'],
                'type': alias['type']
            }

        final = map(convert_alias, aliases.cleaned_data)
        dispatcher.call_task_sync('network.interface.configure', interface_name, {
            'aliases': final
        })

    else:
        nic = models.Interfaces.objects.get(pk=interface_name)
        form = InterfacesForm(instance=nic)
        aliases = AliasFormSet(initial=nic.aliases)

    return render(request, 'network/editinterface.html', {
        'interface_name': interface_name,
        'form': form,
        'formset': aliases
    })


def ipmi(request):

    if request.method == "POST":
        form = IPMIForm(request.POST)
        if form.is_valid():
            args = {
                'dhcp': form.cleaned_data['dhcp'],
                'address': str(form.cleaned_data['address']),
                'netmask': int(form.cleaned_data['netmask']),
                'gateway': str(form.cleaned_data['gateway']),
                'vlan_id': form.cleaned_data.get('vlan_id')
            }

            if form.cleaned_data.get('password'):
                args['password'] = form.cleaned_data['password']

            import logging
            logging.warning('ipmi args: {0}'.format(args))
            result = dispatcher.call_task_sync(
                'ipmi.configure',
                int(form.cleaned_data.get('channel')),
                args
            )
            if result['state'] == 'FINISHED':
                return JsonResp(request, message=_("IPMI successfully edited"))
            else:
                return JsonResp(request, error=True, message=_("IPMI failed"))
    else:
        initial = dispatcher.call_sync('ipmi.get_config', int(request.GET.get('channel', 1)))
        form = IPMIForm(initial=initial)
    return render(request, 'network/ipmi.html', {
        'form': form,
    })


def network(request):

    tabs = appPool.hook_app_tabs('network', request)
    tabs = sorted(tabs, key=lambda y: y['order'] if 'order' in y else 0)
    return render(request, 'network/index.html', {
        'focus_form': request.GET.get('tab', 'network'),
        'hook_tabs': tabs,
    })
