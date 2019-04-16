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
from collections import OrderedDict
from datetime import date
import base64
import pickle as pickle
import json
import logging
import os
import pytz
import re
import requests
import shutil
import socket
import subprocess
import tarfile
import tempfile
import time
import urllib.parse
import xmlrpc.client

from wsgiref.util import FileWrapper
from django.core.urlresolvers import reverse
from django.http import (
    HttpResponse,
    HttpResponseRedirect,
    StreamingHttpResponse,
)
from django.shortcuts import render, render_to_response
from django.utils.translation import ugettext as _, ungettext
from django.views.decorators.cache import never_cache

from freenasUI.account.models import bsdUsers
from freenasUI.common.system import get_sw_name, get_sw_version
from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware.client import client, ClientException, ValidationErrors
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.form import handle_middleware_validation
from freenasUI.middleware.notifier import notifier
from freenasUI.middleware.util import get_validation_errors, upload_job_and_wait
from freenasUI.middleware.zfs import zpool_list
from freenasUI.network.models import GlobalConfiguration
from freenasUI.storage.models import Volume
from freenasUI.system import forms, models
from freenasUI.system.utils import (
    UpdateHandler,
    factory_restore,
)

DEBUG_JOB = None
VERSION_FILE = '/etc/version'
PGFILE = '/tmp/.extract_progress'
INSTALLFILE = '/tmp/.upgrade_install'
BOOTENV_DELETE_PROGRESS = '/tmp/.bootenv_bulkdelete'
RE_DD = re.compile(r"^(\d+) bytes", re.M | re.S)
PERFTEST_SIZE = 40 * 1024 * 1024 * 1024  # 40 GiB

log = logging.getLogger('system.views')


def _info_humanize(info):
    info['physmem'] = f'{int(info["physmem"] / 1048576)}MB'
    info['loadavg'] = ', '.join(list(map(lambda x: f'{x:.2f}', info['loadavg'])))
    localtz = pytz.timezone(info['timezone'])
    info['datetime'] = info['datetime'].replace(tzinfo=None)
    info['datetime'] = localtz.fromutc(info['datetime'])
    return info


def certificate_common_post_create(action, request, **kwargs):

    form, job, verrors, job_id = None, None, None, None

    if request.session.get('certificate_create'):
        form = getattr(
            forms, request.session['certificate_create']['form']
        )(request.session['certificate_create']['payload'], **kwargs)
        job_id = request.session['certificate_create']['job_id']
        form.is_valid()
        form._middleware_action = action
        verrors = get_validation_errors(job_id)
        if verrors:
            handle_middleware_validation(form, verrors)
        with client as c:
            job = c.call(
                'core.get_jobs',
                [['id', '=', job_id]],
            )

        del request.session['certificate_create']

    if not job:
        if job_id:
            error = f'Job {job_id} does not exist'
        else:
            error = '"certificate_create" key does not exist in session'

        job = {
            'state': 'FAILED',
            'error': error
        }
    else:
        job = job[0]

    return form, job, verrors


def system_info(request):

    with client as c:
        local = _info_humanize(c.call('system.info'))

        if local['license']:
            if local['license']['contract_end'] > date.today():
                days = (local['license']['contract_end'] - date.today()).days
                local['license'] = _('%1s contract, expires at %2s, %3d %4s left' % (
                    _(local['license']['contract_type'].title()),
                    local['license']['contract_end'].strftime("%x"),
                    days,
                    ungettext('day', 'days', days),
                ))
            else:
                local['license'] = _('%1s contract, expired at %2s' % (
                    _(local['license']['contract_type'].title()),
                    local['license']['contract_end'].strftime("%x"),
                ))

        standby = None
        if not notifier().is_freenas() and notifier().failover_licensed():
            try:
                standby = _info_humanize(c.call('failover.call_remote', 'system.info', timeout=2))
            except ClientException:
                pass

    return render(request, 'system/system_info.html', {
        'local': local,
        'standby': standby,
        'is_freenas': notifier().is_freenas(),
    })


def bootenv_datagrid(request):
    with client as c:
        pool = c.call('zfs.pool.query', [['id', '=', 'freenas-boot']])[0]
    bootme = notifier().zpool_parse('freenas-boot')
    zlist = zpool_list(name='freenas-boot')
    try:
        advanced = models.Advanced.objects.order_by('-id')[0]
    except Exception:
        advanced = models.Advanced.objects.create()

    return render(request, 'system/bootenv_datagrid.html', {
        'actions_url': reverse('system_bootenv_datagrid_actions'),
        'resource_url': reverse('api_dispatch_list', kwargs={
            'api_name': 'v1.0',
            'resource_name': 'system/bootenv',
        }),
        'structure_url': reverse('system_bootenv_datagrid_structure'),
        'bootme': bootme,
        'pool': pool,
        'advanced': advanced,
        'zlist': zlist,
    })


def bootenv_datagrid_actions(request):
    onclick = '''function() {
    var mybtn = this;
    for (var i in grid.selection) {
        var data = grid.row(i).data;
        editObject('%s', data.%s, [mybtn,]);
    }
}'''

    onselectafter = '''function(evt, actionName, action) {
    for(var i=0;i < evt.rows.length;i++) {
        var row = evt.rows[i];
        if(%s) {
            query(".grid" + actionName).forEach(function(item, idx) {
                domStyle.set(item, "display", "none");
            });
            break;
        }
     }
}'''
    actions = {
        _('Clone'): {
            'on_click': onclick % (_('Clone'), '_add_url'),
            'button_name': _('Clone'),
        },
        _('Delete'): {
            'on_click': onclick % (_('Delete'), '_delete_url'),
            'on_select_after': onselectafter % (
                'row.data._delete_url === undefined'
            ),
            'button_name': _('Delete'),
        },
        _('DeleteBulk'): {
            'on_click': """
function() {
    var mybtn = this;
    var ids = [];
    for (var i in grid.selection) {
        var data = grid.row(i).data;
        ids.push(data.id);
    }
    editObject('Delete In Bulk',data._deletebulk_url + '?ids=' + ids.join(","),
        [mybtn,]);
}""",
            'on_select_after': """function(evt, actionName, action) {
    var numrows = 0;
    for(var i in evt.grid.selection) {
        var row = evt.grid.row(i);
        if (row.data._deletebulk_url === undefined) {
            numrows = 0;
            break;
        }
        numrows++;
    }
    if(numrows <= 1) {
        query(".grid" + actionName).forEach(function(item, idx) {
            domStyle.set(item, "display", "none");
        });
    } else {
        query(".grid" + actionName).forEach(function(item, idx) {
            domStyle.set(item, "display", "block");
        });
    }
}
""",
            'button_name': _('Delete'),
        },
        _('Activate'): {
            'on_click': onclick % (_('Activate'), '_activate_url'),
            'on_select_after': onselectafter % (
                'row.data._activate_url === undefined'
            ),
            'button_name': _('Activate'),
        },
        _('Rename'): {
            'on_click': onclick % (_('Rename'), '_rename_url'),
            'button_name': _('Rename'),
        },
        _('Keep'): {
            'on_click': onclick % (_('Keep'), '_keep_url'),
            'on_select_after': onselectafter % (
                'row.data._keep_url === undefined'
            ),
            'button_name': _('Keep'),
        },
        _('UnKeep'): {
            'on_click': onclick % (_('Unkeep'), '_un_keep_url'),
            'on_select_after': onselectafter % (
                'row.data._un_keep_url === undefined'
            ),
            'button_name': _('Unkeep'),
        },
    }
    return HttpResponse(
        json.dumps(actions),
        content_type='application/json',
    )


