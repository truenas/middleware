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
import json
import logging

from django.core.urlresolvers import reverse
from django.shortcuts import render
from django.utils.translation import ugettext as _

from freenasUI.directoryservice.forms import idmap_tdb_Form
from freenasUI.directoryservice.models import idmap_tdb
from freenasUI.directoryservice.views import get_directoryservice_status
from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware.client import client
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.form import handle_middleware_validation
from freenasUI.middleware.notifier import notifier
from freenasUI.services import models
from freenasUI.services.exceptions import ServiceFailed
from freenasUI.services.forms import (
    CIFSForm,
    S3Form
)
from freenasUI.support.utils import fc_enabled
from middlewared.client import ValidationErrors


log = logging.getLogger("services.views")


def index(request):

    view = appPool.hook_app_index('sharing', request)
    view = [_f for _f in view if _f]
    if view:
        return view[0]

    return render(request, 'services/index.html', {
        'toggleCore': request.GET.get('toggleCore'),
    })


def core(request):

    disabled = {}
    extra_services = {}

    try:
        afp = models.AFP.objects.order_by("-id")[0]
    except IndexError:
        afp = models.AFP.objects.create()

    if not notifier().is_freenas():
        try:
            asigra = models.Asigra.objects.order_by("-id")[0]
        except IndexError:
            asigra = models.Asigra.objects.create()
        extra_services['asigra'] = asigra.get_edit_url()

    try:
        models.CIFS.objects.order_by("-id")[0]
    except IndexError:
        models.CIFS.objects.create()

    try:
        dynamicdns = models.DynamicDNS.objects.order_by("-id")[0]
    except IndexError:
        dynamicdns = models.DynamicDNS.objects.create()

    try:
        lldp = models.LLDP.objects.order_by("-id")[0]
    except IndexError:
        lldp = models.LLDP.objects.create()

    try:
        nfs = models.NFS.objects.order_by("-id")[0]
    except IndexError:
        nfs = models.NFS.objects.create()

    try:
        ftp = models.FTP.objects.order_by("-id")[0]
    except IndexError:
        ftp = models.FTP.objects.create()

    try:
        tftp = models.TFTP.objects.order_by("-id")[0]
    except IndexError:
        tftp = models.TFTP.objects.create()

    try:
        rsyncd = models.Rsyncd.objects.order_by("-id")[0]
    except IndexError:
        rsyncd = models.Rsyncd.objects.create()

    try:
        models.S3.objects.order_by("-id")[0]
    except IndexError:
        models.S3.objects.create()

    try:
        smart = models.SMART.objects.order_by("-id")[0]
    except IndexError:
        smart = models.SMART.objects.create()

    try:
        snmp = models.SNMP.objects.order_by("-id")[0]
    except IndexError:
        snmp = models.SNMP.objects.create()

    try:
        ssh = models.SSH.objects.order_by("-id")[0]
    except IndexError:
        ssh = models.SSH.objects.create()

    try:
        ups = models.UPS.objects.order_by("-id")[0]
    except IndexError:
        ups = models.UPS.objects.create()

    try:
        webdav = models.WebDAV.objects.order_by("-id")[0]
    except IndexError:
        webdav = models.WebDAV.objects.create()

    return render(request, 'services/core.html', {
        'urls': json.dumps(dict({
            'cifs': reverse('services_cifs'),
            'afp': afp.get_edit_url(),
            'lldp': lldp.get_edit_url(),
            'nfs': nfs.get_edit_url(),
            'rsync': rsyncd.get_edit_url(),
            'dynamicdns': dynamicdns.get_edit_url(),
            's3': reverse('services_s3'),
            'snmp': snmp.get_edit_url(),
            'ups': ups.get_edit_url(),
            'ftp': ftp.get_edit_url(),
            'tftp': tftp.get_edit_url(),
            'ssh': ssh.get_edit_url(),
            'smartd': smart.get_edit_url(),
            'webdav': webdav.get_edit_url(),
            'netdata': reverse('services_netdata'),
        }, **extra_services)),
        'disabled': json.dumps(disabled),
    })


