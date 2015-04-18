#!/usr/bin/env python
#-
# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#

import os
import paramiko
import socket
import sys

sys.path.append('/usr/local/www')
sys.path.append('/usr/local/www/freenasUI')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI.storage.models import Replication


def fixkey(ip):
    print "My idea of what the remote hostkey should be is wrong."
    while True:
        ret = raw_input("Would you like me to fix this? (y/n): ")
        if ret.lower() == "y" or ret.lower() == "yes":
            rep = os.popen("ssh-keyscan %s 2> /dev/null" % ip).read()
            return rep
        elif ret.lower() == "n" or ret.lower() == "no":
            break
        else:
            print "Please choose either y or n."
            continue


def check_ssh(ip, port, user, key_file, retries=1):
    ssh = paramiko.SSHClient()
    if os.path.isfile("/etc/ssh/ssh_known_hosts"):
        try:
            ssh.load_system_host_keys("/etc/ssh/ssh_known_hosts")
        except paramiko.hostkeys.InvalidHostKey:
            os.unlink("/etc/ssh/ssh_known_hosts")

    for x in range(retries):
        try:
            ssh.connect(ip, port, username=user, key_filename=key_file)
            return True
        except (paramiko.BadHostKeyException, paramiko.SSHException) as e:
            if hasattr(e, "message") and ("not found in known_hosts"
                                          in e.message or "does not match!"
                                          in e.message):
                return fixkey(ip)
        except (paramiko.AuthenticationException,
                paramiko.SSHException, socket.error) as e:
            print e
    return False

replication_tasks = Replication.objects.all()
for replication in replication_tasks:
    print "Replication task: %s" % replication
    if not replication.repl_enabled:
        print("%s replication not enabled" % replication)
    remote = replication.repl_remote.ssh_remote_hostname.__str__()
    remote_port = replication.repl_remote.ssh_remote_port
    if replication.repl_remote.ssh_remote_dedicateduser_enabled:
        user = replication.repl_remote.ssh_remote_dedicateduser
    else:
        user = "root"
    ret = check_ssh(remote, remote_port, user, "/data/ssh/replication")
    if ret is True:
        print "Status: OK"
        print
    elif ret is False:
        print "Status: Failed"
        print
    else:
        replication.repl_remote.ssh_remote_hostkey = ret
        replication.repl_remote.save()
        os.system("service ix-sshd start")
        print "Status: Hostkeys fixed"
        print