def bootenv_datagrid_structure(request):
    structure = OrderedDict((
        ('name', {'label': _('Name')}),
        ('active', {'label': _('Active')}),
        ('created', {'label': _('Created')}),
        ('keep', {'label': _('Keep')}),
    ))
    return HttpResponse(
        json.dumps(structure),
        content_type='application/json',
    )


def bootenv_activate(request, name):
    if request.method == 'POST':
        with client as c:
            active = c.call('bootenv.activate', name)
        if active is not False:
            return JsonResp(
                request,
                message=_('Boot Environment successfully activated.'),
            )
        return JsonResp(
            request,
            message=_('Failed to activate Boot Environment.'),
        )
    return render(request, 'system/bootenv_activate.html', {
        'name': name,
    })


def bootenv_add(request, source=None):
    if request.method == 'POST':
        form = forms.BootEnvAddForm(request.POST, source=source)
        if form.is_valid():
            try:
                form.save()
                return JsonResp(
                    request,
                    message=_('Boot Environment successfully added.'),
                )
            except ValidationErrors as e:
                handle_middleware_validation(form, e)
        return JsonResp(request, form=form)
    else:
        form = forms.BootEnvAddForm(source=source)
    return render(request, 'system/bootenv_add.html', {
        'form': form,
        'source': source,
    })


def bootenv_scrub(request):
    if request.method == "POST":
        try:
            with client as c:
                c.call('zfs.pool.scrub', 'freenas-boot')
            return JsonResp(request, message=_("Scrubbing the Boot Pool..."))
        except ClientException as e:
            return JsonResp(request, error=True, message=repr(e))
    return render(request, 'system/boot_scrub.html')


def bootenv_scrub_interval(request):
    assert request.method == 'POST'

    interval = request.POST.get('interval')
    if not interval.isdigit():
        return JsonResp(
            request,
            error=True,
            message=_('Interval must be an integer.'),
        )

    with client as c:
        c.call('system.advanced.update', {'boot_scrub': interval})

    return JsonResp(
        request,
        message=_('Scrub interval successfully changed.'),
    )


def bootenv_delete(request, name):
    if request.method == 'POST':
        with client as c:
            delete = c.call('bootenv.delete', name, job=True)
        if delete is not False:
            return JsonResp(
                request,
                message=_('Boot Environment successfully deleted.'),
            )
        return JsonResp(
            request,
            message=_('Failed to delete Boot Environment.'),
        )
    return render(request, 'system/bootenv_delete.html', {
        'name': name,
    })


def bootenv_deletebulk(request):
    names = request.GET.get('ids')
    if '/' in names or ' ' in names:
        raise ValueError("Invalid name")
    names = names.split(',')
    if request.method == 'POST':
        failed = False
        for i, name in enumerate(names):
            with open(BOOTENV_DELETE_PROGRESS, 'w') as f:
                f.write(json.dumps({
                    'current': name,
                    'index': i,
                    'total': len(names),
                }))
            with client as c:
                delete = c.call('bootenv.delete', name, timeout=120)
            if delete is False:
                failed = True
        if os.path.exists(BOOTENV_DELETE_PROGRESS):
            os.unlink(BOOTENV_DELETE_PROGRESS)
        if failed is False:
            return JsonResp(
                request,
                message=_('Boot Environments successfully deleted.'),
            )
        return JsonResp(
            request,
            message=_('Failed to delete Boot Environments.'),
        )
    return render(request, 'system/bootenv_deletebulk.html', {
        'names': names,
        'ids': request.GET.get('ids'),
    })


def bootenv_deletebulk_progress(request):

    if not os.path.exists(BOOTENV_DELETE_PROGRESS):
        return HttpResponse(
            json.dumps({'indeterminate': True}),
            content_type='application/json',
        )

    with open(BOOTENV_DELETE_PROGRESS, 'r') as f:
        data = f.read()

    try:
        data = json.loads(data)
        return HttpResponse(
            json.dumps({
                'indeterminate': False,
                'percent': int((data['index'] / float(data['total'])) * 100.0),
                'details': data['current'],
            }),
            content_type='application/json',
        )
    except Exception:
        log.warn("Unable to load progress status for boot env bulk delete")

    return HttpResponse(
        json.dumps({'indeterminate': True}),
        content_type='application/json',
    )


def bootenv_rename(request, name):
    if request.method == 'POST':
        form = forms.BootEnvRenameForm(request.POST, name=name)
        if form.is_valid():
            try:
                form.save()
                return JsonResp(
                    request,
                    message=_('Boot Environment successfully renamed.'),
                )
            except ValidationErrors as e:
                handle_middleware_validation(form, e)
        return JsonResp(request, form=form)
    else:
        form = forms.BootEnvRenameForm(name=name)
    return render(request, 'system/bootenv_rename.html', {
        'form': form,
        'name': name,
    })


def bootenv_keep(request, name):
    if request.method == 'POST':
        with client as c:
            keep = c.call('bootenv.set_attribute', name, {'keep': True})
        if keep:
            return JsonResp(
                request,
                message=_('Boot Environment successfully Kept.'),
            )
        return JsonResp(
            request,
            message=_('Failed to keep Boot Environment.'),
        )
    return render(request, 'system/bootenv_keep.html', {
        'name': name,
    })


