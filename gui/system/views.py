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
#####################################################################

import cPickle as pickle
import datetime
import json
import logging
import os
import re
import shutil
import signal
import socket
import subprocess
import sysctl
import time
import urllib
import xmlrpclib

from django.contrib.auth import login, get_backends
from django.core.servers.basehttp import FileWrapper
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import (
    HttpResponse,
    HttpResponseRedirect,
    StreamingHttpResponse,
)
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _
from django.views.decorators.cache import never_cache

from freenasUI.account.models import bsdUsers
from freenasUI.common.locks import mntlock
from freenasUI.common.system import get_sw_name, get_sw_version, send_mail
from freenasUI.common.pipesubr import pipeopen
from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier
from freenasUI.network.models import GlobalConfiguration
from freenasUI.storage.models import MountPoint
from freenasUI.system import forms, models

GRAPHS_DIR = '/var/db/graphs'
VERSION_FILE = '/etc/version'
PGFILE = '/tmp/.extract_progress'
DDFILE = '/tmp/.upgrade_dd'
RE_DD = re.compile(r"^(\d+) bytes", re.M | re.S)
PERFTEST_SIZE = 40 * 1024 * 1024 * 1024  # 40 GiB

log = logging.getLogger('system.views')


def _system_info(request=None):
    # OS, hostname, release
    __, hostname, __ = os.uname()[0:3]
    platform = sysctl.filter('hw.model')[0].value
    physmem = '%dMB' % (
        sysctl.filter('hw.physmem')[0].value / 1048576,
    )
    # All this for a timezone, because time.asctime() doesn't add it in.
    date = time.strftime('%a %b %d %H:%M:%S %Z %Y') + '\n'
    uptime = subprocess.check_output(
        "env -u TZ uptime | awk -F', load averages:' '{ print $1 }'",
        shell=True
    )
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
    sysinfo = _system_info(request)
    sysinfo['info_hook'] = appPool.get_system_info(request)
    return render(request, 'system/system_info.html', sysinfo)


def config_restore(request):
    if request.method == "POST":
        request.session['allow_reboot'] = True
        notifier().config_restore()
        user = bsdUsers.objects.filter(bsdusr_uid=0)[0]
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
                    form.error_class([
                        _('The uploaded file is not valid.'),
                    ])
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
        os.chmod(FIRMWARE_DIR, 01777)
        form = forms.ConfigUploadForm()

        return render(request, 'system/config_upload.html', {
            'form': form,
        })


def config_save(request):

    hostname = GlobalConfiguration.objects.all().order_by('-id')[0].gc_hostname
    filename = '/data/freenas-v1.db'
    wrapper = FileWrapper(file(filename))

    freenas_build = "UNKNOWN"
    try:
        with open(VERSION_FILE) as d:
            freenas_build = d.read().strip()
    except:
        pass

    response = StreamingHttpResponse(
        wrapper, content_type='application/octet-stream'
    )
    response['Content-Length'] = os.path.getsize(filename)
    response['Content-Disposition'] = \
        'attachment; filename="%s-%s-%s.db"' % (
            hostname.encode('utf-8'),
            freenas_build,
            time.strftime('%Y%m%d%H%M%S'))
    return response


def reporting(request):
    return render(request, 'system/reporting.html')


def home(request):
    try:
        settings = models.Settings.objects.order_by("-id")[0]
    except:
        settings = None

    try:
        email = models.Email.objects.order_by("-id")[0]
    except:
        email = None

    try:
        ssl = models.SSL.objects.order_by("-id")[0]
    except:
        ssl = None

    try:
        advanced = models.Advanced.objects.order_by("-id")[0]
    except:
        advanced = None

    try:
        systemdataset = models.SystemDataset.objects.order_by("-id")[0]
    except:
        systemdataset = None

    try:
        registration = models.Registration.objects.order_by("-id")[0]
    except:
        registration = None

    return render(request, 'system/index.html', {
        'focus_form': request.GET.get('tab', 'system.SysInfo'),
        'settings': settings,
        'email': email,
        'ssl': ssl,
        'advanced': advanced,
        'systemdataset': systemdataset,
        'registration': registration,
    })


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
        return HttpResponseRedirect('/')
    request.session.pop("allow_reboot")
    return render(request, 'system/reboot.html', {
        'sw_name': get_sw_name(),
        'sw_version': get_sw_version(),
    })


def reboot_run(request):
    notifier().restart("system")
    return HttpResponse('OK')


