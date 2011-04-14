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

from subprocess import *

from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import HttpResponse
from django.utils import simplejson
from django.utils.translation import ugettext as _

#TODO: do not import *
from freenasUI.network.forms import * 
from freenasUI.network.models import * 
from freenasUI.network.views import * 

## Network Section

def _lagg_performadd(lagg):
    # Search for a available slot for laggX interface
    interface_names = [v[0] for v in 
                       Interfaces.objects.all().values_list('int_interface')]
    candidate_index = 0
    while ("lagg%d" % (candidate_index)) in interface_names:
        candidate_index += 1
    lagg_name = "lagg%d" % candidate_index
    lagg_protocol = lagg.cleaned_data['lagg_protocol']
    lagg_member_list = lagg.cleaned_data['lagg_interfaces']
    # Step 1: Create an entry in interface table that
    # represents the lagg interface
    lagg_interface = Interfaces(int_interface = lagg_name,
                                int_name = lagg_name,
                                int_dhcp = False,
                                int_ipv6auto = False
                                )
    lagg_interface.save()
    # Step 2: Write associated lagg attributes
    lagg_interfacegroup = LAGGInterface(lagg_interface = lagg_interface,
                                        lagg_protocol = lagg_protocol
                                        )
    lagg_interfacegroup.save()
    # Step 3: Write lagg's members in the right order
    order = 0
    for interface in lagg_member_list:
        lagg_member_entry = LAGGInterfaceMembers(
                                      lagg_interfacegroup = lagg_interfacegroup,
                                      lagg_ordernum = order,
                                      lagg_physnic = interface,
                                      lagg_deviceoptions = 'up'
                                      )
        lagg_member_entry.save()
        order = order + 1

def network(request, objtype = None):

    globalconf = GlobalConfiguration.objects.order_by("-id")[0].id
    variables = RequestContext(request, {
        'focus_form' : request.GET.get('tab','network'),
        'globalconf': globalconf,
    })
    return render_to_response('network/index2.html', variables)

def summary(request):

    p1 = Popen(["ifconfig", "-lu"], stdin=PIPE, stdout=PIPE)
    p1.wait()
    int_list = p1.communicate()[0].split('\n')[0].split(' ')

    if 'lo0' in int_list:
        int_list.remove('lo0')

    ifaces = []
    for iface in int_list:

        p1 = Popen(["ifconfig", iface, "inet"], stdin=PIPE, stdout=PIPE)
        p2 = Popen(["grep", "inet "], stdin=p1.stdout, stdout=PIPE)
        p1.wait()
        p2.wait()
        if p2.returncode == 0:
            output = p2.communicate()[0]
            output = output.strip('\t').strip().split(' ')
            ifaces.append({
                'name': iface,
                'inet': output[1],
                'netmask': output[3],
                'broadcast': output[5],
                })
        #else:
        #    ifaces.append({
        #        'name': iface,
        #        'inet': '-',
        #        'netmask': '-',
        #        'broadcast': '-',
        #        })

    p1 = Popen(["cat", "/etc/resolv.conf"], stdin=PIPE, stdout=PIPE)
    p2 = Popen(["grep", "nameserver"], stdin=p1.stdout, stdout=PIPE)
    p1.wait()
    p2.wait()
    nss = []
    if p2.returncode == 0:
        output = p2.communicate()[0]
        for ns in output.split('\n')[:-1]:
            addr = ns.split(' ')[-1]
            nss.append(addr)

    p1 = Popen(["netstat", "-rn"], stdin=PIPE, stdout=PIPE)
    p2 = Popen(["grep", "^default"], stdin=p1.stdout, stdout=PIPE)
    p3 = Popen(["awk", "{print $2}"], stdin=p2.stdout, stdout=PIPE)
    p1.wait()
    p2.wait()
    p3.wait()
    default = None
    if p3.returncode == 0:
        output = p3.communicate()[0]
        default = output.replace('\n','')

    variables = RequestContext(request, {
        'ifaces': ifaces,
        'nss': nss,
        'default': default,
    })
    return render_to_response('network/summary.html', variables)

def interface(request):

    int_list = Interfaces.objects.order_by("-id").values()

    variables = RequestContext(request, {
        'int_list': int_list,
    })
    return render_to_response('network/interface.html', variables)

def vlan(request):

    vlan_list = VLAN.objects.order_by("-id").values()

    variables = RequestContext(request, {
        'vlan_list': vlan_list,
    })
    return render_to_response('network/vlan.html', variables)

def staticroute(request):

    sr_list = StaticRoute.objects.order_by("-id").values()

    variables = RequestContext(request, {
        'sr_list': sr_list,
    })
    return render_to_response('network/staticroute.html', variables)

def lagg(request):

    lagg_list = LAGGInterface.objects.order_by("-id").all()

    variables = RequestContext(request, {
        'lagg_list': lagg_list,
    })
    return render_to_response('network/lagg.html', variables)

def lagg_add(request):

    lagg = LAGGInterfaceForm()
    if request.method == 'POST':
        lagg = LAGGInterfaceForm(request.POST)
        if lagg.is_valid():
            _lagg_performadd(lagg)
            return HttpResponse(simplejson.dumps(
                       { "error": False,
                         "message": _("%s successfully added") % "LAGG" }),
                       mimetype="application/json"
                       )
            #return render_to_response('network/lagg_add_ok.html')
            #return HttpResponseRedirect('/network/global/lagg/')

    variables = RequestContext(request, {
        'lagg': lagg,
    })
    return render_to_response('network/lagg_add.html', variables)

def globalconf(request):

    extra_context = {}
    gc = GlobalConfigurationForm(
            data = GlobalConfiguration.objects.order_by("-id").values()[0],
            auto_id=False
            )
    if request.method == 'POST':
        gc = GlobalConfigurationForm(request.POST,auto_id=False)
        if gc.is_valid():
            gc.save()
            extra_context['saved'] = True

    extra_context.update({
        'gc': gc,
    })
    variables = RequestContext(request, extra_context)

    return render_to_response('network/globalconf.html', variables)

def lagg_members(request, object_id):
    laggmembers = LAGGInterfaceMembers.objects.filter(
                      lagg_interfacegroup = object_id
                      )
    variables = RequestContext(request, {
        'focused_tab' : 'account',
        'laggmembers': laggmembers,
    })
    return render_to_response('network/lagg_members.html', variables)

def lagg_members2(request, object_id):
    laggmembers = LAGGInterfaceMembers.objects.filter(
                      lagg_interfacegroup = object_id
                      ) 
    variables = RequestContext(request, {
        'laggmembers': laggmembers,
    })
    return render_to_response('network/lagg_members2.html', variables)
