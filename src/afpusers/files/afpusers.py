#!/usr/local/bin/python

# Based on macusers perl script in netatalk3:
# Written for linux; may have to be modified for your brand of Unix.
# Support for FreeBSD added by Joe Clarke <marcus@marcuscom.com>.
# Support Solaris added by Frank Lahm <franklahm@googlemail.com>.
# Support has also been added for 16 character usernames.

import sys
import re
import platform
import subprocess
import socket
import pwd

NETATALK_PROCESS = "netatalk"
AFPD_PROCESS = "afpd"

match_rx = None

if platform.system() in ("FreeBSD", "Darwin"):
    PS_STR = "-awwxouser,pid,ppid,start,command"
    MATCH_STR = '(\w+)\s+(\d+)\s+(\d+)\s+([\d\w:]+)'
    match_rx = re.compile(MATCH_STR)
else:
    print("Unknown OS", file=sys.stderr)
    sys.exit(1)

ASIP_PORT = "afpovertcp"
ASIP_PORT_NO = 548


def AFPUsers():
    mac = {}
    MAIN_PID = None

    if platform.system() in ("FreeBSD"):
        rx = re.compile("^\S+\s+\S+\s+(\d+)\s+\d+\s+[\w\d]+\s+[\d\.:]+\s+([\d\.]+)")
        try:
            p = subprocess.Popen(["/usr/bin/sockstat", "-4"],
                                 stdout=subprocess.PIPE, encoding="utf8")
        except:
            print("Cannot popen sockstat: %s " % sys.exc_info()[0],
                  file=sys.stderr)
            sys.exit(1)

    for line in p.stdout:
        line = line.rstrip()
        if AFPD_PROCESS in line:
            m = rx.match(line)
            if m is not None:
                pid = int(m.group(1))
                try:
                    host = socket.gethostbyaddr(m.group(2))[0]
                except:
                    host = 'unknown ' + m.group(2)
                mac[pid] = host
        p.wait()

    try:
        p = subprocess.Popen(["/bin/ps", PS_STR], stdout=subprocess.PIPE,
                             encoding="utf8")
    except:
        print("Cannot popen ps the first time: %s" % sys.exc_info()[0],
              file=sys.stderr)
        sys.exit(1)

    for line in p.stdout:
        line = line.rstrip()
        if NETATALK_PROCESS in line:
            m = match_rx.match(line)
            if m is not None:
                MAIN_PID = int(m.group(2))
        p.wait()

    try:
        p = subprocess.Popen(["/bin/ps", PS_STR], stdout=subprocess.PIPE,
                             encoding="utf8")
    except:
        print("Cannot popen ps: %s" % sys.exc_info()[0], file=sys.stderr)
        sys.exit(1)

    for line in p.stdout:
        line = line.rstrip()
        if AFPD_PROCESS in line:
            m = match_rx.match(line)
            if m is not None:
                user = m.group(1)
                pid = int(m.group(2))
                ppid = int(m.group(3))
                time = m.group(4)
                if MAIN_PID and ppid != MAIN_PID:
                    uid = 0
                    fname = ""
                    temp = pwd.getpwnam(user)
                    if temp is not None:
                        uid = temp.pw_uid
                        fname = temp.pw_gecos
                    yield (pid, uid, user, fname, time, mac[pid])
        p.wait()


if __name__ == "__main__":
    print("PID      UID      Username         Name                 Logintime Mac")
    for (pid, uid, user, fname, time, mac) in AFPUsers():
        print("%-8d %-8d %-16s %-20s %-9s %s" % (pid, uid, user, fname, time, mac))
