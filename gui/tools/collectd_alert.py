#!/usr/local/bin/python2.7
#
# Copyright (c) 2017 iXsystems, Inc.
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

import cPickle as pickle
import os
import re
import sys

from lockfile import LockFile, LockTimeout

COLLECTD_FILE = '/tmp/.collectdalert'


def main():

    lock = LockFile(COLLECTD_FILE)
    while not lock.i_am_locking():
        try:
            lock.acquire(timeout=5)
        except LockTimeout:
            lock.break_lock()

    data = {}
    if os.path.exists(COLLECTD_FILE):
        with open(COLLECTD_FILE, 'rb') as f:
            try:
                data = pickle.loads(f.read())
            except:
                pass

    text = sys.stdin.read().replace('\n\n', '\nMessage: ', 1)
    v = dict(re.findall(r"(?P<name>.*?): (?P<value>.*?)\n", text))

    k = v["Plugin"]
    if "PluginInstance" in v.keys():
        k += "-" + v["PluginInstance"]
    k += "/" + v["Type"]
    if "TypeInstance" in v.keys():
        k += "-" + v["TypeInstance"]

    if v["Severity"] == "OKAY":
        data.pop(k, None)
    else:
        data[k] = v;

    with open(COLLECTD_FILE, 'wb') as f:
        f.write(pickle.dumps(data))

    lock.release()


if __name__ == '__main__':
    main()
