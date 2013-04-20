#+
# Copyright 2013 iXsystems, Inc.
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
import logging   

from django.http import HttpResponse 
from django.shortcuts import render
from django.utils import simplejson
from django.utils.translation import ugettext as _

from freenasUI.freeadmin.views import JsonResp   
from freenasUI.middleware.notifier import notifier
from freenasUI.jails import forms
from freenasUI.jails import models
from freenasUI.common.warden import Warden, \
    WARDEN_STATUS_RUNNING, \
    WARDEN_STATUS_STOPPED

log = logging.getLogger("jails.views")

def jails_home(request):

    try:
        jailsconf = models.JailsConfiguration.objects.order_by("-id")[0].id
    except IndexError:
        jailsconf = models.JailsConfiguration.objects.create().id

    return render(request, 'jails/index.html', {
        'focused_form': request.GET.get('tab', 'jails'),
         'jailsconf': jailsconf
    })


def jail_edit(request, id):

    try:
        jail = models.Jails.objects.get(id=id)
    except Exception, e:
        jail = None 

    if request.method == 'POST':
        form = forms.JailsEditForm(request.POST, instance=jail)
        if form.is_valid():
            form.save() 
            return JsonResp(request,
                message=_("Jail successfully edited."))
    else:
        form = forms.JailsEditForm(instance=jail)

    return render(request, 'jails/edit.html', { 
        'form': form
    })


def jail_storage(request, id=-1):

    try:
        jail = models.Jails.objects.get(id=id)
    except Exception, e:
        jail = None 

    if request.method == 'POST':
        form = forms.NullMountPointForm(request.POST, jail=jail)
        if form.is_valid():
            form.save()
            return JsonResp(request,
                message=_("Storage successfully added."))
    else:
        form = forms.NullMountPointForm(jail=jail)

    return render(request, 'jails/storage.html', {
        'form': form,
    }) 
    

def jail_start(request, id):

    try:
        jail = models.Jails.objects.get(id=id)
    except Exception, e:
        jail = None 

    if jail and jail.jail_status == WARDEN_STATUS_STOPPED:
        Warden().start(jail=jail.jail_host)

    resp = render(request, "jails/start.html", { })
    resp.content = (
        "<html><body>"
        + "Jail successfully started." +
        "</boby></html>"
    )

    return resp


def jail_stop(request, id):

    try:
        jail = models.Jails.objects.get(id=id)
    except Exception, e:
        jail = None 

    if jail and jail.jail_status == WARDEN_STATUS_RUNNING:
        Warden().stop(jail=jail.jail_host)

    resp = render(request, "jails/stop.html", { })
    resp.content = (
        "<html><body>"
        + "Jail successfully stopped." +
        "</boby></html>"
    )

    return resp

def jail_delete(request, id):

    try:
        jail = models.Jails.objects.get(id=id)
    except Exception, e:
        jail = None 

    if jail and jail.jail_status == WARDEN_STATUS_RUNNING:
        Warden().delete(jail=jail.jail_host)

    return JsonResp(request, message=_("Jail successfully deleted."))

def jail_auto(request, id):
    log.debug("XXX: jail_auto()")
    return render(request, 'jails/auto.html', { }) 

def jail_checkup(request, id):
    log.debug("XXX: jail_checkup()")
    return render(request, 'jails/checkup.html', { }) 

def jail_details(request, id):
    log.debug("XXX: jail_details()")
    return render(request, 'jails/details.html', { }) 

def jail_export(request, id):
    log.debug("XXX: jail_export()")
    return render(request, 'jails/export.html', { }) 

def jail_import(request, id):
    log.debug("XXX: jail_import()")
    return render(request, 'jails/import.html', { }) 

def jail_options(request, id):
    log.debug("XXX: jail_options()")
    return render(request, 'jails/options.html', { }) 

def jail_pkgs(request, id):
    log.debug("XXX: jail_pkgs()")
    return render(request, 'jails/pkgs.html', { }) 

def jail_pbis(request, id):
    log.debug("XXX: jail_pbis()")
    return render(request, 'jails/pbis.html', { }) 

def jail_zfsmksnap(request, id):
    log.debug("XXX: jail_zfsmksnap()")
    return render(request, 'jails/zfsmksnap.html', { }) 

def jail_zfslistclone(request, id):
    log.debug("XXX: jail_zfslistclone()")
    return render(request, 'jails/zfslistclone.html', { }) 

def jail_zfslistsnap(request, id):
    log.debug("XXX: jail_zfslistsnap()")
    return render(request, 'jails/zfslistsnap.html', { }) 

def jail_zfsclonesnap(request, id):
    log.debug("XXX: jail_zfsclonesnap()")
    return render(request, 'jails/zfsclonesnap.html', { }) 

def jail_zfscronsnap(request, id):
    log.debug("XXX: jail_zfscronsnap()")
    return render(request, 'jails/zfscronsnap.html', { }) 

def jail_zfsrevertsnap(request, id):
    log.debug("XXX: jail_zfsrevertsnap()")
    return render(request, 'jails/zfsrevertsnap.html', { }) 

def jail_zfsrmclonesnap(request, id):
    log.debug("XXX: jail_zfsrmclonesnap()")
    return render(request, 'jails/zfsrmclonesnap.html', { }) 

def jail_zfsrmsnap(request, id):
    log.debug("XXX: jail_zfsrmsnap()")
    return render(request, 'jails/zfsrmsnap.html', { }) 
