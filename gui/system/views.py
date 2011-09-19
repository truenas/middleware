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

import commands
import os
import shutil
import subprocess
import time

from django.contrib.auth import login, get_backends
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import simplejson
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse

from freenasUI.system import forms
from freenasUI.system import models
from freenasUI.middleware.notifier import notifier
from freenasUI.common.system import get_sw_name, get_sw_version

GRAPHS_DIR = '/var/db/graphs'
VERSION_FILE = '/etc/version'
DEBUG_TEMP = '/tmp/debug.txt'

def _system_info():
    # OS, hostname, release
    __, hostname, __ = os.uname()[0:3]
    platform = subprocess.check_output(['sysctl', '-n', 'hw.model'])
    physmem = str(int(int(subprocess.check_output(['sysctl', '-n', 'hw.physmem'])) / 1048576)) + 'MB'
    # All this for a timezone, because time.asctime() doesn't add it in.
    date = time.strftime('%a %b %d %H:%M:%S %Z %Y') + '\n'
    uptime = commands.getoutput("env -u TZ uptime | awk -F', load averages:' '{    print $1 }'")
    loadavg = "%.2f, %.2f, %.2f" % os.getloadavg()

    freenas_build = "Unrecognized build (%s        missing?)" % VERSION_FILE
    try:
        with open(VERSION_FILE) as d:
            freenas_build = d.read()
    except:
        pass

    return {
        'hostname': hostname,
        'platform': platform,
        'physmem': physmem,
        'date': date,
        'uptime': uptime,
        'loadavg': loadavg,
        'freenas_build': freenas_build,
    }

def system_info(request):
    sysinfo = _system_info()
    return render(request, 'system/system_info.html', sysinfo)

def config_restore(request):
    if request.method == "POST":
        notifier().config_restore()
        user = User.objects.all()[0]
        backend = get_backends()[0]
        user.backend = "%s.%s" % (backend.__module__,
                                  backend.__class__.__name__)
        login(request, user)
        return render(request, 'system/config_ok2.html')
    return render(request, 'system/config_restore.html')

def config_upload(request):

    if request.method == "POST":
        form = forms.ConfigUploadForm(request.POST, request.FILES)

        variables = {
            'form': form,
        }

        if form.is_valid():
            if not notifier().config_upload(request.FILES['config']):
                form._errors['__all__'] = \
                    form.error_class([_('The uploaded file is not valid.'),])
            else:
                return render(request, 'system/config_ok.html', variables)

        if request.GET.has_key('iframe'):
            return HttpResponse('<html><body><textarea>' +
                                render_to_string('system/config_upload.html',
                                                 variables) +
                                '</textarea></boby></html>')
        else:
            return render(request, 'system/config_upload.html', variables)
    else:
        FIRMWARE_DIR = '/var/tmp/firmware'
        if os.path.exists(FIRMWARE_DIR):
            if os.path.islink(FIRMWARE_DIR):
                os.unlink(FIRMWARE_DIR)
            if os.path.isdir(FIRMWARE_DIR):
                shutil.rmtree(FIRMWARE_DIR + '/')
        os.mkdir(FIRMWARE_DIR)
        os.chmod(FIRMWARE_DIR, 01777)
        form = forms.ConfigUploadForm()

        return render(request, 'system/config_upload.html', {
            'form': form,
        })

def config_save(request):

    from django.core.servers.basehttp import FileWrapper
    from network.models import GlobalConfiguration
    hostname = GlobalConfiguration.objects.all().order_by('-id')[0].gc_hostname
    filename = '/data/freenas-v1.db'
    wrapper = FileWrapper(file(filename))

    freenas_build = "UNKNOWN"
    try:
        with open(VERSION_FILE) as d:
            freenas_build = d.read().strip()
    except:
        pass

    response = HttpResponse(wrapper, content_type='application/octet-stream')
    response['Content-Length'] = os.path.getsize(filename)
    response['Content-Disposition'] = \
        'attachment; filename=%s-%s-%s.db' % (hostname.encode('utf-8'), freenas_build, time.strftime('%Y%m%d%H%M%S'))
    return response

def reporting(request):

    graphs = {}
    for gtype in ('hourly', 'daily', 'weekly', 'monthly', 'yearly', ):
        graphs_dir = os.path.join(GRAPHS_DIR, gtype)
        if os.path.isdir(graphs_dir):
            graphs[gtype] = os.listdir(graphs_dir)
        else:
            graphs[gtype] = None

    return render(request, 'system/reporting.html', {
        'graphs': graphs,
    })

def settings(request):
    settings = models.Settings.objects.order_by("-id")[0].id
    email = models.Email.objects.order_by("-id")[0].id
    ssl = models.SSL.objects.order_by("-id")[0].id
    advanced = models.Advanced.objects.order_by("-id")[0].id

    return render(request, 'system/settings.html', {
        'settings': settings,
        'email': email,
        'ssl': ssl,
        'advanced': advanced,
    })

def advanced(request):

    extra_context = {}
    advanced = forms.AdvancedForm(data = models.Advanced.objects.order_by("-id").values()[0], auto_id=False)
    if request.method == 'POST':
        advanced = forms.AdvancedForm(request.POST, auto_id=False)
        if advanced.is_valid():
            advanced.save()
            extra_context['saved'] = True

    extra_context.update({
        'advanced': advanced,
    })
    return render(request, 'system/advanced.html', extra_context)

