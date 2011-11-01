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
# $FreeBSD$
#####################################################################

from subprocess import Popen, PIPE

from django.shortcuts import render_to_response, render
from django.http import HttpResponse
from django.utils.translation import ugettext as _

from freeadmin.views import JsonResponse
from freenasUI.network import forms
from freenasUI.network import models

## Network Section
def _lagg_performadd(lagg):
    # Search for a available slot for laggX interface
    interface_names = [v[0] for v in
                       models.Interfaces.objects.all().values_list('int_interface')]
    candidate_index = 0
    while ("lagg%d" % (candidate_index)) in interface_names:
        candidate_index += 1
    lagg_name = "lagg%d" % candidate_index
    lagg_protocol = lagg.cleaned_data['lagg_protocol']
    lagg_member_list = lagg.cleaned_data['lagg_interfaces']
    # Step 1: Create an entry in interface table that
    # represents the lagg interface
    lagg_interface = models.Interfaces(int_interface = lagg_name,
                                int_name = lagg_name,
                                int_dhcp = False,
                                int_ipv6auto = False
                                )
    lagg_interface.save()
    # Step 2: Write associated lagg attributes
    lagg_interfacegroup = models.LAGGInterface(lagg_interface = lagg_interface,
                                        lagg_protocol = lagg_protocol
                                        )
    lagg_interfacegroup.save()
    # Step 3: Write lagg's members in the right order
    order = 0
    for interface in lagg_member_list:
        lagg_member_entry = models.LAGGInterfaceMembers(
                                      lagg_interfacegroup = lagg_interfacegroup,
                                      lagg_ordernum = order,
                                      lagg_physnic = interface,
                                      lagg_deviceoptions = 'up'
                                      )
        lagg_member_entry.save()
        order = order + 1

def network(request):

    try:
        globalconf = models.GlobalConfiguration.objects.order_by("-id")[0].id
    except IndexError:
        globalconf = models.GlobalConfiguration.objects.create().id
    return render(request, 'network/index.html', {
        'focus_form' : request.GET.get('tab','network'),
        'globalconf': globalconf,
    })

def summary(request):

    p1 = Popen(["ifconfig", "-lu"], stdin=PIPE, stdout=PIPE)
    p1.wait()
    int_list = p1.communicate()[0].split('\n')[0].split(' ')
    int_list = filter(lambda y: y not in ('lo0', 'pfsync0', 'pflog0'), int_list)

    ifaces = []
    for iface in int_list:

        p1 = Popen(["ifconfig", iface, "inet"], stdin=PIPE, stdout=PIPE)
        p2 = Popen(["grep", "inet "], stdin=p1.stdout, stdout=PIPE)
        output = p2.communicate()[0]
        if p2.returncode == 0:
            for line in output.split('\n'):
                if not line:
                    continue
                line = line.strip('\t').strip().split(' ')
                netmask = line[3]
                try:
                    netmask = int(netmask, 16)
                    count = 0
                    for i in range(32):
                        if netmask == 0:
                            break
                        count += 1
                        netmask = netmask << 1 & 0xffffffff
                    netmask = count
                except:
                    pass
                ifaces.append({
                    'name': iface,
                    'inet': line[1],
                    'netmask': netmask,
                    'broadcast': line[5] if len(line) > 5 else None,
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

    return render(request, 'network/summary.html', {
        'ifaces': ifaces,
        'nss': nss,
        'default': default,
    })

def interface(request):
    int_list = models.Interfaces.objects.order_by("-id").values()
    return render(request, 'network/interface.html', {
        'int_list': int_list,
    })

def vlan(request):
    vlan_list = models.VLAN.objects.order_by("-id").values()
    return render(request, 'network/vlan.html', {
        'vlan_list': vlan_list,
    })

def staticroute(request):
    sr_list = models.StaticRoute.objects.order_by("-id").values()
    return render(request, 'network/staticroute.html', {
        'sr_list': sr_list,
    })

def lagg(request):
    lagg_list = models.LAGGInterface.objects.order_by("-id").all()
    return render(request, 'network/lagg.html', {
        'lagg_list': lagg_list,
    })

def lagg_add(request):

    lagg = forms.LAGGInterfaceForm()
    if request.method == 'POST':
        lagg = forms.LAGGInterfaceForm(request.POST)
        if lagg.is_valid():
            _lagg_performadd(lagg)
            return JsonResponse(message=_("LAGG successfully added"))

    return render(request, 'network/lagg_add.html', {
        'lagg': lagg,
    })

def globalconf(request):

    extra_context = {}
    gc = forms.GlobalConfigurationForm(
            data = models.GlobalConfiguration.objects.order_by("-id").values()[0],
            auto_id=False
            )
    if request.method == 'POST':
        gc = forms.GlobalConfigurationForm(request.POST,auto_id=False)
        if gc.is_valid():
            gc.save()
            extra_context['saved'] = True

    extra_context.update({
        'gc': gc,
    })
    return render(request, 'network/globalconf.html', extra_context)

def lagg_members(request, object_id):
    laggmembers = models.LAGGInterfaceMembers.objects.filter(
                      lagg_interfacegroup = object_id
                      ) 
    return render(request, 'network/lagg_members.html', {
        'laggmembers': laggmembers,
    })
