#!/usr/local/bin/python
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

import os, subprocess, sqlite3, pickle, sys

PERSIST_DATA = "/data/mfi.pkl"

# Check to see is there are any mfi devices

devs = os.listdir("/dev")

for dev in devs:
    if dev.startswith("mfi"):
        # mfi found, proceed
        # check to see if there's output from a previous run
        data = {}
        if os.path.isfile(PERSIST_DATA):
            pkl_file = open(PERSIST_DATA, "rb")
            data = pickle.load(pkl_file)
            pkl_file.close()

        temp_list = []
        ret = os.popen("/usr/sbin/mfiutil show events -c crit").readlines()
        for line in ret:
            temp_list.append(line.strip().split(" "))
        send_email = False
        for line in temp_list:
            key = line[0]
            if key not in list(data.keys()):
                data[line[0]] = " ".join(line[1:])
                send_email = True

        # Cache the controller log for future runs.  This is done so
        # that an email alert is only sent for new events
        pkl_file = open(PERSIST_DATA, "wb")
        pickle.dump(data, pkl_file, -1)
        pkl_file.close()

        if send_email:
            conn = sqlite3.connect("/data/freenas-v1.db")
            c = conn.cursor()
            c.execute("SELECT em_fromemail FROM system_email ORDER BY -id LIMIT 1")
            for row in c:
                to_addr = str(row[0])
            if len(to_addr) > 0:
                fm = os.popen("""grep -E '^root:' /etc/aliases | """
                              """awk '{print $2'}""").readlines()
                if fm:
                    for line in fm:
                         addy = line.strip()
                else:
                    # This code path results in not sending mail.  To
                    # ensure that mail is sent when email is configured
                    # remove the cached controller log
                    os.remove(PERSIST_DATA)
                    sys.exit()
                message = ""
                for key in list(data.keys()):
                    message += key + " " + data[key] + "\n"
                cmd = """echo '%s' | mailx -s 'RAID status' %s""" % (message, addy)
                p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
                output, errors = p.communicate()
                # TODO: If this fails we should clear the log cache so
                # we retry sending mail on the next run
                sys.exit()
            else:
                # This code path results in not sending mail.  To
                # ensure that mail is sent when email is configured
                # remove the cached controller log
                os.remove(PERSIST_DATA)
