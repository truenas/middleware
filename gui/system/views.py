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

import datetime
import tempfile
from subprocess import Popen
import os, commands

from django.contrib.auth.decorators import permission_required, login_required
from django.contrib.auth import authenticate, login, logout, get_backends
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.template.loader import render_to_string
from django.template import RequestContext
from django.utils import simplejson
from django.utils.translation import ugettext as _

from freenasUI.system.forms import * 
from freenasUI.system.models import * 
from freenasUI.middleware.notifier import notifier
from freenasUI.common.system import get_freenas_version

def _system_info():
    hostname = commands.getoutput("hostname")
    uname1 = os.uname()[0]
    uname2 = os.uname()[2]
    platform = os.popen("sysctl -n hw.model").read()
    date = os.popen('env -u TZ date').read()
    uptime = commands.getoutput("uptime | awk -F', load averages:' '{    print $1 }'")
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
        'date': date,
        'uptime': uptime,
        'loadavg': loadavg,
        'freenas_build': freenas_build,
    }

@login_required
def index(request, objtype = None):
    if objtype != None:
        focus_form = objtype
    else:
        focus_form = 'system'
    sysinfo = _system_info()
    settings = SettingsForm(data = Settings.objects.order_by("-id").values()[0])
    advanced = AdvancedForm(data = Advanced.objects.order_by("-id").values()[0])
    try:
        email = EmailForm(instance = Email.objects.order_by("-id")[0])
    except:
        email = EmailForm()
    try:
         ssl = SSLForm(instance = SSL.objects.order_by("-id")[0])
    except:
         ssl = SSLForm()
    firmloc = FirmwareTemporaryLocationForm()
    firmware = FirmwareUploadForm()
    if request.method == 'POST':
        if objtype == 'settings':
            settings = SettingsForm(request.POST)
            if settings.is_valid():
                settings.save()
                return HttpResponseRedirect('/system/' + objtype)
        elif objtype == 'advanced':
            advanced = AdvancedForm(request.POST)
            if advanced.is_valid():
                advanced.save()
                return HttpResponseRedirect('/system/' + objtype)
        elif objtype == 'email':
            email = EmailForm(request.POST)
            if email.is_valid():
                email.save()
                return HttpResponseRedirect('/system/' + objtype)
        elif objtype == 'ssl':
            ssl = SSLForm(request.POST)
            if ssl.is_valid():
                ssl.save()
                return HttpResponseRedirect('/system/' + objtype)
        elif objtype == 'firmloc':
            firmloc = FirmwareTemporaryLocationForm(request.POST)
            if firmloc.is_valid():
                firmloc.done()
                return HttpResponseRedirect('/system/firmware/')
        elif objtype == 'firmware':
            firmware = FirmwareUploadForm(request.POST, request.FILES)
            if firmware.is_valid():
                firmware.done()
                return HttpResponseRedirect('/system/' + objtype)
        else: 
            raise Http404()

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
    

    variables = RequestContext(request, {
        'focused_tab' : 'system',
        'settings': settings,
        'email': email,
        'ssl': ssl,
        'advanced': advanced,
        'firmloc': firmloc,
        'firmware': firmware,
        'focus_form': focus_form,
        'graphs': graphs,
    })
    variables.update(sysinfo)
    return render_to_response('system/index.html', variables)

@login_required
def system_info(request):

    sysinfo = _system_info()

    variables = RequestContext(request, {

    })
    variables.update(sysinfo)
    return render_to_response('system/system_info.html', variables)

@login_required
def firmware_upload(request):

    firmware = FirmwareUploadForm()
    variables = RequestContext(request)
    if request.method == 'POST':
        firmware = FirmwareUploadForm(request.POST, request.FILES)
        valid = firmware.is_valid()
        try:
            if valid:
                firmware.done()
                return render_to_response('system/firmware_ok.html')
        except:
            pass
        variables.update({
            'firmware': firmware,
        })
        if request.GET.has_key("iframe"):
            return HttpResponse("<html><body><textarea>"+render_to_string('system/firmware2.html', variables)+"</textarea></boby></html>")
        else:
            return render_to_response('system/firmware2.html', variables)

    variables.update({
        'firmware': firmware,
    })
    
    return render_to_response('system/firmware.html', variables)

@login_required
def firmware_location(request):

    firmloc = FirmwareTemporaryLocationForm()
    variables = RequestContext(request)
    if request.method == 'POST':
        try:
            firmloc = FirmwareTemporaryLocationForm(request.POST)
            if firmloc.is_valid():
                firmloc.done()
                firmware = FirmwareUploadForm()
                variables.update({
                    'firmware': firmware,
                })
                return render_to_response('system/firmware2.html', variables)
        except:
            pass
        variables.update({
            'firmloc': firmloc,
        })
        return render_to_response('system/firmware_location2.html', variables)

    variables.update({
        'firmloc': firmloc,
    })
    
    return render_to_response('system/firmware_location.html', variables)

@login_required
def config(request):

    variables = RequestContext(request, {

    })

    return render_to_response('system/config.html', variables)

