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
import logging
import os

from django.http import HttpResponse  
from django.shortcuts import render
from django.utils.translation import ugettext_lazy as _

from freenasUI.directoryservice import forms, models, utils
from freenasUI.freeadmin.options import FreeBaseInlineFormSet
from freenasUI.freeadmin.views import JsonResp
from freenasUI.services.models import services

log = logging.getLogger("directoryservice.views")

def directoryservice_home(request):
    activedirectory = models.ActiveDirectory.objects.order_by("-id")[0]
    ldap = models.LDAP.objects.order_by("-id")[0]
    nis = models.NIS.objects.order_by("-id")[0]
    nt4 = models.NT4.objects.order_by("-id")[0]

    return render(request, 'directoryservice/index.html', {
        'focus_form': request.GET.get('tab', 'directoryservice'),
        'activedirectory': activedirectory,
        'ldap': ldap, 
        'nis': nis, 
        'nt4': nt4
    })


def directoryservice_activedirectory(request):
    activedirectory = models.ActiveDirectory.objects.order_by("-id")[0]

    if request.method == "POST":
        form = forms.ActiveDirectoryForm(request.POST, instance=activedirectory)
        if form.is_valid(): 
            form.save()
            return JsonResp(
                request,
                message="Active Directory successfully edited."
            )
    else:
        form = forms.ActiveDirectoryForm(instance=activedirectory)

    return render(request, 'directoryservice/activedirectory.html', {
        'activedirectory': activedirectory,
        'form': form,
        'inline': True
    })


def directoryservice_ldap(request):
    ldap = models.LDAP.objects.order_by("-id")[0]

    if request.method == "POST":
        form = forms.LDAPForm(request.POST, instance=ldap)
        if form.is_valid(): 
            form.save()
            return JsonResp(
                request,
                message="LDAP successfully edited."
            )
    else:
        form = forms.LDAPForm(instance=ldap)

    return render(request, 'directoryservice/ldap.html', {
        'ldap': ldap,
        'form': form,
        'inline': True
    })


def directoryservice_nt4(request):
    nt4 = models.NT4.objects.order_by("-id")[0]

    if request.method == "POST":
        form = forms.NT4Form(request.POST, instance=nt4)
        if form.is_valid(): 
            form.save()
            return JsonResp(
                request,
                message="NT4 successfully edited."
            )
    else:
        form = forms.NT4Form(instance=nt4)

    return render(request, 'directoryservice/nt4.html', {
        'nt4': nt4,
        'form': form,
        'inline': True
    })


def directoryservice_nis(request):
    nis = models.NT4.objects.order_by("-id")[0]

    if request.method == "POST":
        form = forms.NISForm(request.POST, instance=nis)
        if form.is_valid(): 
            form.save()
            return JsonResp(
                request,
                message="NIS successfully edited."
            )
    else:
        form = forms.NISForm(instance=nis)

    return render(request, 'directoryservice/nis.html', {
        'nis': nis,
        'form': form,
        'inline': True
    })


def get_directoryservice_status():
    data = {}

    ad = models.ActiveDirectory.objects.all()[0] 
    ldap = models.LDAP.objects.all()[0]
    nis = models.NIS.objects.all()[0]
    nt4 = models.NT4.objects.all()[0]
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


def directoryservice_idmap_ad(request, id):
    idmap_ad = models.idmap_ad.objects.get(id=id)

    if request.method == "POST":
        form = forms.idmap_ad_Form(request.POST, instance=idmap_ad)
        if form.is_valid(): 
            form.save()
            return JsonResp(
                request,
                message="Idmap ad successfully edited."
            )
    else:
        form = forms.idmap_ad_Form(instance=idmap_ad)

    return render(request, 'directoryservice/idmap_ad.html', {
        'form': form
    })


def directoryservice_idmap_autorid(request, id):
    idmap_autorid = models.idmap_autorid.objects.get(id=id)

    if request.method == "POST":
        form = forms.idmap_autorid_Form(request.POST, instance=idmap_autorid)
        if form.is_valid(): 
            form.save()
            return JsonResp(
                request,
                message="Idmap autorid successfully edited."
            )
    else:
        form = forms.idmap_autorid_Form(instance=idmap_autorid)

    return render(request, 'directoryservice/idmap_autorid.html', {
        'form': form
    })