def shutdown_dialog(request):
    if request.method == "POST":
        if notifier().zpool_scrubbing():
            if 'scrub_asked' not in request.session:
                request.session['scrub_asked'] = True
                return render(request, 'system/shutdown_dialog2.html')
        request.session['allow_shutdown'] = True
        return JsonResp(
            request,
            message=_("Shutdown is being issued"),
            events=['window.location="%s"' % reverse('system_shutdown')])
    return render(request, 'system/shutdown_dialog.html')


def shutdown(request):
    """ shuts down the system and powers off the system """
    if not request.session.get("allow_shutdown"):
        return HttpResponseRedirect('/')
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
    form = forms.EmailForm(request.POST, **kwargs)
    if not form.is_valid():
        return JsonResp(request, form=form)

    email = bsdUsers.objects.get(bsdusr_username='root').bsdusr_email
    if not email:
        return JsonResp(
            request,
            error=True,
            message=_(
                "You must configure the root email (Accounts->Users->root)"
            ),
        )

    sid = transaction.savepoint()
    form.save()

    error = False
    if request.is_ajax():
        sw_name = get_sw_name()
        error, errmsg = send_mail(subject=_('Test message from %s'
                                            % (sw_name)),
                                  text=_('This is a message test from %s'
                                         % (sw_name, )))
    if error:
        errmsg = _("Your test email could not be sent: %s") % errmsg
    else:
        errmsg = _('Your test email has been sent!')
    transaction.savepoint_rollback(sid)

    return JsonResp(request, error=error, message=errmsg)


class DojoFileStore(object):

    def __init__(self, path, dirsonly=False, root="/", filterVolumes=True):
        self.root = os.path.abspath(str(root))
        self.filterVolumes = filterVolumes
        if self.filterVolumes:
            self.mp = [
                os.path.abspath(mp.mp_path.encode('utf8'))
                for mp in MountPoint.objects.filter(
                    mp_volume__vol_fstype__in=('ZFS', 'UFS')
                )
            ]

        self.path = os.path.join(self.root, path.replace("..", ""))
        self.path = os.path.abspath(self.path)
        # POSIX allows one or two initial slashes, but treats three or more
        # as single slash.
        if self.path.startswith('//'):
            self.path = self.path[1:]

        self.path = self.path.encode('utf8')

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
        for _entry in sorted(os.listdir(entry)):
            #FIXME: better extendable way to exclude files
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
            }) + '?root=%s' % urllib.quote_plus(self.root),
        )
        item['id'] = item['$ref']
        return item


def directory_browser(request, path='/'):
    """ This view provides the ajax driven directory browser callback """
    #if not path.startswith('/'):
    #    path = '/%s' % path

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
    #if not path.startswith('/'):
    #    path = '/%s' % path

    directories = DojoFileStore(
        path,
        dirsonly=False,
        root=request.GET.get("root", "/"),
    ).items()
    context = directories
    content = json.dumps(context)
    return HttpResponse(content, content_type='application/json')


def firmware_progress(request):

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
    elif os.path.exists(DDFILE):
        with open(DDFILE, 'r') as f:
            pid = f.readline()
            if pid:
                pid = int(pid.strip())
        try:
            os.kill(pid, signal.SIGINFO)
            time.sleep(0.5)
            with open(DDFILE, 'r') as f2:
                line = f2.read()
            reg = RE_DD.findall(line)
            if reg:
                current = int(reg[-1])
                size = os.stat("/var/tmp/firmware/firmware.img").st_size
                percent = int((float(current) / size) * 100)
                data = {
                    'step': 3,
                    'percent': percent,
                }
        except OSError:
            pass

    content = json.dumps(data)
    return HttpResponse(content, content_type='application/json')


def initialwizard_progress(request):
    data = {}
    if os.path.exists(forms.WIZARD_PROGRESSFILE):
        with open(forms.WIZARD_PROGRESSFILE, 'rb') as f:
            data = f.read()
        try:
            data = pickle.loads(data)
        except:
            data = {}
    content = json.dumps(data)
    return HttpResponse(content, content_type='application/json')


