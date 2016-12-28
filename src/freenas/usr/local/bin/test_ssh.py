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

import django
django.setup()

from freenasUI.storage.models import Replication


def fixkey(ip):
    """Return a host key or False"""
    print "My idea of what the remote hostkey should be is wrong."
    while True:
        ret = raw_input("Would you like me to fix this? (y/n): ")
        if ret.lower() == "y":
            # ssh-keyscan handles errors and timeouts for us
            # rep will either be a key or False.  All other errors
            # are trapped by ssh-keyscan itself.
            rep = os.popen("ssh-keyscan %s 2> /dev/null" % ip).read()
            return rep or False
        elif ret.lower() == "n":
            return False
        else:
            print "Please choose either y or n."
            continue


def check_ssh(ip, port, user, key_file, retries=1):
    """Returns True if ssh works properly for the passed in parameters.
    Returns False if ssh fails and ssh-keyscan cannot get the remote host key
    or if the user chooses to not let the script try to fetch the
    correct host key or if there are ssh errors that are unrelated
    to the host keys being wrong.  For instance the IP is unreachable.
    Return a host key if ssh fails due to the host key being wrong
    but ssh-keyscan is able to get the correct key
    """
    ssh = paramiko.SSHClient()
    # Generally FreeNAS will have a known_hosts file generated
    # by ix-sshd, especially if there's a replication task in the
    # database, however if there isn't, or if it's corrupted
    # don't let that stop us.
    if os.path.isfile("/usr/local/etc/ssh/ssh_known_hosts"):
        try:
            ssh.load_system_host_keys("/usr/local/etc/ssh/ssh_known_hosts")
        except paramiko.hostkeys.InvalidHostKey:
            # TODO: Presumably if we unlink this file and don't end
            # up saving any changes to the database later on it will
            # get regenerated at some point with the same corruption.
            os.unlink("/usr/local/etc/ssh/ssh_known_hosts")

    for x in range(retries):
        try:
            ssh.connect(ip, port, username=user, key_filename=key_file)
            return True
        except (paramiko.BadHostKeyException, paramiko.SSHException) as e:
            # Errors ssh-keyscan can fix!
            if hasattr(e, "message") and ("not found in known_hosts"
                                          in e.message or "does not match!"
                                          in e.message):
                return fixkey(ip)
        except (paramiko.AuthenticationException,
                paramiko.SSHException, socket.error) as e:
            # Errors that can't be automagically fixed.  Print them out to
            # give us a clue what's going wrong.
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
    # This is a tad convoluted.  The return value of check_ssh is either:
    # True if ssh for this replication task works properly,
    # False if ssh for this replication task fails and either the
    # script cannot fix it or the user chooses not to have the
    # script try to fix it, or...
    # an ssh host key if ssh-keyscan was able to get the remote hostkey.
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
