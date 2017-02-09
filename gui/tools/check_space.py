#!/usr/bin/env python
#
# Copyright (c) 2012 iXsystems, Inc.
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
import decimal
import os
import re
import subprocess
import sys

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI'
])

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

import django
django.setup()

from freenasUI.common.system import send_mail


TO_MB = {
    'T': 1048576,
    'G': 1024,
    'M': 1,
    'K': decimal.Decimal('0.0009765625'),
}


def to_mbytes(string):

    unit = string[-1].upper()
    value = decimal.Decimal(string[:-1])
    return value * TO_MB.get(unit, 1)


def email(dataset, threshold, avail):
    send_mail(subject="Volume threshold",
              text="""Hi,

Your volume %s has reached the threshold of %s.
Currently there is %s of available space.
""" % (dataset, threshold, avail))


def _size_or_perc(string):
    last = string[-1]
    if last.upper() not in ('T', 'G', 'M', 'K', '%'):
        raise argparse.ArgumentTypeError(
            "This is not a valid size, use a suffix: T, G, M, K or %"
        )
    return string


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-d',
        '--dataset',
        required=True,
        type=str,
    )
    parser.add_argument(
        '-t',
        '--threshold',
        required=True,
        type=_size_or_perc,
    )
    args = parser.parse_args(argv)

    pipe = subprocess.Popen([
        "/sbin/zfs",
        "list",
        "-Hr",
    ],
        stdout=subprocess.PIPE,
        stdin=subprocess.PIPE)
    output = pipe.communicate()[0]
    if pipe.returncode != 0:
        print("Dataset not found")
        sys.exit(1)

    reg = re.search(r'^%s\b.*' % (args.dataset, ), output, re.M)
    if not reg:
        print("Dataset not found")
        sys.exit(1)
    line = reg.group(0)
    o_used, o_avail, o_refer = line.split('\t')[1:4]

    used = to_mbytes(o_used)
    avail = to_mbytes(o_avail)

    if args.threshold[-1] == '%':
        threshold = (used + avail) * decimal.Decimal(args.threshold[:-1]) / 100
    else:
        threshold = to_mbytes(args.threshold)

    sentinel_file = "/var/tmp/check_space.%s" % (
        args.dataset.replace('/', '_'),
    )

    if avail < threshold:
        if not os.path.exists(sentinel_file):
            email(args.dataset, args.threshold, o_avail)
            open(sentinel_file, 'w').close()
        sys.exit(2)
    else:
        try:
            os.unlink(sentinel_file)
        except:
            pass


if __name__ == '__main__':
    main(sys.argv[1:])
