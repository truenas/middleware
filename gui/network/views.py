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

from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware.notifier import notifier
from freenasUI.network import models
from freenasUI.network.forms import HostnameForm, IPMIForm


def hostname(request):
    try:
        globalconf = models.GlobalConfiguration.objects.order_by("-id")[0]
    except IndexError:
        globalconf = models.GlobalConfiguration.objects.create()
    form = HostnameForm(instance=globalconf, data=request.POST)
    if form.is_valid():
        form.save()
    return JsonResp(
        request,
        form=form,
    )


def ipmi(request):

    if request.method == "POST":
        form = IPMIForm(request.POST)
        if form.is_valid():
            if form.save() == 0:
                return JsonResp(request, message=_("IPMI successfully edited"))
            else:
                return JsonResp(request, error=True, message=_("IPMI failed"))
    else:
        form = IPMIForm()
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


def summary(request):

    p1 = Popen(["ifconfig", "-lu"], stdin=PIPE, stdout=PIPE, encoding='utf8')
    p1.wait()
    int_list = p1.communicate()[0].split('\n')[0].split(' ')
    int_list = [y for y in int_list if y not in (
        'lo0',
        'pfsync0',
        'pflog0',
    )]

    ifaces = {}
    for iface in int_list:

        ifaces[iface] = {'v4': [], 'v6': []}
        p1 = Popen(["ifconfig", iface, "inet"], stdin=PIPE, stdout=PIPE)
        p2 = Popen(["grep", "inet "], stdin=p1.stdout, stdout=PIPE, encoding='utf8')
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
                ifaces[iface]['v4'].append({
                    'inet': line[1],
                    'netmask': netmask,
                    'broadcast': line[5] if len(line) > 5 else None,
                })

        p1 = Popen(["ifconfig", iface, "inet6"], stdin=PIPE, stdout=PIPE)
        p2 = Popen(["grep", "inet6 "], stdin=p1.stdout, stdout=PIPE, encoding='utf8')
        output = p2.communicate()[0]
        if p2.returncode == 0:
            for line in output.split('\n'):
                if not line:
                    continue
                line = line.strip('\t').strip().split(' ')
                ifaces[iface]['v6'].append({
                    'addr': line[1].split('%')[0],
                    'prefixlen': line[3],
                })

    p1 = Popen(["cat", "/etc/resolv.conf"], stdin=PIPE, stdout=PIPE)
    p2 = Popen(["grep", "nameserver"], stdin=p1.stdout, stdout=PIPE, encoding='utf8')
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
    p3 = Popen(["awk", "{print $2}"], stdin=p2.stdout, stdout=PIPE, encoding='utf8')
    p1.wait()
    p2.wait()
    p3.wait()
    default = None
    if p3.returncode == 0:
        output = p3.communicate()[0]
        default = output.split('\n')

    return render(request, 'network/summary.html', {
        'ifaces': ifaces,
        'nss': nss,
        'default': default,
    })
