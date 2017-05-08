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

from freenasUI.directoryservice import forms, models, utils
from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier
from freenasUI.services.models import services

log = logging.getLogger("directoryservice.views")


def directoryservice_home(request):

    view = appPool.hook_app_index('directoryservice', request)
    view = [_f for _f in view if _f]
    if view:
        return view[0]

    try:
        activedirectory = models.ActiveDirectory.objects.order_by("-id")[0]
    except:
        activedirectory = models.ActiveDirectory.objects.create()

    try:
        ldap = models.LDAP.objects.order_by("-id")[0]
    except:
        ldap = models.LDAP.objects.create()

    try:
        nis = models.NIS.objects.order_by("-id")[0]
    except:
        nis = models.NIS.objects.create()

    try:
        nt4 = models.NT4.objects.order_by("-id")[0]
    except:
        nt4 = models.NT4.objects.create()

    try:
        ks = models.KerberosSettings.objects.order_by("-id")[0]
    except:
        ks = models.KerberosSettings.objects.create()

    return render(request, 'directoryservice/index.html', {
        'focus_form': request.GET.get('tab', 'directoryservice'),
        'activedirectory': activedirectory,
        'ldap': ldap,
        'nis': nis,
        'nt4': nt4,
        'kerberossettings': ks,
    })


def directoryservice_kerberosrealm(request, id):
    kr = models.KerberosRealm.objects.get(pk=id)

    if request.method == "POST":
        form = forms.KerberosRealmForm(request.POST, instance=kr)
        if form.is_valid():
            form.save()
            return JsonResp(
                request,
                message="Kerberos Realm successfully updated."
            )
        else:
            return JsonResp(request, form=form)
    else:
        form = forms.KerberosRealmForm(instance=kr)

    return render(request, 'directoryservice/kerberos_realm.html', {
        'form': form,
        'inline': True
    });


def directoryservice_kerberoskeytab(request, id=None):
    kt = None
    mf = forms.KerberosKeytabCreateForm

    if id != None:
        kt = models.KerberosKeytab.objects.get(pk=id)
        mf = forms.KerberosKeytabEditForm

    if request.method == "POST":
        form = mf(request.POST, request.FILES, instance=kt)
        if form.is_valid():
            form.save()
            return JsonResp(
                request,
                message="Kerberos Keytab successfully updated."
            )
        else:
            return JsonResp(request, form=form)

    else:
        form = mf(instance=kt)

    return render(request, 'directoryservice/kerberos_keytab.html', {
        'form': form,
        'inline': True
    });


def directoryservice_kerberoskeytab_edit(request, id):
    return directoryservice_kerberoskeytab(request, id)


def directoryservice_kerberoskeytab_add(request):
    return directoryservice_kerberoskeytab(request)


def directoryservice_kerberoskeytab_delete(request, id):
    kt = models.KerberosKeytab.objects.get(pk=id)
    form = forms.KerberosKeytabEditForm(instance=kt)

    if request.method == "POST":
        try:
            kt.delete() 
            notifier().start("ix-kerberos")
            return JsonResp(
                request,
                message="Kerberos Keytab successfully deleted."
            )
        except MiddlewareError:
            raise
        except Exception as e:
            return JsonResp(request, error=True, message=repr(e))

    return render(request, 'directoryservice/kerberos_keytab.html', {
        'form': form,
        'inline': True
    });


def get_directoryservice_status():
    data = {}
    ad_enable = False
    dc_enable = False
    ldap_enable = False
    nis_enable = False
    nt4_enable = False

    ad = models.ActiveDirectory.objects.all()
    if ad and ad[0]:
        ad_enable = ad[0].ad_enable

    ldap = models.LDAP.objects.all()
    if ldap and ldap[0]:
        ldap_enable = ldap[0].ldap_enable

    nis = models.NIS.objects.all()
    if nis and nis[0]:
        nis_enable = nis[0].nis_enable

    nt4 = models.NT4.objects.all()
    if nt4 and nt4[0]:
        nt4_enable = nt4[0].nt4_enable

    svc = services.objects.get(srv_service='domaincontroller')
    if svc:
        dc_enable = svc.srv_enable

    data['ad_enable'] = ad_enable
    data['dc_enable'] = dc_enable
    data['ldap_enable'] = ldap_enable
    data['nis_enable'] = nis_enable
    data['nt4_enable'] = nt4_enable 

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
            return JsonResp(request, form=form)
    else:
        form = forms.idmap_ad_Form(instance=idmap_ad)

    return render(request, 'directoryservice/idmap_ad.html', {
        'form': form
    })


def directoryservice_idmap_adex(request, id):
    idmap_ad = models.idmap_adex.objects.get(id=id)

    if request.method == "POST":
        form = forms.idmap_adex_Form(request.POST, instance=idmap_ad)
        if form.is_valid():
            form.save()
            return JsonResp(
                request,
                message="Idmap adex successfully edited."
            )
        else:
            return JsonResp(request, form=form)
    else:
        form = forms.idmap_adex_Form(instance=idmap_ad)

    return render(request, 'directoryservice/idmap_adex.html', {
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
            return JsonResp(request, form=form)
    else:
        form = forms.idmap_autorid_Form(instance=idmap_autorid)

    return render(request, 'directoryservice/idmap_autorid.html', {
        'form': form
    })


def directoryservice_idmap_fruit(request, id):
    idmap_fruit = models.idmap_fruit.objects.get(id=id)

    if request.method == "POST":
        form = forms.idmap_fruit_Form(request.POST, instance=idmap_fruit)
        if form.is_valid(): 
            form.save()
            return JsonResp(
                request,
                message="Idmap fruit successfully edited."
            )
        else:
            return JsonResp(request, form=form)
    else:
        form = forms.idmap_fruit_Form(instance=idmap_fruit)

    return render(request, 'directoryservice/idmap_fruit.html', {
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
            return JsonResp(request, form=form)
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
            return JsonResp(request, form=form)
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
            return JsonResp(request, form=form)
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
            return JsonResp(request, form=form)
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
            return JsonResp(request, form=form)
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
            return JsonResp(request, form=form)
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
            return JsonResp(request, form=form)
    else:
        form = forms.idmap_tdb2_Form(instance=idmap_tdb2)

    return render(request, 'directoryservice/idmap_tdb2.html', {
        'form': form
    })


def directoryservice_idmap_backend(request, obj_type, obj_id, idmap_type):
    data = utils.get_idmap(obj_type, obj_id, idmap_type)
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
