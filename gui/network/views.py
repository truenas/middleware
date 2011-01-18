#+
# Copyright 2010 iXsystems
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
# $FreeBSD$
#####################################################################

from freenasUI.network.forms import * 
from freenasUI.network.models import * 
from freenasUI.network.views import * 
from django.forms.models import modelformset_factory
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.contrib.auth import authenticate, login, logout
from django.template import RequestContext
from django.http import Http404
from django.views.generic.list_detail import object_detail, object_list
from django.views.generic.create_update import update_object, delete_object
from freenasUI.middleware.notifier import notifier
import os, commands

## Network Section

@login_required
def network(request, objtype = None):
    gc = GlobalConfigurationForm(data = GlobalConfiguration.objects.order_by("-id").values()[0])
    if objtype != None:
        focus_form = objtype
    else:
        focus_form = 'gc'
    interfaces = InterfacesForm()
    vlan = VLANForm()
    lagg = LAGGInterfaceForm()
    staticroute = StaticRouteForm()
    int_list = Interfaces.objects.order_by("-id").values()
    vlan_list = VLAN.objects.order_by("-id").values()
    lagg_list = LAGGInterface.objects.order_by("-id").all()
    sr_list = StaticRoute.objects.order_by("-id").values()
    errform = ""
    if request.method == 'POST':
        if objtype == 'configuration':
            gc = GlobalConfigurationForm(request.POST)
            if gc.is_valid():
                gc.save()
        elif objtype == 'int':
            interfaces = InterfacesForm(request.POST)
            if interfaces.is_valid():
                interfaces.save()
            else:
                errform = 'int'
        elif objtype == 'vlan':
            vlan = VLANForm(request.POST)
            if vlan.is_valid():
                vlan.save()
            else:
                errform = 'vlan'
        elif objtype == 'lagg':
            lagg = LAGGInterfaceForm(request.POST)
            if lagg.is_valid():
                # Search for a available slot for laggX interface
                interface_names = Interfaces.objects.all().values('int_interface')
                candidate_index = 0
                while ("lagg%d" % (candidate_index)) in interface_names:
                    candidate_index = candidate_index + 1
                lagg_name = "lagg%d" % (candidate_index)
                lagg_protocol = lagg.cleaned_data['lagg_protocol']
                lagg_member_list = lagg.cleaned_data['lagg_interfaces']
                # Step 1: Create an entry in interface table that represents the lagg interface
                lagg_interface = Interfaces(int_interface = lagg_name, int_name = lagg_name, int_dhcp = True, int_ipv6auto = False)
                lagg_interface.save()
                # Step 2: Write associated lagg attributes
                lagg_interfacegroup = LAGGInterface(lagg_interface = lagg_interface, lagg_protocol = lagg_protocol)
                lagg_interfacegroup.save()
                # Step 3: Write lagg's members in the right order
                order = 0
                for interface in lagg_member_list:
                    lagg_member_entry = LAGGInterfaceMembers(lagg_interfacegroup = lagg_interfacegroup, lagg_ordernum = order, lagg_physnic = interface, lagg_deviceoptions = 'up')
                    lagg_member_entry.save()
                    order = order + 1
                return HttpResponseRedirect('/network/global/lagg/')
            else:
                errform = 'lagg'
        elif objtype == 'sr':
            staticroute = StaticRouteForm(request.POST)
            if staticroute.is_valid():
                staticroute.save()
            else:
                errform = 'sr'
        else:
            raise Http404() 
    variables = RequestContext(request, {
        'gc': gc,
        'interfaces': interfaces,
        'vlan': vlan,
        'lagg': lagg,
        'staticroute': staticroute,
        'int_list': int_list,
        'vlan_list': vlan_list,
        'lagg_list': lagg_list,
        'sr_list': sr_list,
        'errform': errform,
        'focus_form': focus_form,
    })
    return render_to_response('network/index.html', variables)

@login_required
def lagg_members(request, object_id):
    laggmembers = LAGGInterfaceMembers.objects.filter(lagg_interfacegroup = object_id) 
    variables = RequestContext(request, { 'laggmembers': laggmembers, })
    return render_to_response('network/lagg_members.html', variables)

@login_required
def generic_delete(request, object_id, objtype):
    network_model_map = {
        'int':    Interfaces,
        'vlan':   VLAN,
        'lagg':   LAGGInterface,
        'sr':   StaticRoute,
    }
    return delete_object(
        request = request,
        model = network_model_map[objtype],
        post_delete_redirect = '/network/' + objtype + '/view/',
        object_id = object_id, )

@login_required
def generic_update(request, object_id, objtype):
    objtype2form = {
            'int':   ( Interfaces, InterfaceEditForm ),
            'vlan':   ( VLAN, None ),
            'laggint':   ( LAGGInterfaceMembers, LAGGInterfaceMemberForm ),
            'sr':   ( StaticRoute, None ),
            } 
    model, form_class = objtype2form[objtype]
    return update_object(
        request = request,
        model = model, form_class = form_class,
        object_id = object_id, 
        post_save_redirect = '/network/' + objtype + '/view/',
        )

