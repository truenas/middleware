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
import json
import logging
import os
import string
import time

from wsgiref.util import FileWrapper
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.translation import ugettext as _

from freenasUI.freeadmin.views import JsonResp
from freenasUI.jails import forms, models
from freenasUI.jails.utils import get_jails_index
from freenasUI.common.sipcalc import sipcalc_type
from freenasUI.common.warden import (
    Warden,
    WARDEN_EXPORT_FLAGS_DIR
)
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier

log = logging.getLogger("jails.views")


def jails_home(request):
    default_iface = notifier().get_default_interface()

    try:
        jailsconf = models.JailsConfiguration.objects.order_by("-id")[0]

    except IndexError:
        jailsconf = models.JailsConfiguration.objects.create()

    if not jailsconf.jc_collectionurl:
        jailsconf.jc_collectionurl = get_jails_index()
        jailsconf.save()

    return render(request, 'jails/index.html', {
        'focus_form': request.GET.get('tab', 'jails.View'),
        'jailsconf': jailsconf,
        'default_iface': default_iface
    })


def jailsconfiguration(request):

    try:
        jc = models.JailsConfiguration.objects.order_by("-id")[0]

    except IndexError:
        jc = models.JailsConfiguration.objects.create()

    if request.method == "POST":
        form = forms.JailsConfigurationForm(request.POST, instance=jc)
        if form.is_valid():
            form.save()
            return JsonResp(
                request,
                message="Jails Configuration successfully updated."
            )
        else:
            return JsonResp(request, form=form)
    else:
        form = forms.JailsConfigurationForm(instance=jc)

    return render(request, 'jails/jailsconfiguration.html', {
        'form': form,
        'inline': True
    })


def jail_edit(request, id):

    jail = models.Jails.objects.get(id=id)

    if request.method == 'POST':
        form = forms.JailsEditForm(request.POST, instance=jail)
        if form.is_valid():
            form.save()
            return JsonResp(
                request,
                message=_("Jail successfully edited.")
            )
    else:
        form = forms.JailsEditForm(instance=jail)

    return render(request, 'jails/edit.html', {
        'form': form
    })


def jail_storage_add(request, jail_id):

    jail = models.Jails.objects.get(id=jail_id)

    if request.method == 'POST':
        form = forms.JailMountPointForm(request.POST, jail=jail)
        if form.is_valid():
            form.save()
            return JsonResp(
                request,
                message=_("Storage successfully added.")
            )
    else:
        form = forms.JailMountPointForm(jail=jail)

    return render(request, 'jails/storage.html', {
        'form': form,
    })


def jail_start(request, id):

    jail = models.Jails.objects.get(id=id)

    if request.method == 'POST':
        try:
            notifier().reload("http")  # Jail IP reflects nginx plugins.conf
            Warden().start(jail=jail.jail_host)
            return JsonResp(
                request,
                message=_("Jail successfully started.")
            )

        except Exception, e:
            return JsonResp(request, error=True, message=repr(e))

    else:
        return render(request, "jails/start.html", {
            'name': jail.jail_host
        })


def jail_stop(request, id):

    jail = models.Jails.objects.get(id=id)

    if request.method == 'POST':
        try:
            Warden().stop(jail=jail.jail_host)
            return JsonResp(
                request,
                message=_("Jail successfully stopped.")
            )

        except Exception, e:
            return JsonResp(request, error=True, message=repr(e))

    else:
        return render(request, "jails/stop.html", {
            'name': jail.jail_host
        })


def jail_restart(request, id):

    jail = models.Jails.objects.get(id=id)

    if request.method == 'POST':
        try:
            Warden().stop(jail=jail.jail_host)
            Warden().start(jail=jail.jail_host)
            return JsonResp(
                request,
                message=_("Jail successfully restarted.")
            )

        except Exception, e:
            return JsonResp(request, error=True, message=repr(e))

    else:
        return render(request, "jails/restart.html", {
            'name': jail.jail_host
        })


def jail_delete(request, id):

    jail = models.Jails.objects.get(id=id)

    if request.method == 'POST':
        try:
            jail.delete()
            return JsonResp(
                request,
                message=_("Jail successfully deleted.")
            )
        except MiddlewareError:
            raise
        except Exception, e:
            return JsonResp(request, error=True, message=repr(e))

    else:
        return render(request, "jails/delete.html", {
            'name': jail.jail_host
        })


