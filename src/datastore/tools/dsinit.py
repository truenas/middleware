#!/usr/local/bin/python2.7
#+
# Copyright 2015 iXsystems, Inc.
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
#####################################################################

import argparse
import os
import sys
import string
import launchd
import json


DEFAULT_CONFIGFILE = '/usr/local/etc/middleware.conf'


def read_config(filename):
    try:
        f = open(filename)
        conf = json.load(f)
        f.close()
    except IOError, err:
        print("Cannot read config file: {0}".format(str(err)), file=sys.stderr)
        sys.exit(1)
    except ValueError, err:
        print("Cannot read config file: {0}".format(str(err)), file=sys.stderr)
        sys.exit(1)

    if 'datastore' not in conf:
        print("Cannot initialize datastore: configuration not found", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', metavar='CONFIG', default=DEFAULT_CONFIGFILE, help='Config file name')
    args = parser.parse_args()
    config = read_config(args.c)

    ds = config['datastore']
    db_dir = ds['dbdir']
    driver_name = ds['drier']
    driver_dir = os.path.join('/usr/local/lib/datastore/drivers', ds['driver'])

    with open(os.path.join(driver_dir, driver_name + '.json'), 'r') as f:
        plist = f.read()

    vars = {
        'dbdir': db_dir,
        'driverdir': driver_dir
    }

    template = string.Template(plist)
    plist = template.safe_substitute(**vars)

    try:
        plist = json.loads(plist)
    except ValueError:
        print("Cannot load driver plist generated from: {0}".format(driver_name + '.json'), file=sys.stderr)
        sys.exit(1)

    try:
        launchd.load(plist)
    except OSError, e:
        print("Cannot load datastore job: {0}".format(e))
        sys.exit(1)


if __name__ == '__main__':
    main()
