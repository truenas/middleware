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

from freenasUI.system.forms import * 
from freenasUI.system.models import * 
from django.forms.models import modelformset_factory
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.contrib.auth import authenticate, login, logout
from django.template import RequestContext
from django.http import Http404
from django.views.generic.list_detail import object_detail, object_list
from freenasUI.middleware.notifier import notifier
from freenasUI.common.helperview import helperView
import os, commands

@login_required
def index(request, objtype = None):
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
    return render_to_response('freenas/index.html', variables)

@login_required
def top(request):
    top = os.popen('top').read()
    variables = RequestContext(request, {
        'top': top,
    })
    return render_to_response('freenas/status/top.xml', variables, mimetype='text/xml')

def login(request):
    username = request.POST['username']
    password = request.POST['password']
    user = authenticate(username=username, password=password)
    if user is not None:
        if user.is_active:
            login(request, user)
            # Redirect to a success page.
        return HttpResponseRedirect('/freenas/login/') # Redirect after POST

def logout(request):
    logout(request)
    # Redirect to a success page.
    return HttpResponseRedirect('/freenas/logout/') # Redirect after POST


## System Section

@login_required
def reboot(request):
    """ reboots the system """
    notifier().restart("system")
    return render_to_response('freenas/system/reboot.html')

@login_required
def shutdown(request):
    """ shuts down the system and powers off the system """
    notifier().stop("system")
    return render_to_response('freenas/system/shutdown.html')

@login_required
def settings(request):
    return helperView(request, SettingsForm, Settings, 'freenas/system/general_setup.html')

@login_required
def password(request):
    return helperView(request, systemGeneralPasswordForm, systemGeneralPassword, 'freenas/system/general_password.html')

@login_required
def advanced(request):
    return helperView(request, AdvancedForm, Advanced, 'freenas/system/advanced.html')

@login_required
def email(request):
    return helperView(request, EmailForm, Email, 'freenas/system/advanced_email.html')

@login_required
def proxy(request):
    return helperView(request, ProxyForm, Proxy, 'freenas/system/advanced_proxy.html')

@login_required
def swap(request):
    return helperView(request, SwapForm, Swap, 'freenas/system/advanced_swap.html')

@login_required
def commandscripts(request):
    if request.method == 'POST':
        form = CommandScriptsForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = CommandScriptsForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/system/commandscripts_add.html', variables)

@login_required
def cronjob(request):
    if request.method == 'POST':
        form = CronJobForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = CronJobForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/system/cronjob.html', variables)

@login_required
def rcconf(request):
    if request.method == 'POST':
        form = rcconfForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = rcconfForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/system/rcconf.html', variables)

@login_required
def sysctl(request):
    if request.method == 'POST':
        form = sysctlForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = sysctlForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/system/sysctlMIB.html', variables)