def jail_export(request, id):

    jail = models.Jails.objects.get(id=id)
    jailsconf = models.JailsConfiguration.objects.order_by("-id")[0]

    dir = jailsconf.jc_path
    filename = "%s/%s.wdn" % (dir, jail.jail_host)

    Warden().export(
        jail=jail.jail_host, path=dir, flags=WARDEN_EXPORT_FLAGS_DIR
    )

    freenas_build = "UNKNOWN"
    # FIXME
    """
    try:
        with open(VERSION_FILE) as d:
            freenas_build = d.read().strip()
    except:
        pass
    """

    wrapper = FileWrapper(file(filename))
    response = HttpResponse(wrapper, content_type='application/octet-stream')
    response['Content-Length'] = os.path.getsize(filename)
    response['Content-Disposition'] = \
        'attachment; filename=%s-%s-%s.wdn' % (
            jail.jail_host.encode('utf-8'),
            freenas_build,
            time.strftime('%Y%m%d%H%M%S'))

    return response

jail_progress_estimated_time = 600
jail_progress_start_time = 0
jail_progress_percent = 0


def jail_progress(request):
    global jail_progress_estimated_time
    global jail_progress_start_time
    global jail_progress_percent

    data = {
        'size': 0,
        'data': '',
        'state': 'running',
        'eta': 0,
        'percent': 0
    }

    logfile = '/var/tmp/warden.log'
    if os.path.exists(logfile):
        f = open(logfile, "r")
        buf = f.readlines()
        f.close()

        percent = 0
        size = len(buf)
        if size > 0:
            for line in buf:
                if line.startswith('====='):
                    parts = line.split()
                    if len(parts) > 1:
                        percent = parts[1][:-1]

            buf = string.join(buf)
            size = len(buf)

        if not percent:
            percent = 0

        elapsed = 1
        curtime = int(time.time())

        if jail_progress_start_time == 0:
            jail_progress_start_time = curtime
            eta = jail_progress_estimated_time

        else:
            elapsed = curtime - jail_progress_start_time
            eta = jail_progress_estimated_time - elapsed

        if percent > 0 and jail_progress_percent != percent:
            p = float(percent) / 100
            # t = float(p) * jail_progress_estimated_time

            estimated_time = elapsed / p
            eta = estimated_time - elapsed

            jail_progress_estimated_time = estimated_time

        if eta > 3600:
            data['eta'] = "%02d:%02d:%02d" % (eta / 3600, eta / 60, eta % 60)
        elif eta > 0:
            data['eta'] = "%02d:%02d" % (eta / 60, eta % 60)
        else:
            data['eta'] = "00:00"

        data['percent'] = percent
        data['size'] = size
        data['data'] = buf

        jail_progress_percent = percent

        if not os.path.exists("/var/tmp/.jailcreate"):
            data['state'] = 'done'
            jail_progress_estimated_time = 600
            jail_progress_start_time = 0
            jail_progress_percent = 0

    return HttpResponse(json.dumps(data), content_type="application/json")

linux_jail_progress_estimated_time = 600
linux_jail_progress_start_time = 0
linux_jail_progress_percent = 0


