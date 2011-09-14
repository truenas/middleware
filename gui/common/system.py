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

import os
import smtplib
import sqlite3
import subprocess
import traceback
import syslog
from email.mime.text import MIMEText
from email.Utils import formatdate
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

def get_freenas_login_version():
    # A specialized case of get_freenas_version() used by the login
    # dialog to only return the middle of the version string.
    # For example, if the file contains FreeNAS-8r7200-amd64 we want to
    # return 8r7200
    version = "FreeNAS"
    try:
        fd = open("/etc/version.freenas")
    except:
        fd = None

    if fd:
        version = fd.read().strip().split("-")
        fd.close()
        # FreeNAS-8.0.1-RC1-amd64
        if len(version) == 4:
            return "-".join(version[1:3])
        # FreeNAS-8r7200-amd64
        else:
            return version[1]

    return version

def get_freenas_var_by_file(f, var):
    assert f and var

    pipe = os.popen('. "%s"; echo "${%s}"' % (f, var, ))
    try:
        val = pipe.readlines()[-1].rstrip()
    finally:
        pipe.close()

    return val

def get_freenas_var(var, default = None):
    val = get_freenas_var_by_file("/etc/rc.freenas", var)
    if not val:
        val = default
    return val

def send_mail(subject=None, text=None, interval=timedelta(), channel='freenas', to=None, extra_headers=None):
    if interval > timedelta():
        channelfile = '/tmp/.msg.%s' % (channel)
        last_update = datetime.now() - interval
        try:
            last_update = datetime.fromtimestamp(os.stat(channelfile).st_mtime)
        except OSError:
            pass
        timediff = datetime.now() - last_update
        if (timediff >= interval) or (timediff < timedelta()):
            f = open(channelfile, 'w')
            f.close()
        else:
            return

    error = False
    errmsg = ''
    email = Email.objects.all().order_by('-id')[0]
    msg = MIMEText(text)
    if subject:
        msg['Subject'] = subject
    msg['From'] = email.em_fromemail
    if not to:
        to = bsdUsers.objects.get(bsdusr_username='root').bsdusr_email
    msg['To'] = to
    msg['Date'] = formatdate()

    if not extra_headers:
        extra_headers = {}
    for key, val in extra_headers.items():
        if msg.has_key(key):
            msg.replace_header(key, val)
        else:
            msg[key] = val

    try:
        if email.em_security == 'ssl':
            server = smtplib.SMTP_SSL(email.em_outgoingserver, email.em_port,
                                      timeout=10)
        else:
            server = smtplib.SMTP(email.em_outgoingserver, email.em_port,
                                  timeout=10)
            if email.em_security == 'tls':
                server.starttls()
        if email.em_smtp:
            server.login(email.em_user, email.em_pass)
        server.sendmail(email.em_fromemail, [to],
                        msg.as_string())
        server.quit()
    except Exception, e:
        syslog.openlog("freenas", syslog.LOG_CONS | syslog.LOG_PID, facility=syslog.LOG_MAIL)
        for line in traceback.format_exc().splitlines():
            syslog.syslog(syslog.LOG_ERR, line)
        syslog.closelog()
        errmsg = str(e)
        error = True
    return error, errmsg

def get_fstype(path):
    assert path

    if not os.access(path, os.F_OK):
        return None

    lines = subprocess.check_output(['/bin/df', '-T', path]).splitlines()

    out = (lines[len(lines) - 1]).split()

    return (out[1].upper())

def get_mounted_filesystems():
    mounted = []

    lines = subprocess.check_output(['/sbin/mount']).splitlines()

    for line in lines:
        parts = line.split()
        mountinfo = {}
        mountinfo['fs_spec'] = parts[0]
        mountinfo['fs_file'] = parts[2]
        end = min(parts[3].find(')'), parts[3].find(','))
        mountinfo['fs_vfstype'] = parts[3][1:end]
        mounted.append(mountinfo)

    return mounted

def is_mounted(**kwargs):
    ret = False

    mounted = get_mounted_filesystems()
    for mountpt in mounted:
        if 'device' in kwargs:
            if mountpt['fs_spec'] == kwargs['device']:
                ret = True
                break
        elif 'path' in kwargs:
            if mountpt['fs_file'] == kwargs['path']:
                ret = True
                break

    return ret

def mount(dev, path, mntopts=None):
    if mntopts:
        opts = ['-o', mntopts]
    else:
        opts = []

    try:
        subprocess.check_call(['/sbin/mount', ] + opts + [dev, path, ])
    except:
        return False
    else:
        return True

def umount(path):
    try:
        subprocess.check_call(['/sbin/umount', path, ])
    except:
        return False
    else:
        return True

def service_enabled(name):
    db = get_freenas_var("FREENAS_DATABASE", "/data/freenas-v1.db")
    h = sqlite3.connect(db)
    c = h.cursor()

    enabled = False
    sql = "select srv_enable from services_services " \
        "where srv_service = '%s' order by -id limit 1" % name
    c.execute(sql)
    row = c.fetchone()
    if row and row[0] != 0:
        enabled = True

    c.close()
    h.close()

    return enabled
