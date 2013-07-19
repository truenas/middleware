#+
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
import logging
import requests
import string
import os

from django.http import HttpResponse
from django.shortcuts import render
from django.utils import simplejson
from django.utils.translation import ugettext as _

from freenasUI.common.pipesubr import pipeopen
from freenasUI.freeadmin.views import JsonResp
from freenasUI.support import forms, models
from freenasUI.system.models import Email
from freenasUI.support.supportcaptcha import (
    SUPPORT_PROTO,
    SUPPORT_HOST,
    SUPPORT_BASE,
    SUPPORT_URL,
    SUPPORT_URL_GET,
    SUPPORT_URL_POST
)

log = logging.getLogger("support.views")

def index(request):
    try: 
        email = Email.objects.order_by("-id")[0]
        if email:
            email = email.em_fromemail
    except:
        email = None

    try:
        ticket = models.Support.objects.order_by("-id")[0]
    except IndexError:
        ticket = models.Support.objects.create()

    if request.method == "POST":
        form = forms.SupportForm(request.POST, email=email)
        if form.is_valid():
            debug_file = "/tmp/freenas-debug.txt"
            crash_file = "/var/crash/textdump"
            version_file = "/etc/version"

            files = {}
            args = ["/usr/local/bin/freenas-debug",
                "-g", "-h", "-T", "-n", "-s", "-y", "-t", "-z"]
            p1 = pipeopen(string.join(args, ' '), allowfork=True)
            debug_out = p1.communicate()[0]
            with open(debug_file, 'w') as f:
                f.write(debug_out)

            if os.path.exists(debug_file):
                files['debug_file'] = open(debug_file, 'rb')

            if os.path.exists(crash_file):
                files['crash_file'] = open(crash_file, 'rb')

            if os.path.exists(version_file):
                files['version_file'] = open(version_file, 'rb')

            payload = {
                'support_issue': request.POST['support_issue'],
                'support_description': request.POST['support_description'],
                'support_type': request.POST['support_type'],
                'support_email': request.POST['support_email'],
                'captcha_0': request.POST['captcha_0'],
                'captcha_1': request.POST['captcha_1']
            }

            i = 0
            ntries = 10 
            while i < ntries:
                try:
                    r = requests.post(SUPPORT_URL_POST, data=payload, files=files)
                    break
                except:
                    pass

                i += 1

            if r.status_code == 200:
                return JsonResp(request, message=_("Support request successfully sent"))
            else: 
                return JsonResp(
                    request,
                    error=True,
                    message=_("Error posting to URL"),
                )

    else:
        form = forms.SupportForm(email=email)

    return render(request, "support/index.html", {
        'form': form
    })