@login_required
def config_restore(request):

    variables = RequestContext(request)

    if request.method == "POST":
        notifier().config_restore()
        user = User.objects.all()[0]
        backend = get_backends()[0]
        user.backend = "%s.%s" % (backend.__module__, backend.__class__.__name__)
        login(request, user)
        return render_to_response('system/config_ok2.html', variables)

    return render_to_response('system/config_restore.html', variables)

@login_required
def config_upload(request):

    if request.method == "POST":
        form = ConfigUploadForm(request.POST, request.FILES)

        variables = RequestContext(request, {
            'form': form,
        })
        
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
                return render_to_response('system/config_ok.html', variables)

        return render_to_response('system/config_upload2.html', variables)
    else:
        form = ConfigUploadForm()

        variables = RequestContext(request, {
            'form': form,
        })

        return render_to_response('system/config_upload.html', variables)

@login_required
def config_save(request):

    from django.core.servers.basehttp import FileWrapper
    filename = '/data/freenas-v1.db'
    wrapper = FileWrapper(file(filename))
    response = HttpResponse(wrapper, content_type='application/octet-stream')
    response['Content-Length'] = os.path.getsize(filename)
    response['Content-Disposition'] = 'attachment; filename=freenas-%s.db' % datetime.datetime.now().strftime("%Y-%m-%d")
    return response

@login_required
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
    

    variables = RequestContext(request, {
        'graphs': graphs,
    })

    return render_to_response('system/reporting.html', variables)

@login_required
def settings(request):

    settings = Settings.objects.order_by("-id")[0].id
    email = Email.objects.order_by("-id")[0].id
    ssl = SSL.objects.order_by("-id")[0].id
    advanced = Advanced.objects.order_by("-id")[0].id

    variables = RequestContext(request, {
        'settings': settings,
        'email': email,
        'ssl': ssl,
        'advanced': advanced,
    })

    return render_to_response('system/settings.html', variables)

@login_required
def advanced(request):

    extra_context = {}
    advanced = AdvancedForm(data = Advanced.objects.order_by("-id").values()[0], auto_id=False)
    if request.method == 'POST':
        advanced = AdvancedForm(request.POST, auto_id=False)
        if advanced.is_valid():
            advanced.save()
            extra_context['saved'] = True

    extra_context.update({
        'advanced': advanced,
    })
    variables = RequestContext(request, extra_context)

    return render_to_response('system/advanced.html', variables)

@login_required
def test(request, objtype = None):
    context = RequestContext(request)

    return render_to_response('system/test.html', context)

@login_required
def test1(request, objtype = None):
    if objtype != None:
        focus_form = objtype
    else:
        focus_form = 'system'
    hostname = commands.getoutput("hostname")
    uname1 = os.uname()[0]
    uname2 = os.uname()[2]
    platform = os.popen("sysctl -n hw.model").read()
    date = os.popen('env -u TZ date').read()
    uptime = commands.getoutput("uptime | awk -F', load averages:' '{    print $1 }'")
    loadavg = commands.getoutput("uptime | awk -F'load averages:' '{     print $2 }'")
    settings = SettingsForm(data = Settings.objects.order_by("-id").values()[0])
    advanced = AdvancedForm(data = Advanced.objects.order_by("-id").values()[0])
    if request.method == 'POST':
        if objtype == 'settings':
            settings = SettingsForm(request.POST)
            if settings.is_valid():
                settings.save()
        elif objtype == 'advanced':
            advanced = AdvancedForm(request.POST)
            if advanced.is_valid():
                advanced.save()
        else: 
            raise Http404()
        return HttpResponseRedirect('/system/' + objtype)
    try:
        d = open('/etc/version.freenas', 'r')
        freenas_build = d.read()
        d.close()
    except:
        freenas_build = "Unrecognized build (/etc/version.freenas        missing?)"
    variables = RequestContext(request, {
        'focused_tab' : 'system',
        'settings': settings,
        'advanced': advanced,
        'hostname': hostname,
        'uname1': uname1,
        'uname2': uname2,
        'platform': platform,
        'date': date,
        'uptime': uptime,
        'loadavg': loadavg,
        'freenas_build': freenas_build,
        'focus_form': focus_form,
    })
    return render_to_response('system/test1.html', variables)

@login_required
def varlogmessages(request, lines):
    if lines == None:
        lines = 3
    msg = os.popen('tail -n %s /var/log/messages' % int(lines)).read().strip()
    variables = RequestContext(request, {
        'msg': msg,
    })
    return render_to_response('system/status/msg.xml', variables, mimetype='text/xml')

@login_required
def top(request):
    top = os.popen('top').read()
    variables = RequestContext(request, {
        'focused_tab' : 'system',
        'top': top,
    })
    return render_to_response('system/status/top.xml', variables, mimetype='text/xml')

@login_required
def reboot(request):
    """ reboots the system """
    notifier().restart("system")
    variables = RequestContext(request, {
        'freenas_version': get_freenas_version(),
    })
    return render_to_response('system/reboot.html', variables)

@login_required
def shutdown(request):
    """ shuts down the system and powers off the system """
    notifier().stop("system")
    variables = RequestContext(request, {
        'freenas_version': get_freenas_version(),
    })
    return render_to_response('system/shutdown.html', variables)

