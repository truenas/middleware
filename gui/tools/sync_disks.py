#!/usr/bin/env python
#-
# Copyright (c) 2011 iXsystems, Inc.
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

import argparse
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.join(HERE, ".."))
sys.path.append(os.path.join(HERE, "../.."))
sys.path.append('/usr/local/www')
sys.path.append('/usr/local/www/freenasUI')

from freenasUI import settings

from django.core.management import setup_environ
setup_environ(settings)

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI.middleware.notifier import notifier


def main():
    parser = argparse.ArgumentParser(description='Sync disks.')
    parser.add_argument('devs', metavar='N', type=str, nargs='*',
        help='device name(s)')
    args = parser.parse_args()
    _notifier = notifier()
    if args.devs:
        for dev in args.devs:
            dev = dev.replace("/dev/", "")
            _notifier.sync_disk(dev)
    else:
        _notifier.sync_disks()

if __name__ == "__main__":
    main()
