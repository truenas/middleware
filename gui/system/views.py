#+
# Copyright 2010 iXsystems
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

from datetime import datetime
import tempfile
import os
import commands

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
from freenasUI.common.system import get_freenas_version

def _system_info():
    hostname = commands.getoutput("hostname")
    uname1 = os.uname()[0]
    uname2 = os.uname()[2]
    platform = os.popen("sysctl -n hw.model").read()
    physmem = str(int(int(os.popen("sysctl -n hw.physmem").read()) / 1048576)) + "MB"
    date = os.popen('env -u TZ date').read()
    uptime = commands.getoutput("env -u TZ uptime | awk -F', load averages:' '{    print $1 }'")
    loadavg = "%.2f, %.2f, %.2f" % os.getloadavg()

    try:
        d = open('/etc/version.freenas', 'r')
        freenas_build = d.read()
        d.close()
    except:
        freenas_build = "Unrecognized build (/etc/version.freenas        missing?)"

    return {
        'hostname': hostname,
        'uname1': uname1,
        'uname2': uname2,
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

def config(request):
    return render(request, 'system/config.html')

def config_restore(request):
    if request.method == "POST":
        notifier().config_restore()
        user = User.objects.all()[0]
        backend = get_backends()[0]
        user.backend = "%s.%s" % (backend.__module__, backend.__class__.__name__)
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
            import sqlite3
            sqlite = request.FILES['config'].read()
            f = tempfile.NamedTemporaryFile()
            f.write(sqlite)
            f.flush()
            try:
                conn = sqlite3.connect(f.name)
                cur = conn.cursor()
                cur.execute("""SELECT name FROM sqlite_master
                WHERE type='table'
                ORDER BY name;""")
            except sqlite3.DatabaseError:
                f.close()
                form._errors['__all__'] = form.error_class([_("The uploaded file is not valid."),])
            else:
                db = open('/data/freenas-v1.db', 'w')
                db.write(sqlite)
                db.close()
                f.close()
                user = User.objects.all()[0]
                backend = get_backends()[0]
                user.backend = "%s.%s" % (backend.__module__, backend.__class__.__name__)
                login(request, user)
                return render(request, 'system/config_ok.html', variables)

        if request.GET.has_key("iframe"):
            return HttpResponse("<html><body><textarea>"+render_to_string('system/config_upload.html', variables)+"</textarea></boby></html>")
        else:
            return render(request, 'system/config_upload.html', variables)
    else:
        os.system("rm -rf /var/tmp/firmware")
        os.system("/bin/ln -s /var/tmp/ /var/tmp/firmware")
        form = forms.ConfigUploadForm()

        return render(request, 'system/config_upload.html', {
            'form': form,
        })

def config_save(request):

    from django.core.servers.basehttp import FileWrapper
    filename = '/data/freenas-v1.db'
    wrapper = FileWrapper(file(filename))
    response = HttpResponse(wrapper, content_type='application/octet-stream')
    response['Content-Length'] = os.path.getsize(filename)
    response['Content-Disposition'] = 'attachment; filename=freenas-%s.db' % datetime.now().strftime("%Y-%m-%d")
    return response

def reporting(request):

    graphs = {}
    try:
        graphs['hourly']  = None or [file for file in os.listdir( os.path.join('/var/db/graphs/', 'hourly/') )],
    except OSError:
        pass
    try:
        graphs['daily']   = None or [file for file in os.listdir( os.path.join('/var/db/graphs/', 'daily/') )],
    except OSError:
        pass
    try:
        graphs['weekly']  = None or [file for file in os.listdir( os.path.join('/var/db/graphs/', 'weekly/') )],
    except OSError:
        pass
    try:
        graphs['monthly'] = None or [file for file in os.listdir( os.path.join('/var/db/graphs/', 'monthly/') )],
    except OSError:
        pass
    try:
        graphs['yearly']  = None or [file for file in os.listdir( os.path.join('/var/db/graphs/', 'yearly/') )],
    except OSError:
        pass
    
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
    if lines == None:
        lines = 3
    msg = os.popen('tail -n %s /var/log/messages' % int(lines)).read().strip()
    return render(request, 'system/status/msg.xml', {
        'msg': msg,
    }, mimetype='text/xml')

def top(request):
    top = os.popen('top').read()
    return render(request, 'system/status/top.xml', {
        'focused_tab' : 'system',
        'top': top,
    }, mimetype='text/xml')

def reboot(request):
    """ reboots the system """
    notifier().restart("system")
    return render(request, 'system/reboot.html', {
        'freenas_version': get_freenas_version(),
    })

def shutdown(request):
    """ shuts down the system and powers off the system """
    notifier().stop("system")
    return render(request, 'system/shutdown.html', {
        'freenas_version': get_freenas_version(),
    })

def testmail(request):

    error = False
    errmsg = ''
    if request.is_ajax():
        from common.system import send_mail
        error, errmsg = send_mail(subject="Test message from FreeNAS", 
                                  text="This is a message test from FreeNAS")

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
    
    def items(self):
        if self.path == '/mnt':
            return self.children(self.path)
          
        node = self._item(self.path, self.path)
        if node['directory']:
            node['children'] = self.children(self.path)
        return node
    
    def children(self, entry):
        children = [ self._item(self.path, entry) for entry in os.listdir(entry) if len([f for f in self.mp if os.path.join(self.path,entry).startswith(f)]) > 0]
        if self.dirsonly:
            children = [ child for child in children if child['directory']]
        return children
    
    def _item(self, path, entry):
        full_path = os.path.join(path, entry)
        isdir = os.path.isdir(full_path)
        item = dict(name=os.path.basename(entry), 
                    directory=isdir,
                    path=full_path)
        if isdir:
            item['children'] = True
        
        item['$ref'] = os.path.abspath(reverse('system_dirbrowser', kwargs={'path':full_path}))
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

def cronjobs(request):
    crons = models.CronJob.objects.all().order_by('id')
    return render(request, "system/cronjob.html", {
        'cronjobs': crons,
        })

def rsyncs(request):
    rsyncs = models.Rsync.objects.all().order_by('id')
    return render(request, "system/rsync.html", {
        'rsyncs': rsyncs,
        })