def varlogmessages(request, lines):
    if lines is None:
        lines = 3
    msg = os.popen('tail -n %s /var/log/messages' % int(lines)).read().strip()
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
        'focused_tab' : 'system',
        'top': top_output,
    }, content_type='text/xml')

def reboot(request):
    """ reboots the system """
    return render(request, 'system/reboot.html', {
        'sw_name': get_sw_name(),
        'sw_version': get_sw_version(),
    })

def reboot_run(request):
    notifier().restart("system")
    return HttpResponse('OK')

def shutdown(request):
    """ shuts down the system and powers off the system """
    return render(request, 'system/shutdown.html', {
        'sw_name': get_sw_name(),
        'sw_version': get_sw_version(),
    })

def shutdown_run(request):
    notifier().stop("system")
    return HttpResponse('OK')

def testmail(request):

    error = False
    errmsg = ''
    if request.is_ajax():
        from common.system import send_mail
        sw_name = get_sw_name()
        error, errmsg = send_mail(subject=_('Test message from %s'
                                            % (sw_name)),
                                  text=_('This is a message test from %s'
                                         % (sw_name, )))

    return HttpResponse(simplejson.dumps({
        'error': error,
        'errmsg': errmsg,
        }))

def clearcache(request):

    error = False
    errmsg = ''

    os.system("(/usr/local/bin/python /usr/local/www/freenasUI/tools/cachetool.py expire >/dev/null 2>&1 && /usr/local/bin/python /usr/local/www/freenasUI/tools/cachetool.py fill >/dev/null 2>&1) &")

    return HttpResponse(simplejson.dumps({
        'error': error,
        'errmsg': errmsg,
        }))

class DojoFileStore(object):
    def __init__(self, path, dirsonly=False):
        from storage.models import MountPoint
        self.mp = [os.path.abspath(mp.mp_path) for mp in MountPoint.objects.filter(mp_volume__vol_fstype__in=('ZFS','UFS'))]

        self.path = path.replace("..", "")
        if not self.path.startswith('/mnt/'):
            self.path = '/mnt/'+self.path
        self.path = os.path.abspath(self.path)
        self.dirsonly = dirsonly
        self._lookupurl = 'system_dirbrowser' if self.dirsonly else 'system_filebrowser'

    def items(self):
        if self.path == '/mnt':
            return self.children(self.path)

        node = self._item(self.path, self.path)
        if node['directory']:
            node['children'] = self.children(self.path)
        return node

    def children(self, entry):
        _children = [self._item(self.path, entry) for entry in os.listdir(entry) if len([f for f in self.mp if os.path.join(self.path, entry).startswith(f + '/') or os.path.join(self.path, entry) == f]) > 0]
        if self.dirsonly:
            _children = [child for child in _children if child['directory']]
        return _children

    def _item(self, path, entry):
        full_path = os.path.join(path, entry)
        isdir = os.path.isdir(full_path)
        item = {
                 'name': os.path.basename(entry),
                 'directory': isdir,
                 'path': full_path,
               }
        if isdir:
            item['children'] = True

        item['$ref'] = os.path.abspath(reverse(self._lookupurl,
                                       kwargs={ 'path' : full_path }))
        item['id'] = item['$ref']
        return item

def directory_browser(request, path='/'):
    """ This view provides the ajax driven directory browser callback """
    if not path.startswith('/'):
        path = '/%s' % path

    directories = DojoFileStore(path, dirsonly=True).items()
    context = directories
    content = simplejson.dumps(context)
    return HttpResponse(content, mimetype='application/json')

def file_browser(request, path='/'):
    """ This view provides the ajax driven directory browser callback """
    if not path.startswith('/'):
        path = '/%s' % path

    directories = DojoFileStore(path, dirsonly=False).items()
    context = directories
    content = simplejson.dumps(context)
    return HttpResponse(content, mimetype='application/json')

def cronjobs(request):
    crons = models.CronJob.objects.all().order_by('id')
    return render(request, "system/cronjob.html", {
        'cronjobs': crons,
        })

def smarttests(request):
    tests = models.SMARTTest.objects.all().order_by('id')
    return render(request, "system/smarttest.html", {
        'smarttests': tests,
        })

def rsyncs(request):
    syncs = models.Rsync.objects.all().order_by('id')
    return render(request, 'system/rsync.html', {
        'rsyncs': syncs,
        })

def restart_httpd(request):
    """ restart httpd """
    notifier().restart("http")
    return HttpResponse('OK')

def debug(request):
    """Save freenas-debug output to DEBUG_TEMP"""
    p1 = subprocess.Popen(["/usr/local/bin/freenas-debug", "-a", "-g", "-h", "-l", "-n", "-s", "-y", "-t", "-z"], stdout=subprocess.PIPE)
    debug = p1.communicate()[0]
    with open(DEBUG_TEMP, 'w') as f:
        f.write(debug)
    return render(request, 'system/debug.html')

def debug_save(request):
    from django.core.servers.basehttp import FileWrapper
    from network.models import GlobalConfiguration

    hostname = GlobalConfiguration.objects.all().order_by('-id')[0].gc_hostname
    wrapper = FileWrapper(file(DEBUG_TEMP))

    response = HttpResponse(wrapper, content_type='application/octet-stream')
    response['Content-Length'] = os.path.getsize(DEBUG_TEMP)
    response['Content-Disposition'] = \
        'attachment; filename=debug-%s-%s.txt' % (hostname.encode('utf-8'), time.strftime('%Y%m%d%H%M%S'))
    return response
