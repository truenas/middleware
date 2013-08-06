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

from tempfile import NamedTemporaryFile

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
            error = None
            support_info = {
                'support_issue': request.POST['support_issue'],
                'support_description': request.POST['support_description'],
                'support_type': request.POST['support_type'],
                'support_email': request.POST['support_email']
            }

            try:
                f = NamedTemporaryFile(delete=False)
                f.write(simplejson.dumps(support_info))
                f.close()

                args = ["/usr/local/bin/ixdiagnose", "-t", f.name]
                p1 = pipeopen(string.join(args, ' '), allowfork=True)
                p1.communicate()

            except Exception as e:
                error = e

            os.unlink(f.name)

            if not error:
                return JsonResp(request, message=_("Support request successfully sent"))
            else:
                return JsonResp(request, error=True, message=error)

    else:
        form = forms.SupportForm(email=email)

    return render(request, "support/index.html", {
        'form': form
    })
