#!/usr/local/bin/python
#
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

import logging
import os
import re
import sys

from middlewared.client import Client

log = logging.getLogger('tools.updatessl')

RE_CERTIFICATE = re.compile(r"(-{5}BEGIN[\s\w]+-{5}[^-]+-{5}END[\s\w]+-{5})+", re.M | re.S)


def main(certfile, keyfile):
    """ This function reads the certificates that were ported form
    pre-certmanager to 9.3 post-certmanager in the update and
    tries to parse, import and save them into the new Cert UI model db.
    Once it has done so successfully,it then goes ahead to set the webui
    setting's certfile to the above created cert object"""

    # Try to read the certfile and private keyfile and parse them
    # into respective vars, throw appropriate errors if files notice
    # found and then exit with return status 1.
    try:
        with open(certfile, "r") as f:
            crt = f.read()
    except IOError:
        print("Cannot read certfile specified at %s" % certfile)
        sys.exit(1)
    try:
        with open(keyfile, "r") as f:
            key = f.read()
    except IOError:
        print("Cannot read keyfile specified at %s" % keyfile)
        sys.exit(1)

    with Client() as c:
        created_cert = {
            'name': 'freenas-pre-certui',
            'type': 0x00000008,
            'certificate': crt,
            'privatekey': key,
            'chain': True if len(RE_CERTIFICATE.findall(crt)) > 1 else False,
        }
        created_cert.update(c.call('certificate.load_certificate', crt))

        id = c.call(
            'datastore.insert',
            'system.certificate',
            created_cert,
            {'prefix': 'cert_'}
        )

        c.call('system.general.update', {'ui_certificate': id})


def usage():
    usage_str = """usage: %s cert key
    cert: The full path to the certificate file
    key : The full path to the privatekey file of the cert specificed""" \
        % (os.path.basename(sys.argv[0]), )
    sys.exit(usage_str)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        usage()
    else:
        main(sys.argv[1], sys.argv[2])