def perftest(request):

    systemdataset, volume, basename = notifier().system_dataset_settings()

    if request.method == 'GET':
        p1 = subprocess.Popen([
            '/usr/local/bin/perftests-nas', '-t',
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        tests = p1.communicate()[0].strip('\n').split('\n')
        return render(request, 'system/perftest.html', {
            'tests': tests,
        })

    if not basename:
        raise MiddlewareError(
            _('System dataset is required to perform this action.')
        )

    dump = '/mnt/%s/perftest.txz' % basename
    perftestdataset = '%s/perftest' % basename

    with mntlock(mntpt='/mnt/%s' % basename):

        _n = notifier()

        rv, errmsg = _n.create_zfs_dataset(
            path=perftestdataset,
            props={
                'primarycache': 'metadata',
                'secondarycache': 'metadata',
                'compression': 'off',
            },
            _restart_collectd=False,
        )

        currdir = os.getcwd()
        os.chdir('/mnt/%s' % perftestdataset)

        p1 = subprocess.Popen([
            '/usr/local/bin/perftests-nas',
            '-o', ('/mnt/%s' % perftestdataset).encode('utf8'),
            '-s', str(PERFTEST_SIZE),
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        p1.communicate()

        os.chdir('..')

        p1 = pipeopen('tar -cJf %s perftest' % dump)
        p1.communicate()

        os.chdir(currdir)

        _n.destroy_zfs_dataset(perftestdataset)

        return JsonResp(
            request,
            message='Performance test has completed.',
            events=[
                'window.location=\'%s\'' % reverse('system_perftest_download'),
            ],
        )


def perftest_download(request):

    systemdataset, volume, basename = notifier().system_dataset_settings()
    dump = '/mnt/%s/perftest.txz' % basename

    wrapper = FileWrapper(file(dump))
    response = StreamingHttpResponse(
        wrapper,
        content_type='application/octet-stream',
    )
    response['Content-Length'] = os.path.getsize(dump)
    response['Content-Disposition'] = \
        'attachment; filename=perftest-%s-%s.tgz' % (
            socket.gethostname(),
            time.strftime('%Y%m%d%H%M%S'))

    return response


def perftest_progress(request):
    systemdataset, volume, basename = notifier().system_dataset_settings()
    progressfile = '/mnt/%s/perftest/.progress' % basename

    data = ''
    try:
        if os.path.exists(progressfile):
            with open(progressfile, 'r') as f:
                data = f.read()
            data = data.strip('\n')
    except:
        pass

    total = None
    reg = re.search(r'^totaltests:(\d+)$', data, re.M)
    if reg:
        total = int(reg.groups()[0])

    runningtest = data.rsplit('\n')[-1]
    if ':' in runningtest:
        runningtest = runningtest.split(':')[0]

    percent = None
    step = len(data.split('\n'))
    if total:
        step -= total
    indeterminate = True

    content = json.dumps({
        'step': step,
        'percent': percent,
        'indeterminate': indeterminate,
    })
    return HttpResponse(content, content_type='application/json')


def restart_httpd(request):
    """ restart httpd """
    notifier().restart("http")
    return HttpResponse('OK')


def reload_httpd(request):
    """ restart httpd """
    notifier().reload("http")
    return HttpResponse('OK')


def debug(request):
    hostname = GlobalConfiguration.objects.all().order_by('-id')[0].gc_hostname
    p1 = pipeopen("zfs list -H -o name")
    zfs = p1.communicate()[0]
    zfs = zfs.split()
    direc = "/var/tmp/ixdiagnose"
    mntpt = '/var/tmp'
    systemdataset, volume, basename = notifier().system_dataset_settings()
    if basename:
        mntpoint = '/mnt/%s' % basename
        if os.path.exists(mntpoint):
            direc = '%s/ixdiagnose' % mntpoint
            mntpt = mntpoint
    dump = "%s/ixdiagnose.tgz" % direc

    with mntlock(mntpt=mntpt):

        # Be extra safe in case we have left over from previous run
        if os.path.exists(direc):
            opts = ["/bin/rm", "-r", "-f", direc]
            p1 = pipeopen(' '.join(opts), allowfork=True)
            p1.wait()

        opts = ["/usr/local/bin/ixdiagnose", "-d", direc, "-s", "-F"]
        p1 = pipeopen(' '.join(opts), allowfork=True)
        p1.communicate()

        wrapper = FileWrapper(file(dump))
        response = StreamingHttpResponse(
            wrapper,
            content_type='application/octet-stream',
        )
        response['Content-Length'] = os.path.getsize(dump)
        response['Content-Disposition'] = \
            'attachment; filename=debug-%s-%s.tgz' % (
                hostname.encode('utf-8'),
                time.strftime('%Y%m%d%H%M%S'))

        opts = ["/bin/rm", "-r", "-f", direc]
        p1 = pipeopen(' '.join(opts), allowfork=True)
        p1.wait()

        return response


def backup(request):
    # Check if any backup is currently running
    backups = models.Backup.objects.all().order_by('-bak_started_at')

    if len(backups) < 1 or backups[0].bak_acknowledged:
        # No backup is pending, can schedule next one

        if request.method == 'POST':
            backup_form = forms.BackupForm(request.POST)
            if backup_form.is_valid():
                backup = models.Backup()
                backup.bak_started_at = datetime.datetime.now()
                backup.save()
                transaction.commit()

                args = {
                    'cmd': 'START',
                    'hostport': backup_form.cleaned_data['backup_hostname'],
                    'username': backup_form.cleaned_data['backup_username'],
                    'password': backup_form.cleaned_data['backup_password'],
                    'directory': backup_form.cleaned_data['backup_directory'],
                    'with-data': backup_form.cleaned_data['backup_data'],
                    'compression': backup_form.cleaned_data['backup_compression'],
                    'backup-id': backup.id
                }

                notifier().start('backup')
                response = notifier().call_backupd(args)

                if response['status'] != 'OK':
                    return JsonResp(request, error=True, message='Could not communicate with backup daemon')

                return render(request, 'system/backup_progress.html')

        backup_form = forms.BackupForm()
        return render(request, 'system/backup.html', {
            'form': backup_form
        })
    elif backups[0].bak_finished or backups[0].bak_failed:
        if request.method == 'POST':
            backups[0].bak_acknowledged = True
            backups[0].save()
            return JsonResp(request, message='Backup dismissed')

        return render(request, 'system/backup_acknowledge.html', {'backup': backups[0]})
    else:
        return render(request, 'system/backup_progress.html')

def backup_progress(request):
    # Check if any backup is currently running
    backup = models.Backup.objects.all().order_by('-bak_started_at').first()

    if backup.bak_finished:
        data = {'status': 'finished', 'message': backup.bak_status}
        return HttpResponse(json.dumps(data), content_type='application/json')

    if backup.bak_failed:
        data = {'status': 'error', 'message': backup.bak_status}
        return HttpResponse(json.dumps(data), content_type='application/json')

    response = notifier().call_backupd({'cmd': 'PROGRESS'})
    if response['status'] != 'OK':
        data = {'status': 'error', 'message': 'Could not communicate with backup daemon'}
        return HttpResponse(json.dumps(data), content_type='application/json')

    data = {
        'status': 'running',
        'percent': response['percentage'],
        'message': response['message']
    }

    return HttpResponse(json.dumps(data), content_type='application/json')

def backup_abort(request):
    # Check if any backup is currently running
    backups = models.Backup.objects.all().order_by('-bak_started_at')

    if len(backups) < 1 or backups[0].bak_finished:
        pass

    if request.method == 'POST':
        # User wants to abort a backup
        response = notifier().call_backupd({'cmd': 'ABORT'})
        if response['status'] != 'OK':
            return render(request, 'system/backup_acknowledge.html', {'backup': backups[0]})

        return render(request, 'system/backup_acknowledge.html', {'backup': backups[0]})

class UnixTransport(xmlrpclib.Transport):
    def make_connection(self, addr):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(addr)
        self.sock.settimeout(5)
        return self.sock

    def single_request(self, host, handler, request_body, verbose=0):
        # issue XML-RPC request

        self.make_connection(host)

        try:
            self.sock.send(request_body + "\n")
            p, u = self.getparser()

            while 1:
                data = self.sock.recv(1024)
                if not data:
                    break
                p.feed(data)

            self.sock.close()
            p.close()

            return u.close()
        except xmlrpclib.Fault:
            raise
        except Exception:
            # All unexpected errors leave connection in
            # a strange state, so we clear it.
            self.close()
            raise


class MyServer(xmlrpclib.ServerProxy):

    def __init__(self, addr):

        self.__handler = "/"
        self.__host = addr
        self.__transport = UnixTransport()
        self.__encoding = None
        self.__verbose = 0
        self.__allow_none = 0

    def __request(self, methodname, params):
        # call a method on the remote server

        request = xmlrpclib.dumps(
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
        # magic method dispatcher
        return xmlrpclib._Method(self.__request, name)


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
        except Exception, e:
            notifier().restart("webshell")
            time.sleep(0.5)

    try:
        if alive:
            if k:
                multiplex.proc_write(
                    sid,
                    xmlrpclib.Binary(bytearray(k.encode('utf-8')))
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
    except (KeyError, ValueError, IndexError, xmlrpclib.Fault), e:
        response = HttpResponse('Invalid parameters: %s' % e)
        response.status_code = 400
        return response


def terminal_paste(request):
    return render(request, "system/terminal_paste.html")