def directoryservice_idmap_hash(request, id):
    idmap_hash = models.idmap_hash.objects.get(id=id)

    if request.method == "POST":
        form = forms.idmap_hash_Form(request.POST, instance=idmap_hash)
        if form.is_valid(): 
            form.save()
            return JsonResp(
                request,
                message="Idmap hash successfully edited."
            )
    else:
        form = forms.idmap_hash_Form(instance=idmap_hash)

    return render(request, 'directoryservice/idmap_hash.html', {
        'form': form
    })


def directoryservice_idmap_ldap(request, id):
    idmap_ldap = models.idmap_ldap.objects.get(id=id)

    if request.method == "POST":
        form = forms.idmap_ldap_Form(request.POST, instance=idmap_ldap)
        if form.is_valid(): 
            form.save()
            return JsonResp(
                request,
                message="Idmap ldap successfully edited."
            )
    else:
        form = forms.idmap_ldap_Form(instance=idmap_ldap)

    return render(request, 'directoryservice/idmap_ldap.html', {
        'form': form
    })


def directoryservice_idmap_nss(request, id):
    idmap_nss = models.idmap_nss.objects.get(id=id)

    if request.method == "POST":
        form = forms.idmap_nss_Form(request.POST, instance=idmap_nss)
        if form.is_valid(): 
            form.save()
            return JsonResp(
                request,
                message="Idmap nss successfully edited."
            )
    else:
        form = forms.idmap_nss_Form(instance=idmap_nss)

    return render(request, 'directoryservice/idmap_nss.html', {
        'form': form
    })


def directoryservice_idmap_rfc2307(request, id):
    idmap_rfc2307 = models.idmap_rfc2307.objects.get(id=id)

    if request.method == "POST":
        form = forms.idmap_rfc2307_Form(request.POST, instance=idmap_rfc2307)
        if form.is_valid(): 
            form.save()
            return JsonResp(
                request,
                message="Idmap rfc2307 successfully edited."
            )
    else:
        form = forms.idmap_rfc2307_Form(instance=idmap_rfc2307)

    return render(request, 'directoryservice/idmap_rfc2307.html', {
        'form': form
    })


def directoryservice_idmap_rid(request, id):
    idmap_rid = models.idmap_rid.objects.get(id=id)

    if request.method == "POST":
        form = forms.idmap_rid_Form(request.POST, instance=idmap_rid)
        if form.is_valid(): 
            form.save()
            return JsonResp(
                request,
                message="Idmap rid successfully edited."
            )
    else:
        form = forms.idmap_rid_Form(instance=idmap_rid)

    return render(request, 'directoryservice/idmap_rid.html', {
        'form': form
    })


def directoryservice_idmap_tdb(request, id):
    idmap_tdb = models.idmap_tdb.objects.get(id=id)

    if request.method == "POST":
        form = forms.idmap_tdb_Form(request.POST, instance=idmap_tdb)
        if form.is_valid(): 
            form.save()
            return JsonResp(
                request,
                message="Idmap tdb successfully edited."
            )
    else:
        form = forms.idmap_tdb_Form(instance=idmap_tdb)

    return render(request, 'directoryservice/idmap_tdb.html', {
        'form': form
    })


def directoryservice_idmap_tdb2(request, id):
    idmap_tdb2 = models.idmap_tdb2.objects.get(id=id)

    if request.method == "POST":
        form = forms.idmap_tdb2_Form(request.POST, instance=idmap_tdb2)
        if form.is_valid(): 
            form.save()
            return JsonResp(
                request,
                message="Idmap tdb2 successfully edited."
            )
    else:
        form = forms.idmap_tdb2_Form(instance=idmap_tdb2)

    return render(request, 'directoryservice/idmap_tdb2.html', {
        'form': form
    })


def directoryservice_idmap_backend(request, obj_type, idmap_type):
    data = utils.get_idmap(obj_type, idmap_type)
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
