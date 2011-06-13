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

from os import popen, stat
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta

from freenasUI.system.models import Email
from account.models import bsdUsers

def get_freenas_version():
    version = "FreeNAS"
    try:
        fd = open("/etc/version.freenas")
    except:
        fd = None

    if fd:
        version = fd.read().strip()
        fd.close()

    return version


def get_freenas_var_by_file(file, var):
    if not file or not var:
        return None

    pipe = popen(". '%s' && echo ${%s}" % (file, var))
    val = pipe.read().strip().split('\n')
    pipe.close()

    if val:
        val = val[0]
    return val


def get_freenas_var(var, default = None):
    val = get_freenas_var_by_file("/etc/rc.freenas", var)
    if not val:
        val = default
    return val

def send_mail(subject, text, interval = timedelta(), channel = 'freenas'):
    if interval > timedelta():
        channelfile = '/tmp/.msg.%s' % (channel)
        last_update = datetime.now() - interval
        try:
            last_update = datetime.fromtimestamp(stat(channelfile).st_mtime)
        except OSError:
            pass
        timediff = datetime.now() - last_update
        if (timediff >= interval) or (timediff < timedelta()):
            f = open(channelfile, 'w')
            f.close()

    error = False
    errmsg = ''
    email = Email.objects.all().order_by('-id')[0]
    admin = bsdUsers.objects.get(bsdusr_username='root')
    msg = MIMEText(text)
    msg['Subject'] = subject
    msg['From'] = email.em_fromemail
    msg['To'] = admin.bsdusr_email
    try:
        if email.em_security == 'ssl':
            server = smtplib.SMTP_SSL(email.em_outgoingserver, email.em_port, timeout=10)
        else:
            server = smtplib.SMTP(email.em_outgoingserver, email.em_port, timeout=10)
            if email.em_security == 'tls':
                server.starttls()
        if email.em_smtp:
            server.login(email.em_user, email.em_pass)
        server.sendmail(email.em_fromemail, [admin.bsdusr_email], msg.as_string())
        server.quit()
    except Exception, e:
        errmsg = str(e)
        error = True
    return error, errmsg