def bootenv_unkeep(request, name):
    if request.method == 'POST':
        with client as c:
            keep = c.call('bootenv.set_attribute', name, {'keep': False})
        if keep:
            return JsonResp(
                request,
                message=_('Boot Environment successfully UnKept.'),
            )
        return JsonResp(
            request,
            message=_('Failed to Unkeep Boot Environment.'),
        )
    return render(request, 'system/bootenv_unkeep.html', {
        'name': name,
    })


def bootenv_pool_attach(request):
    label = request.GET.get('label')
    if request.method == 'POST':
        form = forms.BootEnvPoolAttachForm(request.POST, label=label)
        if form.is_valid() and form.done():
            return JsonResp(
                request,
                message=_('Disk successfully attached.'),
            )
        return JsonResp(request, form=form)
    else:
        form = forms.BootEnvPoolAttachForm(label=label)
    return render(request, 'system/bootenv_pool_attach.html', {
        'form': form,
        'label': label,
    })


def bootenv_pool_attach_progress(request):
    with client as c:
        try:
            job = c.call('core.get_jobs', [('method', '=', 'boot.attach')], {'order_by': ['-id']})[0]
            load = {
                'apply': True,
                'error': job['error'],
                'finished': job['state'] in ('SUCCESS', 'FAILED', 'ABORTED'),
                'indeterminate': True if job['progress']['percent'] is None else False,
                'percent': job['progress'].get('percent'),
                'step': 1,
                'reboot': True,
                'uuid': ['id'],
            }
            desc = job['progress'].get('description')
            if desc:
                load['details'] = desc

        except IndexError:
            load = {}

    return HttpResponse(
        json.dumps(load),
        content_type='application/json',
    )


def bootenv_pool_detach(request, label):
    if request.method == 'POST':
        with client as c:
            c.call('boot.detach', label)
        return JsonResp(
            request,
            message=_("Disk has been successfully detached."))

    return render(request, 'system/bootenv_pool_detach.html', {
        'label': label,
    })


def bootenv_pool_replace(request, label):
    if request.method == 'POST':
        form = forms.BootEnvPoolReplaceForm(request.POST, label=label)
        if form.is_valid() and form.done():
            return JsonResp(
                request,
                message=_('Disk is being replaced.'),
            )
        return JsonResp(request, form=form)
    else:
        form = forms.BootEnvPoolReplaceForm(label=label)
    return render(request, 'system/bootenv_pool_replace.html', {
        'form': form,
    })


def config_restore(request):
    if request.method == "POST":
        factory_restore(request)
        return render(request, 'system/config_ok2.html')
    return render(request, 'system/config_restore.html')


def config_upload(request):

    if request.method == "POST":
        form = forms.ConfigUploadForm(request.POST, request.FILES)

        variables = {
            'form': form,
        }

        if form.is_valid():
            try:
                upload_job_and_wait(request.FILES['config'], 'config.upload')
            except Exception as e:
                form._errors['__all__'] = form.error_class([str(e)])
                return JsonResp(request, form=form)
            else:
                request.session['allow_reboot'] = True
                return render(request, 'system/config_ok.html', variables)

        return render(request, 'system/config_upload.html', variables)
    else:
        FIRMWARE_DIR = '/var/tmp/firmware'
        if os.path.exists(FIRMWARE_DIR):
            if os.path.islink(FIRMWARE_DIR):
                os.unlink(FIRMWARE_DIR)
            if os.path.isdir(FIRMWARE_DIR):
                shutil.rmtree(FIRMWARE_DIR + '/')
        os.mkdir(FIRMWARE_DIR)
        os.chmod(FIRMWARE_DIR, 0o1777)
        form = forms.ConfigUploadForm()

        return render(request, 'system/config_upload.html', {
            'form': form,
        })


def config_save(request):

    if request.method == 'POST':
        form = forms.ConfigSaveForm(request.POST)
        if form.is_valid():
            return JsonResp(
                request,
                message=_("Config download is starting..."),
                events=['window.location="%s?secret=%s&pool_keys=%s"' % (
                    reverse('system_configdownload'),
                    '1' if form.cleaned_data.get('secret') else '0',
                    '1' if form.cleaned_data.get('pool_keys') else '0',
                )]
            )
    else:
        form = forms.ConfigSaveForm()

    return render(request, 'system/config_save.html', {
        'form': form,
    })


def config_download(request):
    secret = request.GET.get('secret') == '1'
    pool_keys = request.GET.get('pool_keys') == '1'
    geli_path = '/data/geli'
    if not secret and not pool_keys:
        filename = '/data/freenas-v1.db'
        bundle = False
    else:
        bundle = True
        filename = tempfile.mkstemp()[1]
        os.chmod(filename, 0o600)
        with tarfile.open(filename, 'w') as tar:
            tar.add('/data/freenas-v1.db', arcname='freenas-v1.db')
            if secret:
                tar.add('/data/pwenc_secret', arcname='pwenc_secret')
            if pool_keys and os.path.exists(geli_path) and os.listdir(geli_path):
                tar.add(geli_path, arcname='geli')

    wrapper = FileWrapper(open(filename, 'rb'))

    hostname = GlobalConfiguration.objects.all().order_by('-id')[0].gc_hostname
    freenas_build = "UNKNOWN"
    try:
        with open(VERSION_FILE) as d:
            freenas_build = d.read().strip()
    except Exception:
        pass

    response = StreamingHttpResponse(
        wrapper, content_type='application/octet-stream'
    )
    response['Content-Length'] = os.path.getsize(filename)
    response['Content-Disposition'] = (
        'attachment; filename="%s-%s-%s.%s"' % (
            hostname,
            freenas_build,
            time.strftime('%Y%m%d%H%M%S'),
            'tar' if bundle else 'db',
        )
    )
    try:
        return response
    finally:
        if bundle:
            os.unlink(filename)


def reporting(request):
    return render(request, 'system/reporting.html')


def home(request):

    tabs = appPool.hook_app_tabs('system', request)
    tabs = sorted(tabs, key=lambda y: y['order'] if 'order' in y else 0)
    return render(request, 'system/index.html', {
        'focus_form': request.GET.get('tab', 'system.SysInfo'),
        'hook_tabs': tabs,
    })


