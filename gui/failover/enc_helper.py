#!/usr/bin/env python
#-
# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import logging
import socket
import subprocess
import os
import re
import sys
import tempfile
import time
import getpass
sys.path.append('/usr/local/www')
sys.path.append('/usr/local/www/freenasUI')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI.common.pipesubr import pipeopen
from freenasUI.freeadmin.apppool import appPool
from freenasUI.failover.models import Failover
from freenasUI.storage.models import Volume

log = logging.getLogger('tools.haenc')

BUFSIZE = 256

class LocalEscrowCtl:
    def __init__(self):
        server = "/tmp/escrowd.sock"
        connected = False
        retries = 5

        # Start escrowd on demand
        #
        # Attempt to connect the server;
        # if connection can not be established, startescrowd and
        # retry.
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(server)
            connected = True
        except:
            proc = subprocess.Popen(["/usr/sbin/escrowd"])
            while retries > 0 and connected == False:
                try:
                    retries = retries - 1
                    sock.connect(server)
                    connected = True
                except:
                    time.sleep(1)

        # TODO
        if not connected:
            print "FATAL: Can't connect to escrowd"
            sys.exit(1)

        data = sock.recv(BUFSIZE)
        if data != "220 Ready, go ahead\n":
            print "FATAL: server didn't send welcome message, exiting"
            sys.exit(2)
        self.sock = sock

    # Set key on local escrow daemon.
    def setkey(self, passphrase):
        command = "SETKEY %s\n" % (passphrase)
        self.sock.sendall(command)
        data = self.sock.recv(BUFSIZE)
        return (data == "250 setkey accepted.\n")
        # Push the key to remote.

    # Clear key on local escrow daemon.
    def clear(self):
        command = "CLEAR"
        self.sock.sendall(command)
        data = self.sock.recv(BUFSIZE)
        return (data == "200 clear succeeded.\n")

    # Shutdown local escrow daemon.
    def shutdown(self):
        command = "SHUTDOWN"
        self.sock.sendall(command)
        data = self.sock.recv(BUFSIZE)
        return (data == "250 Shutting down.\n")

    # Get key from local escrow daemon.  Returns None if not available.
    def getkey(self):
        command = "REVEAL"
        self.sock.sendall(command)
        data = self.sock.recv(BUFSIZE)
        lines = data.split('\n')
        if lines[0] == "404 No passphrase present":
            return None
        elif lines[0] == "200 Approved":
            if len(lines) > 2:
                data = lines[1]
            else:
                data = self.sock.recv(BUFSIZE)
                data = data.split('\n')[0]
            return data
        else:
            # Should never happen.
            return None

    # Get status of local escrow daemon.  True -- Have key; False -- No key.
    def status(self):
        command = "STATUS"
        self.sock.sendall(command)
        data = self.sock.recv(BUFSIZE)
        return (data == "200 keyd\n")

cmdset = set(['setkey', 'clear', 'synctopeer', 'syncfrompeer', 'shutdown', 'status', 'attachall', 'interactive'])

# Parse command options
if len(sys.argv) < 2 or not sys.argv[1] in cmdset or (sys.argv[1] == 'setkey' and len(sys.argv) != 3):
    print """
Usage: %s command [args...]

Available commands are:
  setkey [passphrase] Sets passphrase
  clear               Clears passphrase
  synctopeer          Transfer local passphrase to remote system
  syncfrompeer        Transfer remote passphrase to local system
  shutdown            Shuts down escrow daemon
  status              Inquiry escrow daemon status
  attachall           Attach volumes with the escrowed passphrase
          """ % sys.argv[0]
    sys.exit(1)

escrowctl = LocalEscrowCtl()
cmd = sys.argv[1]
rv = "Unknown"
if cmd == 'setkey':
    rv = escrowctl.setkey(sys.argv[2])
elif cmd == 'clear':
    rv = escrowctl.clear()
elif cmd == 'shutdown':
    rv = escrowctl.shutdown()
elif cmd == 'status':
    rv = escrowctl.status()
    if rv:
        print "Escrow have the passphrase"
    else:
        print "Escrow running without passphrase"
elif cmd == 'attachall':
    with tempfile.NamedTemporaryFile() as tmp:
        tmp.file.write(escrowctl.getkey() or "")
        tmp.file.flush()
        procs = []
        failed_drive = 0
        failed_volume = 0
        for vol in Volume.objects.filter(vol_encrypt__exact=2):
            keyfile = vol.get_geli_keyfile()
            for ed in vol.encrypteddisk_set.all():
                provider = ed.encrypted_provider
                if not os.path.exists('/dev/%s.eli' % provider):
                    proc = pipeopen("geli attach -j %s -k %s %s" % (
                        tmp.name, keyfile, provider) , quiet=True)
                    procs.append(proc)
            for proc in procs:
                msg = proc.communicate()[1]
                if proc.returncode != 0:
                    print ("Unable to attach GELI provider: %s" % (msg))
                    log.warn("Unable to attach GELI provider: %s", (msg))
                    failed_drive += 1
            importcmd = "zpool import -f -R /mnt %s" % (vol.vol_name)
            proc = pipeopen(importcmd)
            proc.communicate()
            if proc.returncode != 0:
                failed_volume += 1
        if failed_drive > 0:
            print "ERROR: %d drives can not be attached" % (failed_drive)
        rv = (failed_volume == 0)
        try:
            if rv:
                os.unlink('/tmp/.failover_needop')
            else:
                file = open('/tmp/.failover_needop', 'w')
        except:
            pass
elif cmd == 'interactive':
    passphrase = getpass.getpass()
    if passphrase:
        rv = escrowctl.setkey(passphrase)
        os.system("/bin/sh /etc/carp-state-change-hook carp0 LINK_UP")
else:
    peer = str(Failover.objects.all()[0].ipaddress)
    sshcmd = "/usr/bin/ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=7 %s" % (peer)
    if cmd == 'synctopeer':
        passphrase = escrowctl.getkey()
        if passphrase:
            sshcmd = "%s /usr/local/bin/python /usr/local/www/freenasUI/failover/enc_helper.py setkey %s" % (sshcmd, passphrase)
        else:
            print "ERROR: passphrase unavailable."
    elif cmd == 'syncfrompeer':
        sshcmd = "%s /usr/local/bin/python /usr/local/www/freenasUI/failover/enc_helper.py synctopeer" % (sshcmd)
    sshcmd = pipeopen(sshcmd, quiet=True)
    msg = sshcmd.communicate()[1]
    rv = (sshcmd.returncode == 0)
    if not rv:
        print msg

if rv:
    print "Succeeded."
else:
    print "Failed."
