#+
# Copyright 2014 iXsystems, Inc.
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
import json
import os

from django.http import HttpResponse  
from django.shortcuts import render

from freenasUI.directoryservice.models import (
    ActiveDirectory,
    LDAP,
    NIS,
    NT4,
)

from freenasUI.services.models import services

def directoryservice_home(request):

    activedirectory = ActiveDirectory.objects.order_by("-id")[0]
    ldap = LDAP.objects.order_by("-id")[0]
    nis = NIS.objects.order_by("-id")[0]
    nt4 = NT4.objects.order_by("-id")[0]

    return render(request, 'directoryservice/index.html', {
        'focus_form': request.GET.get('tab', 'directoryservice'),
        'activedirectory': activedirectory,
        'ldap': ldap, 
        'nis': nis, 
        'nt4': nt4
    })

def get_directoryservice_status():
    data = {}

    ad = ActiveDirectory.objects.all()[0] 
    ldap = LDAP.objects.all()[0]
    nis = NIS.objects.all()[0]
    nt4 = NT4.objects.all()[0]
    svc = services.objects.get(srv_service='domaincontroller')

    data['ad_enable'] = ad.ad_enable
    data['dc_enable'] = svc.srv_enable
    data['ldap_enable'] = ldap.ldap_enable
    data['nis_enable'] = nis.nis_enable
    data['nt4_enable'] = nt4.nt4_enable 

    return data

def directoryservice_status(request):
    data = get_directoryservice_status()
    content = json.dumps(data)
    return HttpResponse(content, content_type="application/json")


def directoryservice_clearcache(request):
    error = False
    errmsg = ''

    os.system(
        "(/usr/local/bin/python "
        "/usr/local/www/freenasUI/tools/cachetool.py expire >/dev/null 2>&1 &&"
        " /usr/local/bin/python /usr/local/www/freenasUI/tools/cachetool.py "
        "fill >/dev/null 2>&1) &")

    return HttpResponse(json.dumps({
        'error': error,
        'errmsg': errmsg,
    }))
