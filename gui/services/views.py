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
import sysctl

from django.shortcuts import render
from django.utils.translation import ugettext as _

from freenasUI.directoryservice.forms import idmap_tdb_Form
from freenasUI.directoryservice.models import (
    idmap_tdb,
    DS_TYPE_CIFS
)
from freenasUI.directoryservice.views import get_directoryservice_status
from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware.notifier import notifier
from freenasUI.services import models
from freenasUI.services.forms import (
    CIFSForm
)
from freenasUI.system.models import Tunable
from freenasUI.support.utils import fc_enabled

log = logging.getLogger("services.views")


def index(request):

    view = appPool.hook_app_index('sharing', request)
    view = filter(None, view)
    if view:
        return view[0]

    return render(request, 'services/index.html', {
        'toggleCore': request.GET.get('toggleCore'),
    })


def core(request):

    disabled = {}

    for key, val in get_directoryservice_status().iteritems():
        if val is True and key != 'dc_enable':
            disabled['domaincontroller'] = {
                'reason': _('A directory service is already enabled.'),
            }
            break

    try:
        afp = models.AFP.objects.order_by("-id")[0]
    except IndexError:
        afp = models.AFP.objects.create()

    try:
        cifs = models.CIFS.objects.order_by("-id")[0]
    except IndexError:
        cifs = models.CIFS.objects.create()

    try:
        domaincontroller = models.DomainController.objects.order_by("-id")[0]
    except IndexError:
        domaincontroller = models.DomainController.objects.create()

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
        s3 = models.S3.objects.order_by("-id")[0]
    except IndexError:
        s3 = models.S3.objects.create()

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
        'urls': json.dumps({
            'cifs': cifs.get_edit_url(),
            'afp': afp.get_edit_url(),
            'lldp': lldp.get_edit_url(),
            'nfs': nfs.get_edit_url(),
            'rsync': rsyncd.get_edit_url(),
            'dynamicdns': dynamicdns.get_edit_url(),
            's3': s3.get_edit_url(),
            'snmp': snmp.get_edit_url(),
            'ups': ups.get_edit_url(),
            'ftp': ftp.get_edit_url(),
            'tftp': tftp.get_edit_url(),
            'ssh': ssh.get_edit_url(),
            'smartd': smart.get_edit_url(),
            'webdav': webdav.get_edit_url(),
            'domaincontroller': domaincontroller.get_edit_url(),
        }),
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
    except:
        cifs = models.CIFS()

    try:
        it = idmap_tdb.objects.get(
            idmap_ds_type=DS_TYPE_CIFS,
            idmap_ds_id=cifs.id
        )

    except Exception:
        it = idmap_tdb()

    if request.method == "POST":
        form = CIFSForm(request.POST, instance=cifs)
        if form.is_valid():
            form.save()
        else:
            return JsonResp(request, form=form)

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
    sysctl_set = {}
    loader = False
    while True:

        fc_port = request.POST.get('fcport-%d-port' % i)
        fc_target = request.POST.get('fcport-%d-target' % i)

        if fc_port is None:
            break

        port = fc_port.replace('isp', '').replace('/', ',')
        if ',' in port:
            port_number, vport = port.split(',', 1)
            mibname = '%s.chan%s' % (port_number, vport)
        else:
            port_number = port
            vport = None
            mibname = port

        role = sysctl.filter('dev.isp.%s.role' % mibname)
        if role:
            role = role[0]
        tun_var = 'hint.isp.%s.role' % mibname

        qs = models.FibreChannelToTarget.objects.filter(fc_port=fc_port)
        if qs.exists():
            fctt = qs[0]
        else:
            fctt = models.FibreChannelToTarget()
            fctt.fc_port = fc_port
        # Initiator mode
        if fc_target in ('false', False):
            if role:
                # From disabled to initiator, just set sysctl
                if role.value == 0:
                    role.value = 2
                # From target to initiator, reload ctld then set to 2
                elif role.value == 1:
                    sysctl_set[mibname] = 2
            fctt.fc_target = None
            fctt.save()
            qs = Tunable.objects.filter(tun_var=tun_var)
            if qs.exists():
                tun = qs[0]
                if tun.tun_value != '2':
                    tun.tun_value = '2'
                    loader = True
                tun.save()
            else:
                tun = Tunable()
                tun.tun_var = tun_var
                tun.tun_value = '2'
                tun.save()
                loader = True
        # Disabled
        elif fc_target is None:
            if role:
                # From initiator to disabled, just set sysctl
                if role.value == 2:
                    role.value = 0
            if fctt.id:
                fctt.delete()
            qs = Tunable.objects.filter(tun_var=tun_var)
            if qs.exists():
                loader = True
                qs.delete()
        # Target mode
        else:
            if role:
                # From initiator to target, first set sysctl
                if role.value == 2:
                    role.value = 0
            fctt.fc_target = models.iSCSITarget.objects.get(id=fc_target)
            fctt.save()
            qs = Tunable.objects.filter(tun_var=tun_var)
            if qs.exists():
                loader = True
                qs.delete()

        i += 1

    if i > 0:
        notifier().reload("iscsitarget")

    for mibname, val in sysctl_set.items():
        role = sysctl.filter('dev.isp.%s.role' % mibname)
        if role:
            role = role[0]
            role.value = val

    if loader:
        notifier().reload('loader')

    return JsonResp(
        request,
        message=_('Fibre Channel Ports have been successfully changed.'),
    )


def services_s3(request):
    try:
        s3 = models.S3.objects.all()[0]
    except:
        s3 = models.S3()

    if request.method == "POST":
        form = S3Form(request.POST, instance=s3)
        if form.is_valid():
            form.save()
        else:
            return JsonResp(request, form=form)

    else:
        form = S3Form(instance=s3)

    return render(request, 'services/s3.html', {
        'form': form,
    })