#
# XXX HACK XXX
#
# This is just another progress view! We need a univeral means to do this!
#
# XXX HACK XXX
#
def jail_linuxprogress(request):
    global linux_jail_progress_estimated_time
    global linux_jail_progress_start_time
    global linux_jail_progress_percent

    data = {
        'size': 0,
        'data': '',
        'state': 'running',
        'eta': 0,
        'percent': 0
    }

    statusfile = os.environ['EXTRACT_TARBALL_STATUSFILE']
    if os.path.exists("/var/tmp/.templatecreate") and os.path.exists(statusfile):
        percent = 0

        try:
            f = open(statusfile, "r")
            buf = f.readlines()[-1].strip()
            f.close()

            parts = buf.split()
            size = len(parts)
            if size > 2:
                nbytes = float(parts[1])
                total = float(parts[2])
                percent = int((nbytes / total) * 100)
        except:
            pass

        if not percent:
            percent = 0

        elapsed = 1
        curtime = int(time.time())

        if linux_jail_progress_start_time == 0:
            linux_jail_progress_start_time = curtime
            eta = linux_jail_progress_estimated_time

        else:
            elapsed = curtime - linux_jail_progress_start_time
            eta = linux_jail_progress_estimated_time - elapsed

        if percent > 0 and linux_jail_progress_percent != percent:
            p = float(percent) / 100
            # t = float(p) * linux_jail_progress_estimated_time

            estimated_time = elapsed / p
            eta = estimated_time - elapsed

            linux_jail_progress_estimated_time = estimated_time

        if eta > 3600:
            data['eta'] = "%02d:%02d:%02d" % (eta / 3600, eta / 60, eta % 60)
        elif eta > 0:
            data['eta'] = "%02d:%02d" % (eta / 60, eta % 60)
        else:
            data['eta'] = "00:00"

        data['percent'] = percent
        data['size'] = size
        data['data'] = buf

        linux_jail_progress_percent = percent

        if not os.path.exists("/var/tmp/.templatecreate"):
            data['state'] = 'done'
            linux_jail_progress_estimated_time = 600
            linux_jail_progress_start_time = 0
            linux_jail_progress_percent = 0

    return HttpResponse(json.dumps(data), content_type="application/json")


def jail_import(request):
    log.debug("XXX: jail_import()")
    return render(request, 'jails/import.html', {})


def jail_auto(request, id):
    log.debug("XXX: jail_auto()")
    return render(request, 'jails/auto.html', {})


def jail_checkup(request, id):
    log.debug("XXX: jail_checkup()")
    return render(request, 'jails/checkup.html', {})


def jail_details(request, id):
    log.debug("XXX: jail_details()")
    return render(request, 'jails/details.html', {})


def jail_options(request, id):
    log.debug("XXX: jail_options()")
    return render(request, 'jails/options.html', {})


def jail_pkgs(request, id):
    log.debug("XXX: jail_pkgs()")
    return render(request, 'jails/pkgs.html', {})


def jail_pbis(request, id):
    log.debug("XXX: jail_pbis()")
    return render(request, 'jails/pbis.html', {})


def jail_zfsmksnap(request, id):
    log.debug("XXX: jail_zfsmksnap()")
    return render(request, 'jails/zfsmksnap.html', {})


def jail_zfslistclone(request, id):
    log.debug("XXX: jail_zfslistclone()")
    return render(request, 'jails/zfslistclone.html', {})


def jail_zfslistsnap(request, id):
    log.debug("XXX: jail_zfslistsnap()")
    return render(request, 'jails/zfslistsnap.html', {})


def jail_zfsclonesnap(request, id):
    log.debug("XXX: jail_zfsclonesnap()")
    return render(request, 'jails/zfsclonesnap.html', {})


def jail_zfscronsnap(request, id):
    log.debug("XXX: jail_zfscronsnap()")
    return render(request, 'jails/zfscronsnap.html', {})


def jail_zfsrevertsnap(request, id):
    log.debug("XXX: jail_zfsrevertsnap()")
    return render(request, 'jails/zfsrevertsnap.html', {})


def jail_zfsrmclonesnap(request, id):
    log.debug("XXX: jail_zfsrmclonesnap()")
    return render(request, 'jails/zfsrmclonesnap.html', {})


def jail_zfsrmsnap(request, id):
    log.debug("XXX: jail_zfsrmsnap()")
    return render(request, 'jails/zfsrmsnap.html', {})


def jail_info(request, id):
    data = {}

    fields = models.Jails._meta.get_all_field_names()
    for f in fields:
        data[f] = None

    try:
        jail = models.Jails.objects.get(pk=id)
        for k in data.keys():
            data[k] = getattr(jail, k)

    except:
        pass

    content = json.dumps(data)
    return HttpResponse(content, content_type='application/json')


def jail_template_info(request, name):
    data = {}

    fields = models.JailTemplate._meta.get_all_field_names()
    for f in fields:
        data[f] = None

    if name:
        jt = models.JailTemplate.objects.filter(jt_name=name)
        if jt.exists():
            jt = jt[0]
            for k in data.keys():
                data[k] = getattr(jt, k)
            data['jt_instances'] = jt.jt_instances

    content = json.dumps(data)
    return HttpResponse(content, content_type='application/json')