def varlogmessages(request, lines):
    if lines is None:
        lines = 3
    msg = subprocess.Popen(
        ['tail', '-n', str(lines), '/var/log/messages'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).communicate()[0].decode('utf8', 'ignore').strip()
    # "\x07 is invalid XML CDATA, do below to escape it, as well as show some
    # indication of the "console bell" in the webconsole ui
    msg = msg.replace("\x07", "^G")
    return render(request, 'system/status/msg.xml', {
        'msg': msg,
    }, content_type='text/xml')


def top(request):
    top_pipe = os.popen('top')
    try:
        top_output = top_pipe.read()
    finally:
        top_pipe.close()
    return render(request, 'system/status/top.xml', {
        'focused_tab': 'system',
        'top': top_output,
    }, content_type='text/xml')


def reboot_dialog(request):
    if request.method == "POST":
        if notifier().zpool_scrubbing():
            if 'scrub_asked' not in request.session:
                request.session['scrub_asked'] = True
                return render(request, 'system/reboot_dialog2.html')
        request.session['allow_reboot'] = True
        return JsonResp(
            request,
            message=_("Reboot is being issued"),
            events=['window.location="%s"' % reverse('system_reboot')]
        )
    return render(request, 'system/reboot_dialog.html')


def reboot(request):
    """ reboots the system """
    if not request.session.get("allow_reboot"):
        return HttpResponseRedirect('/legacy/')
    request.session.pop("allow_reboot")
    return render(request, 'system/reboot.html', {
        'sw_name': get_sw_name(),
        'sw_version': get_sw_version(),
    })


def reboot_run(request):
    # We need to stop nginx right away to make sure
    # UI dont think we have rebooted while we have not.
    # This could happen if reboot takes too long to shutdown services.
    # See #19458
    # IMPORTANT: do not sync this change stopping the nginx service if
    # we are running on a TrueNAS HA system since that stops the nginx
    # on the soon-to-be master node too! see #20384
    _n = notifier()
    _n.stop("nginx")
    _n.restart("system")
    return HttpResponse('OK')


def shutdown_dialog(request):
    _n = notifier()
    if request.method == "POST":
        if _n.zpool_scrubbing():
            if 'scrub_asked' not in request.session:
                request.session['scrub_asked'] = True
                return render(request, 'system/shutdown_dialog2.html')
        request.session['allow_shutdown'] = True
        if request.POST.get('standby') == 'on':
            try:
                with client as c:
                    c.call('failover.call_remote', 'system.shutdown', [{'delay': 2}])
            except ClientException:
                pass
        return JsonResp(
            request,
            message=_("Shutdown is being issued"),
            events=['window.location="%s"' % reverse('system_shutdown')])
    context = {}
    if not _n.is_freenas() and _n.failover_licensed():
        context['standby'] = True
    return render(request, 'system/shutdown_dialog.html', context)


def shutdown(request):
    """ shuts down the system and powers off the system """
    if not request.session.get("allow_shutdown"):
        return HttpResponseRedirect('/legacy/')
    request.session.pop("allow_shutdown")
    return render(request, 'system/shutdown.html', {
        'sw_name': get_sw_name(),
        'sw_version': get_sw_version(),
    })


def shutdown_run(request):
    notifier().stop("system")
    return HttpResponse('OK')


def testmail(request):

    try:
        kwargs = dict(instance=models.Email.objects.order_by('-id')[0])
    except IndexError:
        kwargs = {}

    fromwizard = False
    data = request.POST.copy()
    for key, value in list(data.items()):
        if key.startswith('system-'):
            fromwizard = True
            data[key.replace('system-', '')] = value

    form = forms.EmailForm(data, **kwargs)
    if not form.is_valid():
        return JsonResp(request, form=form)

    if fromwizard:
        allfield = 'system-__all__'
    else:
        allfield = '__all__'

    if fromwizard:
        email = request.POST.get('system-sys_email')
        errmsg = _('You must provide a Root E-mail')
    else:
        email = bsdUsers.objects.get(bsdusr_username='root').bsdusr_email
        errmsg = _('You must configure the root email (Accounts->Users->root)')
    if not email:
        form.errors[allfield] = form.error_class([errmsg])

        return JsonResp(
            request,
            form=form,
        )

    error = False
    if request.is_ajax():
        sw_name = get_sw_name()
        with client as c:
            mailconfig = form.middleware_prepare()
            try:
                c.call('mail.send', {
                    'subject': f'Test message from your {sw_name}',
                    'text': f'This is a message test from {sw_name}',
                    'to': [email],
                    'timeout': 10,
                }, mailconfig, job=True)
                error = False
            except Exception as e:
                error = True
                errmsg = str(e)
    if error:
        errmsg = _("Your test email could not be sent: %s") % errmsg
    else:
        errmsg = _('Your test email has been sent!')

    form.errors[allfield] = form.error_class([errmsg])
    return JsonResp(
        request,
        form=form,
    )


class DojoFileStore(object):

    def __init__(self, path, dirsonly=False, root="/", filterVolumes=True):
        self.root = os.path.abspath(str(root))
        self.filterVolumes = filterVolumes
        if self.filterVolumes:
            self.mp = [
                os.path.abspath('/mnt/%s' % v.vol_name)
                for v in Volume.objects.all()
            ]

        self.path = os.path.join(self.root, path.replace("..", ""))
        self.path = os.path.abspath(self.path)
        # POSIX allows one or two initial slashes, but treats three or more
        # as single slash.
        if self.path.startswith('//'):
            self.path = self.path[1:]

        self.dirsonly = dirsonly
        if self.dirsonly:
            self._lookupurl = 'system_dirbrowser'
        else:
            self._lookupurl = 'system_filebrowser'

    def items(self):
        if self.path == self.root:
            return self.children(self.path)

        node = self._item(self.path, self.path)
        if node['directory']:
            node['children'] = self.children(self.path)
        return node

    def children(self, entry):
        _children = []
        if not os.path.exists(entry):
            return _children
        for _entry in sorted(os.listdir(entry)):
            # FIXME: better extendable way to exclude files
            if _entry.startswith(".") or _entry == 'md_size':
                continue
            full_path = os.path.join(self.path, _entry)
            if self.filterVolumes and len(
                [
                    f for f in self.mp if (
                        full_path.startswith(f + '/') or full_path == f or
                        full_path.startswith('/mnt')
                    )
                ]
            ) > 0:
                _children.append(self._item(self.path, _entry))
        if self.dirsonly:
            _children = [child for child in _children if child['directory']]
        return _children

    def _item(self, path, entry):
        full_path = os.path.join(path, entry)

        if full_path.startswith(self.root):
            path = full_path.replace(self.root, "/", 1)
        else:
            path = full_path

        if path.startswith("//"):
            path = path[1:]

        isdir = os.path.isdir(full_path)
        item = {
            'name': os.path.basename(full_path),
            'directory': isdir,
            'path': path,
        }
        if isdir:
            item['children'] = True

        item['$ref'] = os.path.abspath(
            reverse(self._lookupurl, kwargs={
                'path': path,
            }) + '?root=%s' % urllib.parse.quote_plus(self.root),
        )
        item['id'] = item['$ref']
        return item


def directory_browser(request, path='/'):
    """ This view provides the ajax driven directory browser callback """

    directories = DojoFileStore(
        path,
        dirsonly=True,
        root=request.GET.get("root", "/"),
    ).items()
    context = directories
    content = json.dumps(context)
    return HttpResponse(content, content_type='application/json')


def file_browser(request, path='/'):
    """ This view provides the ajax driven directory browser callback """

    directories = DojoFileStore(
        path,
        dirsonly=False,
        root=request.GET.get("root", "/"),
    ).items()
    context = directories
    content = json.dumps(context)
    return HttpResponse(content, content_type='application/json')


def manualupdate_running(request):
    uuid = request.GET.get('uuid')
    if not uuid:
        return HttpResponse(uuid, status=202)

    _n = notifier()
    if not _n.is_freenas() and _n.failover_licensed():
        if uuid != "0":
            with client as c:
                job = c.call('failover.call_remote', 'core.get_jobs', [[('id', '=', int(uuid))]])
                if job:
                    job = job[0]
                    if job['state'] == 'SUCCESS':
                        try:
                            c.call('failover.call_remote', 'system.reboot', [{'delay': 2}])
                        except Exception:
                            log.debug('Failed to reboot standby', exc_info=True)
                        return render_to_response('failover/update_standby.html')
                    elif job['state'] == 'FAILED':
                        return JsonResp(request, message=job['error'], error=True)
        else:
            # XXX: very ugly hack to get the legacy manual upgrade thread from the form
            from freenasUI.system.forms import LEGACY_MANUAL_UPGRADE
            if LEGACY_MANUAL_UPGRADE and not LEGACY_MANUAL_UPGRADE.isAlive():
                if not LEGACY_MANUAL_UPGRADE.exception:
                    return render_to_response('failover/update_standby.html')
                else:
                    return JsonResp(request, message=str(LEGACY_MANUAL_UPGRADE.exception), error=True)
    else:
        with client as c:
            job = c.call('core.get_jobs', [('id', '=', int(uuid))])
            if job:
                job = job[0]
                if job['state'] in ('SUCCESS', 'FAILED'):
                    try:
                        os.unlink(job['arguments'][0])
                    except OSError:
                        pass
                if job['state'] == 'SUCCESS':
                    try:
                        c.call('failover.call_remote', 'system.reboot', [{'delay': 2}])
                    except Exception:
                        log.debug('Failed to reboot standby', exc_info=True)
                    return render_to_response('system/done.html')
                elif job['state'] == 'FAILED':
                    return JsonResp(request, message=job['error'], error=True)
            else:
                return JsonResp(request, message=_('Update job not found'), error=True)
    return HttpResponse(uuid, status=202)


def manualupdate_progress(request):

    data = {}
    if os.path.exists(PGFILE):
        with open(PGFILE, 'r') as f:
            last = f.readlines()
            if last:
                step, percent = last[-1].split("|")
                data['step'] = int(step)
                percent = percent.strip()
                if percent:
                    data['percent'] = int(percent)
                else:
                    data['indeterminate'] = True
    elif os.path.exists(INSTALLFILE):
        data = {
            'step': 3,
            'indeterminate': True,
        }

    content = json.dumps(data)
    return HttpResponse(content, content_type='application/json')


def initialwizard_progress(request):
    data = {}
    try:
        with open(forms.WIZARD_PROGRESSFILE, 'rb') as f:
            data = f.read()
        try:
            data = pickle.loads(data)
        except Exception:
            data = {}
    except FileNotFoundError:
        data = {}
    content = json.dumps(data)
    return HttpResponse(content, content_type='application/json')


def restart_httpd(request):
    """ restart httpd """
    notifier().restart("http")
    return HttpResponse('OK')


def restart_httpd_all(request):
    """ restart nginx as well as django (evil)"""
    notifier().restart("http")
    notifier().restart("django")
    return HttpResponse('OK')


def reload_httpd(request):
    """ restart httpd """
    notifier().reload("http")
    return HttpResponse('OK')


def debug(request):
    global DEBUG_JOB

    _n = notifier()
    if request.method == 'GET':
        DEBUG_JOB = None
        if not _n.is_freenas() and _n.failover_licensed():
            try:
                with client as c:
                    c.call('failover.call_remote', 'core.ping')
            except ClientException:
                return render(request, 'system/debug.html', {"failover_down": True})

        return render(request, 'system/debug.html')

    if not DEBUG_JOB:
        # XXX: Dont do this, temporary workaround for legacy UI
        with client as c:
            DEBUG_JOB = c.call('core.download', 'system.debug_download', [], 'debug.tar')
        return HttpResponse('1', status=202)
    with client as c:
        job = c.call('core.get_jobs', [('id', '=', DEBUG_JOB[0])])
    if job and (
        job[0]['state'] not in ('SUCCESS', 'FAILED') and (job[0]['progress']['percent'] or 0) < 90
    ):
        return HttpResponse('1', status=202)
    return render(request, 'system/debug_download.html')


def debug_download(request):
    global DEBUG_JOB
    url = request.GET.get('url')
    if url:
        url = base64.b64decode(url.encode()).decode()
    else:
        url = DEBUG_JOB[1]

    _n = notifier()
    ftime = time.strftime('%Y%m%d%H%M%S')
    if not _n.is_freenas() and _n.failover_licensed():
        filename = f'debug-{ftime}.tar'
    else:
        gconf = GlobalConfiguration.objects.all().order_by('-id')[0]
        filename = f'debug-{gconf.gc_hostname}-{ftime}.txz'

    r = requests.get(f'http://127.0.0.1:6000{url}', stream=True)
    response = StreamingHttpResponse(
        r.iter_content(chunk_size=1024 * 1024),
        content_type='application/octet-stream',
    )
    response['Content-Disposition'] = f'attachment; filename={filename}'
    return response


class UnixTransport(xmlrpc.client.Transport):
    def make_connection(self, addr):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(addr)
        self.sock.settimeout(5)
        return self.sock

    def single_request(self, host, handler, request_body, verbose=0):
        # issue XML-RPC request

        self.make_connection(host)

        try:
            self.sock.send((request_body + "\n").encode('utf8'))
            p, u = self.getparser()

            while 1:
                data = self.sock.recv(1024)
                if not data:
                    break
                p.feed(data)

            self.sock.close()
            p.close()

            return u.close()
        except xmlrpc.client.Fault:
            raise
        except Exception:
            # All unexpected errors leave connection in
            # a strange state, so we clear it.
            self.close()
            raise


class MyServer(xmlrpc.client.ServerProxy):

    def __init__(self, addr):

        self.__handler = "/"
        self.__host = addr
        self.__transport = UnixTransport()
        self.__encoding = None or 'utf-8'
        self.__verbose = 0
        self.__allow_none = False

    def __request(self, methodname, params):
        # call a method on the remote server

        request = xmlrpc.client.dumps(
            params,
            methodname,
            encoding=self.__encoding,
            allow_none=self.__allow_none,
        )

        response = self.__transport.request(
            self.__host,
            self.__handler,
            request,
            verbose=self.__verbose
        )

        if len(response) == 1:
            response = response[0]

        return response

    def __getattr__(self, name):
        if name.startswith('_'):
            return object.__getattribute__(self, name)
        # magic method dispatcher
        return xmlrpc.client._Method(self.__request, name)


@never_cache
def terminal(request):

    sid = int(request.POST.get("s", 0))
    jid = request.POST.get("jid", 0)
    shell = request.POST.get("shell", "")
    k = request.POST.get("k")
    w = int(request.POST.get("w", 80))
    h = int(request.POST.get("h", 24))

    multiplex = MyServer("/var/run/webshell.sock")
    alive = False
    for i in range(3):
        try:
            alive = multiplex.proc_keepalive(sid, jid, shell, w, h)
            break
        except Exception as e:
            notifier().restart("webshell")
            time.sleep(0.5)

    try:
        if alive:
            if k:
                multiplex.proc_write(
                    sid,
                    xmlrpc.client.Binary(bytearray(k.encode('utf-8')))
                )
            time.sleep(0.002)
            content_data = '<?xml version="1.0" encoding="UTF-8"?>' + \
                multiplex.proc_dump(sid)
            response = HttpResponse(content_data, content_type='text/xml')
            return response
        else:
            response = HttpResponse('Disconnected')
            response.status_code = 400
            return response
    except (KeyError, ValueError, TypeError, IndexError, xmlrpc.client.Fault) as e:
        response = HttpResponse('Invalid parameters: %s' % e)
        response.status_code = 400
        return response


def terminal_paste(request):
    return render(request, "system/terminal_paste.html")


def update_save(request):

    assert request.method == 'POST'

    try:
        update = models.Update.objects.order_by('-id')[0]
    except IndexError:
        update = models.Update.objects.create()

    if request.POST.get('autocheck'):
        if request.POST.get('autocheck') == 'true':
            update.upd_autocheck = True
        else:
            update.upd_autocheck = False
        update.save()
        notifier().restart("cron")

    if request.POST.get('train'):
        update.upd_train = request.POST.get('train')
        update.save()

    return HttpResponse(
        json.dumps(True),
        content_type='application/json',
    )


def update_progress(request):

    # If it is HA run update handler on the other node
    if not notifier().is_freenas() and notifier().failover_licensed():
        jobid = request.session.get('failover_update_jobid')
        if jobid:
            with client as c:
                job = c.call('failover.call_remote', 'core.get_jobs', [[('id', '=', jobid)]], {'timeout': 10})[0]
            load = {
                'apply': True if job['method'] == 'update.update' else False,
                'error': job['error'],
                'finished': job['state'] in ('SUCCESS', 'FAILED', 'ABORTED'),
                'indeterminate': True if job['progress']['percent'] is None else False,
                'percent': job['progress'].get('percent'),
                'step': 1,
                'reboot': True,
                'uuid': jobid,
            }
            desc = job['progress'].get('description')
            if desc:
                load['details'] = desc
        else:
            s = notifier().failover_rpc()
            rv = s.updated_handler(None)
            load = rv['data']
    else:
        load = UpdateHandler().load()
    return HttpResponse(
        json.dumps(load),
        content_type='application/json',
    )


def CA_import(request):

    if request.method == "POST":
        form = forms.CertificateAuthorityImportForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                return JsonResp(
                    request,
                    message=_("Certificate Authority successfully imported.")
                )
            except ValidationErrors as e:
                handle_middleware_validation(form, e)
        return JsonResp(request, form=form)

    else:
        form = forms.CertificateAuthorityImportForm()

    return render(request, "system/certificate/CA_import.html", {
        'form': form
    })


def CA_create_internal(request):

    if request.method == "POST":
        form = forms.CertificateAuthorityCreateInternalForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                return JsonResp(
                    request,
                    message=_("Internal Certificate Authority successfully created.")
                )
            except ValidationErrors as e:
                handle_middleware_validation(form, e)
        return JsonResp(request, form=form)

    else:
        form = forms.CertificateAuthorityCreateInternalForm()

    return render(request, "system/certificate/CA_create_internal.html", {
        'form': form
    })


def CA_create_intermediate(request):

    if request.method == "POST":
        form = forms.CertificateAuthorityCreateIntermediateForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                return JsonResp(
                    request,
                    message=_("Intermediate Certificate Authority successfully created.")
                )
            except ValidationErrors as e:
                handle_middleware_validation(form, e)
        return JsonResp(request, form=form)

    else:
        form = forms.CertificateAuthorityCreateIntermediateForm()

    return render(request, "system/certificate/CA_create_intermediate.html", {
        'form': form
    })


def CA_edit(request, id):

    ca = models.CertificateAuthority.objects.get(pk=id)

    if request.method == "POST":
        form = forms.CertificateAuthorityEditForm(request.POST, instance=ca)
        if form.is_valid():
            try:
                form.save()
                return JsonResp(
                    request,
                    message=_("Certificate Authority successfully edited.")
                )
            except ValidationErrors as e:
                handle_middleware_validation(form, e)
        return JsonResp(request, form=form)

    else:
        form = forms.CertificateAuthorityEditForm(instance=ca)

    return render(request, "system/certificate/CA_edit.html", {
        'form': form
    })


def CA_sign_csr(request, id):

    ca = models.CertificateAuthority.objects.get(pk=id)

    if request.method == 'POST':
        form = forms.CertificateAuthoritySignCSRForm(request.POST, instance=ca)
        if form.is_valid():
            try:
                form.save()
                return JsonResp(
                    request,
                    message=_("CSR signed successfully.")
                )
            except ValidationErrors as e:
                handle_middleware_validation(form, e)
        return JsonResp(request, form=form)

    else:
        form = forms.CertificateAuthoritySignCSRForm(instance=ca)

    return render(request, "system/certificate/CA_edit.html", {
        'form': form
    })


def buf_generator(buf):
    for line in buf:
        yield line


def CA_export_certificate(request, id):
    try:
        with client as c:
            ca = c.call('certificateauthority.query', [['id', '=', int(id)]], {'get': True})
        cert = ''.join(ca['chain_list']).strip()
    except Exception as e:
        raise MiddlewareError(e)

    response = StreamingHttpResponse(
        buf_generator(cert), content_type='application/x-pem-file'
    )
    response['Content-Length'] = len(cert)
    response['Content-Disposition'] = f'attachment; filename={ca["name"]}.crt'

    return response


def CA_export_privatekey(request, id):
    try:
        with client as c:
            ca = c.call('certificateauthority.query', [['id', '=', int(id)]], {'get': True})
    except Exception as e:
        raise MiddlewareError(e)

    if not ca['privatekey'] or not ca['key_length']:
        return HttpResponse('No private key or malformed key')

    key = ca['privatekey']
    response = StreamingHttpResponse(
        buf_generator(key), content_type='application/x-pem-file'
    )
    response['Content-Length'] = len(key)
    response['Content-Disposition'] = f'attachment; filename={ca["name"]}.key'

    return response


def certificate_progress(request):
    with client as c:
        job = c.call(
            'core.get_jobs',
            [['id', '=', request.session.get('certificate_create', {}).get('job_id', -1)]]
        )

    if job:
        job = job[0]

    return HttpResponse(json.dumps({
        "status": "finished" if not job or job["state"] in ["SUCCESS", "FAILED", "ABORTED"] else
        job["progress"]["description"],
        "volume": job["arguments"][0] if job else {},
        "extra": job["progress"]["extra"] if job else None,
        "percent": job["progress"]["percent"] if job else None,
    }), content_type='application/json')


def certificate_acme_create(request, csr_id):
    if request.session.get('certificate_create'):

        form, job, verrors = certificate_common_post_create(
            'create', request, csr_id=csr_id
        )

        if job['state'] == 'SUCCESS':
            return JsonResp(request, message=_('ACME Certificate successfully created'))
        else:
            if not verrors:
                raise MiddlewareError(job['error'])
            else:
                return render(request, 'system/certificate/certificate_create_ACME.html', {
                    'form': form
                })

    if request.method == "POST":
        form = forms.CertificateACMEForm(request.POST, csr_id=csr_id)
        if form.is_valid():
            job_id = form.save()
            request.session['certificate_create'] = {
                'job_id': job_id,
                'form': form.__class__.__name__,
                'payload': request.POST,
            }

            return render(
                request, 'system/certificate/certificate_progress.html', {
                    'certificate_url': reverse('certificate_acme_create', kwargs={'csr_id': csr_id}),
                    'dialog_name': 'Create ACME Certificate'
                }
            )
        return JsonResp(request, form=form)

    else:
        form = forms.CertificateACMEForm(csr_id=csr_id)

    return render(request, "system/certificate/certificate_create_ACME.html", {
        'form': form
    })


def certificate_csr_import(request):

    if request.session.get('certificate_create'):

        form, job, verrors = certificate_common_post_create(
            'create', request
        )

        if job['state'] == 'SUCCESS':
            return JsonResp(request, message=_('Certificate Signing Request successfully Imported'))
        else:
            if not verrors:
                raise MiddlewareError(job['error'])
            else:
                return render(request, 'system/certificate/CSR_import.html', {
                    'form': form
                })

    if request.method == "POST":
        form = forms.CertificateCSRImportForm(request.POST)
        if form.is_valid():
            job_id = form.save()
            request.session['certificate_create'] = {
                'job_id': job_id,
                'form': form.__class__.__name__,
                'payload': request.POST,
            }

            return render(
                request, 'system/certificate/certificate_progress.html', {
                    'certificate_url': reverse('certificate_import_csr'),
                    'dialog_name': 'Import Certificate Signing Request'
                }
            )
        return JsonResp(request, form=form)

    else:
        form = forms.CertificateCSRImportForm()

    return render(request, "system/certificate/CSR_import.html", {
        'form': form
    })


def certificate_import(request):

    if request.session.get('certificate_create'):

        form, job, verrors = certificate_common_post_create(
            'create', request,
        )

        if job['state'] == 'SUCCESS':
            return JsonResp(request, message=_('Certificate successfully Imported'))
        else:
            if not verrors:
                raise MiddlewareError(job['error'])
            else:
                return render(request, 'system/certificate/certificate_import.html', {
                    'form': form
                })

    if request.method == "POST":
        form = forms.CertificateImportForm(request.POST)
        if form.is_valid():
            job_id = form.save()
            request.session['certificate_create'] = {
                'job_id': job_id,
                'form': form.__class__.__name__,
                'payload': request.POST,
            }

            return render(
                request, 'system/certificate/certificate_progress.html', {
                    'certificate_url': reverse('certificate_import'),
                    'dialog_name': 'Import Certificate'
                }
            )
        return JsonResp(request, form=form)

    else:
        form = forms.CertificateImportForm()

    return render(request, "system/certificate/certificate_import.html", {
        'form': form
    })


def certificate_create_internal(request):

    if request.session.get('certificate_create'):

        form, job, verrors = certificate_common_post_create(
            'create', request
        )

        if job['state'] == 'SUCCESS':
            return JsonResp(request, message=_('Certificate successfully Created'))
        else:
            if not verrors:
                raise MiddlewareError(job['error'])
            else:
                return render(request, 'system/certificate/certificate_create_internal.html', {
                    'form': form
                })

    if request.method == "POST":
        form = forms.CertificateCreateInternalForm(request.POST)
        if form.is_valid():
            job_id = form.save()
            request.session['certificate_create'] = {
                'job_id': job_id,
                'form': form.__class__.__name__,
                'payload': request.POST,
            }

            return render(
                request, 'system/certificate/certificate_progress.html', {
                    'certificate_url': reverse('certificate_create_internal'),
                    'dialog_name': 'Create Internal Certificate'
                }
            )

        return JsonResp(request, form=form)
    else:
        form = forms.CertificateCreateInternalForm()

    return render(request, "system/certificate/certificate_create_internal.html", {
        'form': form
    })


def certificate_create_CSR(request):

    if request.session.get('certificate_create'):

        form, job, verrors = certificate_common_post_create(
            'create', request
        )

        if job['state'] == 'SUCCESS':
            return JsonResp(request, message=_('Certificate Signing Request successfully Created'))
        else:
            if not verrors:
                raise MiddlewareError(job['error'])
            else:
                return render(request, 'system/certificate/certificate_create_CSR.html', {
                    'form': form
                })

    if request.method == "POST":
        form = forms.CertificateCreateCSRForm(request.POST)
        if form.is_valid():
            job_id = form.save()
            request.session['certificate_create'] = {
                'job_id': job_id,
                'form': form.__class__.__name__,
                'payload': request.POST,
            }

            return render(
                request, 'system/certificate/certificate_progress.html', {
                    'certificate_url': reverse('certificate_create_CSR'),
                    'dialog_name': 'Create CSR'
                }
            )
        return JsonResp(request, form=form)

    else:
        form = forms.CertificateCreateCSRForm()

    return render(request, "system/certificate/certificate_create_CSR.html", {
        'form': form
    })


def certificate_edit(request, id):

    cert = models.Certificate.objects.get(pk=id)

    if request.session.get('certificate_create'):

        form, job, verrors = certificate_common_post_create(
            'update', request, instance=cert
        )

        if job['state'] == 'SUCCESS':
            return JsonResp(request, message=_('Certificate successfully edited'))
        else:
            if not verrors:
                raise MiddlewareError(job['error'])
            else:
                return render(request, 'system/certificate/certificate_edit.html', {
                    'form': form
                })

    if request.method == "POST":
        form = forms.CertificateEditForm(request.POST, instance=cert)
        if form.is_valid():
            job_id = form.save()
            request.session['certificate_create'] = {
                'job_id': job_id,
                'form': form.__class__.__name__,
                'payload': request.POST,
            }

            return render(
                request, 'system/certificate/certificate_progress.html', {
                    'certificate_url': reverse('certificate_edit', kwargs={'id': id}),
                    'dialog_name': 'Edit Certificate'
                }
            )
        return JsonResp(request, form=form)

    else:
        form = forms.CertificateEditForm(instance=cert)

    return render(request, "system/certificate/certificate_edit.html", {
        'form': form
    })


def CSR_edit(request, id):
    cert = models.Certificate.objects.get(pk=id)

    if request.session.get('certificate_create'):

        form, job, verrors = certificate_common_post_create(
            'update', request, instance=cert
        )

        if job['state'] == 'SUCCESS':
            return JsonResp(request, message=_('CSR successfully edited'))
        else:
            if not verrors:
                raise MiddlewareError(job['error'])
            else:
                return render(request, 'system/certificate/CSR_edit.html', {
                    'form': form
                })

    if request.method == "POST":
        form = forms.CertificateCSREditForm(request.POST, instance=cert)
        if form.is_valid():
            job_id = form.save()
            request.session['certificate_create'] = {
                'job_id': job_id,
                'form': form.__class__.__name__,
                'payload': request.POST,
            }

            return render(
                request, 'system/certificate/certificate_progress.html', {
                    'certificate_url': reverse('CSR_edit', kwargs={'id': id}),
                    'dialog_name': 'Edit CSR'
                }
            )
        return JsonResp(request, form=form)

    else:
        form = forms.CertificateCSREditForm(instance=cert)

    return render(request, "system/certificate/CSR_edit.html", {
        'form': form
    })


def certificate_export_certificate(request, id):
    with client as c:
        cert = c.call('certificate.query', [['id', '=', int(id)]], {'get': True})

    response = StreamingHttpResponse(
        buf_generator(cert['certificate']), content_type='application/x-pem-file'
    )
    response['Content-Length'] = len(cert['certificate'])
    response['Content-Disposition'] = f'attachment; filename={cert["name"]}.crt'

    return response


def certificate_export_privatekey(request, id):
    with client as c:
        cert = c.call('certificate.query', [['id', '=', int(id)]], {'get': True})

    if not cert['privatekey'] or not cert['key_length']:
        return HttpResponse('No private key or malformed private key')

    key = cert['privatekey']

    response = StreamingHttpResponse(
        buf_generator(key), content_type='application/x-pem-file'
    )
    response['Content-Length'] = len(key)
    response['Content-Disposition'] = f'attachment; filename={cert["name"]}.key'

    return response


def certificate_export_certificate_and_privatekey(request, id):
    with client as c:
        cert_data = c.call('certificate.query', [['id', '=', int(id)]], {'get': True})

    cert = cert_data['certificate']
    key = cert_data['privatekey']
    combined = key + cert

    response = StreamingHttpResponse(
        buf_generator(combined), content_type='application/octet-stream'
    )
    response['Content-Length'] = len(combined)
    response['Content-Disposition'] = f'attachment; filename={cert_data["name"]}.p12'

    return response


def certificate_to_json(certtype):
    # Keys of interest as used by generic_certificate_autopopulate js function
    # country, state, city, organization, email, organizational_unit
    with client as c:
        data = c.call('certificateauthority.query', [['id', '=', certtype.id]], {'get': True})

    content = json.dumps({
        f'cert_{k}': v for k, v in data.items()
    })
    return HttpResponse(content, content_type='application/json')


def CA_info(request, id):
    return certificate_to_json(
        models.CertificateAuthority.objects.get(pk=int(id))
    )


def job_logs(request, id):
    with client as c:
        job = c.call('core.get_jobs', [('id', '=', int(id))])[0]

    return render_to_response('system/job_logs.html', job)
