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
from subprocess import Popen
import os
import commands

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

from freenasUI.system import forms
from freenasUI.system import models
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

def system_info(request):

    sysinfo = _system_info()

    variables = RequestContext(request, {

    })
    variables.update(sysinfo)
    return render_to_response('system/system_info.html', variables)

def firmware_upload(request):

    firmware = forms.FirmwareUploadForm()
    variables = RequestContext(request)
    if request.method == 'POST':
        firmware = forms.FirmwareUploadForm(request.POST, request.FILES)
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

def firmware_location(request):

    firmloc = forms.FirmwareTemporaryLocationForm()
    variables = RequestContext(request)
    if request.method == 'POST':
        try:
            firmloc = forms.FirmwareTemporaryLocationForm(request.POST)
            if firmloc.is_valid():
                firmloc.done()
                firmware = forms.FirmwareUploadForm()
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

def config(request):

    variables = RequestContext(request, {

    })

    return render_to_response('system/config.html', variables)

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

def config_upload(request):

    if request.method == "POST":
        form = forms.ConfigUploadForm(request.POST, request.FILES)

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

        if request.GET.has_key("iframe"):
            return HttpResponse("<html><body><textarea>"+render_to_string('system/config_upload.html', variables)+"</textarea></boby></html>")
        else:
            return render_to_response('system/config_upload.html', variables)
    else:
        form = forms.ConfigUploadForm()

        variables = RequestContext(request, {
            'form': form,
        })

        return render_to_response('system/config_upload.html', variables)

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
    
    variables = RequestContext(request, {
        'graphs': graphs,
    })

    return render_to_response('system/reporting.html', variables)

def settings(request):

    settings = models.Settings.objects.order_by("-id")[0].id
    email = models.Email.objects.order_by("-id")[0].id
    ssl = models.SSL.objects.order_by("-id")[0].id
    advanced = models.Advanced.objects.order_by("-id")[0].id

    variables = RequestContext(request, {
        'settings': settings,
        'email': email,
        'ssl': ssl,
        'advanced': advanced,
    })

    return render_to_response('system/settings.html', variables)

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
    variables = RequestContext(request, extra_context)

    return render_to_response('system/advanced.html', variables)

def varlogmessages(request, lines):
    if lines == None:
        lines = 3
    msg = os.popen('tail -n %s /var/log/messages' % int(lines)).read().strip()
    variables = RequestContext(request, {
        'msg': msg,
    })
    return render_to_response('system/status/msg.xml', variables, mimetype='text/xml')

def top(request):
    top = os.popen('top').read()
    variables = RequestContext(request, {
        'focused_tab' : 'system',
        'top': top,
    })
    return render_to_response('system/status/top.xml', variables, mimetype='text/xml')

def reboot(request):
    """ reboots the system """
    notifier().restart("system")
    variables = RequestContext(request, {
        'freenas_version': get_freenas_version(),
    })
    return render_to_response('system/reboot.html', variables)

def shutdown(request):
    """ shuts down the system and powers off the system """
    notifier().stop("system")
    variables = RequestContext(request, {
        'freenas_version': get_freenas_version(),
    })
    return render_to_response('system/shutdown.html', variables)

def testmail(request):

    email = models.Email.objects.all().order_by('-id')[0]
    admin = User.objects.all()[0]
    error = False
    errmsg = ''
    if request.is_ajax():
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText("""This is a message test from FreeNAS""")
        msg['Subject'] = "Test message from FreeNAS"
        msg['From'] = email.em_fromemail
        msg['To'] = admin.email
        try:
            if email.em_security == 'ssl':
                server = smtplib.SMTP_SSL(email.em_outgoingserver, email.em_port)
            else:
                server = smtplib.SMTP(email.em_outgoingserver, email.em_port)
                if email.em_security == 'tls':
                    server.starttls()
            if email.em_smtp:
                server.login(email.em_user, email.em_pass)
            ret = server.sendmail(email.em_fromemail, [email.em_fromemail], msg.as_string())
            server.quit()
        except Exception, e:
            errmsg = str(e)
            error = True

    return HttpResponse(simplejson.dumps({
        'error': error,
        'errmsg': errmsg,
        }))