def jail_template_create(request):
    if request.method == "POST":
        form = forms.JailTemplateCreateForm(request.POST)
        if form.is_valid():
            form.save()
            return JsonResp(
                request,
                message=_("Jail Template successfully created.")
            )

    else:
        form = forms.JailTemplateCreateForm()

    return render(request, "jails/jail_template_create.html", {
        'form': form
    })


def jail_template_edit(request, id):
    jt = models.JailTemplate.objects.get(pk=id)

    if request.method == "POST":
        form = forms.JailTemplateEditForm(request.POST, instance=jt)
        if form.is_valid():
            form.save()
            return JsonResp(
                request,
                message=_("Jail Template successfully edited.")
            )

    else:
        form = forms.JailTemplateEditForm(instance=jt)

    return render(request, "jails/jail_template_edit.html", {
        'form': form
    })


def jail_template_delete(request, id):
    jt = models.JailTemplate.objects.get(pk=id)

    if request.method == 'POST':
        try:
            jt.delete()
            return JsonResp(
                request,
                message=_("Jail template successfully deleted.")
            )
        except MiddlewareError:
            raise
        except Exception, e:
            return JsonResp(request, error=True, message=repr(e))

    else:
        return render(request, "jails/delete.html", {
            'name': jt.jt_name
        })


def jailsconfiguration_info(request):
    data = {}

    fields = models.JailsConfiguration._meta.get_all_field_names()
    for f in fields:
        data[f] = None

    try:
        jc = models.JailsConfiguration.objects.all()[0]

    except:
        pass

    for k in data.keys():
        data[k] = getattr(jc, k)

    content = json.dumps(data)
    return HttpResponse(content, content_type='application/json')


def jailsconfiguration_network_info(request):
    data = {
        'jc_ipv4_network': None,
        'jc_ipv4_network_start': None,
        'jc_ipv4_network_end': None,
        'jc_ipv6_network': None,
        'jc_ipv6_network_start': None,
        'jc_ipv6_network_end': None,
    }

    ipv4_iface = notifier().get_default_ipv4_interface()
    if ipv4_iface:
        ipv4_st = sipcalc_type(iface=ipv4_iface)
        if ipv4_st.is_ipv4():
            data['jc_ipv4_network'] = "%s/%d" % (
                ipv4_st.network_address,
                ipv4_st.network_mask_bits
            )
            data['jc_ipv4_network_start'] = str(
                ipv4_st.usable_range[0]).split('/')[0]
            data['jc_ipv4_network_end'] = str(
                ipv4_st.usable_range[1]).split('/')[0]

    ipv6_iface = notifier().get_default_ipv6_interface()
    try:
        iface_info = notifier().get_interface_info(ipv6_iface)
        if iface_info['ipv6'] is None:
            raise Exception

        ipv6_addr = iface_info['ipv6'][0]['inet6']
        if ipv6_addr is None:
            raise Exception

        ipv6_prefix = iface_info['ipv6'][0]['prefixlen']
        if ipv6_prefix is None:
            raise Exception

        ipv6_st = sipcalc_type("%s/%s" % (ipv6_addr, ipv6_prefix))
        if not ipv6_st:
            raise Exception

        if not ipv6_st.is_ipv6():
            raise Exception

        ipv6_st2 = sipcalc_type(ipv6_st.subnet_prefix_masked)
        if not ipv6_st:
            raise Exception

        if not ipv6_st.is_ipv6():
            raise Exception

        data['jc_ipv6_network'] = "%s/%d" % (
            ipv6_st2.compressed_address,
            ipv6_st.prefix_length
        )

        ipv6_st2 = sipcalc_type(ipv6_st.network_range[0])
        data['jc_ipv6_network_start'] = str(
            ipv6_st2.compressed_address).split('/')[0]

        ipv6_st2 = sipcalc_type(ipv6_st.network_range[1])
        data['jc_ipv6_network_end'] = str(
            ipv6_st2.compressed_address).split('/')[0]

    except:
        pass

    content = json.dumps(data)
    return HttpResponse(content, content_type='application/json')
