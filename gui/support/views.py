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
import string
import time

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from django.shortcuts import render
from django.utils.translation import ugettext as _

from freenasUI.account.models import bsdUsers
from freenasUI.common.pipesubr import pipeopen
from freenasUI.freeadmin.views import JsonResp
from freenasUI.network.models import GlobalConfiguration
from freenasUI.support import forms
from freenasUI.system.models import Email

log = logging.getLogger("support.views")

def send_support_request(support_info):
    hostname = GlobalConfiguration.objects.all().order_by('-id')[0].gc_hostname

    dir = "/var/tmp/ixdiagnose"
    dump = "%s/ixdiagnose.tgz" % dir
    filename = dump.split('/')[-1]

    #
    # Run ixdiagnose, saving the output as /var/tmp/ixdiagnose/ixdiagnose.tgz
    #
    opts = ["/usr/local/bin/ixdiagnose", "-d", dir, "-s", "-F"]
    p1 = pipeopen(string.join(opts, ' '), allowfork=True)
    debug = p1.communicate()[0]
    p1.wait()

    #
    # Grab the contents of the tarball
    #
    with open(dump, "r") as f:
        ixdiagnose_output = f.read().strip()
        f.close()

    #
    # Remove the files created by ixdiagnose with a hammer
    #
    opts = ["/bin/rm", "-r", "-f", dir]
    p1 = pipeopen(string.join(opts, ' '), allowfork=True)
    p1.wait()

    #
    # Create a multipart email
    #
    msg = MIMEMultipart()
    msg['To'] = "truenas-support@ixsystems.com"
    msg['From'] = support_info['support_email']
    msg['Subject'] = support_info['support_subject']
    msg.preamble = "support request"

    #
    # Attach the body of the email
    #
    at = MIMEText(support_info['support_description'])
    msg.attach(at)

    #
    # Attach the tarball
    #
    at = MIMEBase("application", "x-gtar-compressed")
    at.set_payload(ixdiagnose_output)
    at.add_header("Content-Disposition", "attachment",
        filename="%s-%s-ixdiagnose.tgz" % (
            hostname.encode('utf-8'),
            time.strftime('%Y%m%d%H%M%S')
        ) 
    )
    encoders.encode_base64(at)

    msg.attach(at)
    msg = msg.as_string()

    #
    # Send it away!
    #
    opts = ["/usr/sbin/sendmail", "-t"]
    p1 = pipeopen(string.join(opts, ' '), allowfork=True)
    p1.communicate(input=msg)[0]


def email_is_configured():
    try:
        email = Email.objects.all().order_by("id")[0]
    except:
        return False

    if not email.em_fromemail:
        return False
    if not email.em_outgoingserver:
        return False
    if not email.em_port:
        return False
    if email.em_smtp and (not email.em_user or not email.em_pass):
        return False
    root_email = bsdUsers.objects.get(bsdusr_username='root').bsdusr_email  
    if not root_email:
        return False

    return True


def index(request):

    if request.method == "POST":
        form = forms.SupportForm(request.POST)
        if form.is_valid():
            error = None
            support_info = {
                'support_email': request.POST['support_email'],
                'support_subject': request.POST['support_subject'],
                'support_description': request.POST['support_description']
            }

            try:  
                send_support_request(support_info)
                events = ["refreshSupport()"]

            except Exception as e:
                return JsonResp(request, error=True, message=e)

            return JsonResp(request, message=_("Support request successfully sent"),
                events=events)

    else:
        form = forms.SupportForm()

    return render(request, "support/index.html", {
        'form': form,
        'email_configured': email_is_configured()
    })
