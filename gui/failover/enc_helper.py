# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.
import socket
import subprocess
import sys
import time

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
            subprocess.Popen(["/usr/sbin/escrowd"])
            while retries > 0 and connected is False:
                try:
                    retries = retries - 1
                    sock.connect(server)
                    connected = True
                except:
                    time.sleep(1)

        # TODO
        if not connected:
            print("FATAL: Can't connect to escrowd")
            sys.exit(1)

        data = sock.recv(BUFSIZE).decode()
        if data != "220 Ready, go ahead\n":
            print("FATAL: server didn't send welcome message, exiting")
            sys.exit(2)
        self.sock = sock

    # Set key on local escrow daemon.
    def setkey(self, passphrase):
        command = "SETKEY %s\n" % (passphrase)
        self.sock.sendall(command.encode())
        data = self.sock.recv(BUFSIZE).decode()
        return (data == "250 setkey accepted.\n")
        # Push the key to remote.

    # Clear key on local escrow daemon.
    def clear(self):
        command = "CLEAR"
        self.sock.sendall(command.encode())
        data = self.sock.recv(BUFSIZE).decode()
        succeeded = (data == "200 clear succeeded.\n")
        file = open('/tmp/.failover_needop', 'w')
        return (succeeded)

    # Shutdown local escrow daemon.
    def shutdown(self):
        command = "SHUTDOWN"
        self.sock.sendall(command.encode())
        data = self.sock.recv(BUFSIZE).decode()
        return (data == "250 Shutting down.\n")

    # Get key from local escrow daemon.  Returns None if not available.
    def getkey(self):
        command = "REVEAL"
        self.sock.sendall(command.encode())
        data = self.sock.recv(BUFSIZE).decode()
        lines = data.split('\n')
        if lines[0] == "404 No passphrase present":
            return None
        elif lines[0] == "200 Approved":
            if len(lines) > 2:
                data = lines[1]
            else:
                data = self.sock.recv(BUFSIZE).decode()
                data = data.split('\n')[0]
            return data
        else:
            # Should never happen.
            return None

    # Get status of local escrow daemon.  True -- Have key; False -- No key.
    def status(self):
        command = "STATUS"
        self.sock.sendall(command.encode())
        data = self.sock.recv(BUFSIZE).decode()
        return (data == "200 keyd\n")