def iscsi(request):
    gconfid = models.iSCSITargetGlobalConfiguration.objects.all().order_by(
        "-id")[0].id
    return render(request, 'services/iscsi.html', {
        'focus_tab': request.GET.get('tab', ''),
        'gconfid': gconfid,
        'fc_enabled': fc_enabled(),
    })


def enable(request, svc):
    return render(request, "services/enable.html", {
        'svc': svc,
    })


def services_cifs(request):
    try:
        cifs = models.CIFS.objects.all()[0]
    except Exception:
        cifs = models.CIFS()

    try:
        it = idmap_tdb.objects.get(
            idmap_tdb_domain='DS_TYPE_DEFAULT_DOMAIN'
        )

    except Exception:
        it = idmap_tdb()

    if request.method == "POST":
        form = CIFSForm(request.POST, instance=cifs)
        try:
            if form.is_valid():
                form.save()
            else:
                return JsonResp(request, form=form)
        except ValidationErrors as e:
            handle_middleware_validation(form, e)
            return JsonResp(request, form=form)
        except ServiceFailed as e:
            return JsonResp(
                request,
                form=form,
                error=True,
                message=e.value,
                events=["serviceFailed(\"%s\")" % e.service])
        except MiddlewareError as e:
            return JsonResp(
                request,
                form=form,
                error=True,
                message=_("Error: %s") % str(e))

        idmap_form = idmap_tdb_Form(request.POST, instance=it)
        if idmap_form.is_valid():
            idmap_form.save()
            return JsonResp(
                request,
                message=_("SMB successfully updated.")
            )
        else:
            return JsonResp(request, form=idmap_form)

    else:
        form = CIFSForm(instance=cifs)
        idmap_form = idmap_tdb_Form(instance=it)

    idmap_form.fields['idmap_tdb_range_low'].label = _("Idmap Range Low")
    idmap_form.fields['idmap_tdb_range_high'].label = _("Idmap Range High")

    return render(request, 'services/cifs.html', {
        'form': form,
        'idmap_form': idmap_form
    })


def fibrechanneltotarget(request):

    i = 0
    while True:

        fc_port = request.POST.get('fcport-%d-port' % i)
        fc_target = request.POST.get('fcport-%d-target' % i)

        if fc_port is None:
            break

        if fc_target in ('false', False):
            mode = 'INITIATOR'
            fc_target = None
        elif fc_target is None:
            mode = 'DISABLED'
            fc_target = None
        else:
            mode = 'TARGET'
            fc_target = int(fc_target)

        with client as c:
            c.call("fcport.update", fc_port, {"mode": mode, "target": fc_target})

        i += 1

    return JsonResp(
        request,
        message=_('Fibre Channel Ports have been successfully changed.'),
    )


def services_s3(request):
    try:
        s3 = models.S3.objects.all()[0]
    except Exception:
        s3 = models.S3()

    if request.method == "POST":
        form = S3Form(request.POST, instance=s3)
        if form.is_valid():
            try:
                form.save()
                return JsonResp(
                    request,
                    message=_("S3 successfully edited.")
                )
            except ValidationErrors as e:
                handle_middleware_validation(form, e)
                return JsonResp(request, form=form)
        else:
            return JsonResp(request, form=form)

    else:
        form = S3Form(instance=s3)

    s3_ui_url = "http://%s:%s" % (s3.s3_bindip, s3.s3_bindport)
    if s3.s3_bindip == "0.0.0.0":
        s3_ui_url = "http://%s:%s" % (request.META['HTTP_HOST'].split(':')[0], s3.s3_bindport)

    s3_started = notifier().started("s3") and s3.s3_browser

    return render(request, 'services/s3.html', {
        'form': form,
        's3': s3,
        's3_ui_url': s3_ui_url,
        's3_started': s3_started
    })


def services_netdata(request):
    started = notifier().started('netdata')
    return render(request,
                  'services/netdata.html',
                  {
                      'started': started
                  })
