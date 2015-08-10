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

import logging
import os
import re
import sys

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI',
])

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI.system.models import (
    Settings,
    Certificate,
)

from OpenSSL import crypto

log = logging.getLogger('tools.updatessl')


def load_certificate(buf):
    cert = crypto.load_certificate(crypto.FILETYPE_PEM, buf)

    cert_info = {}
    cert_info['country'] = cert.get_subject().C
    cert_info['state'] = cert.get_subject().ST
    cert_info['city'] = cert.get_subject().L
    cert_info['organization'] = cert.get_subject().O
    cert_info['common'] = cert.get_subject().CN
    cert_info['email'] = cert.get_subject().emailAddress

    signature_algorithm = cert.get_signature_algorithm()
    m = re.match('^(.+)[Ww]ith', signature_algorithm)
    if m:
        cert_info['digest_algorithm'] = m.group(1).upper()

    return cert_info


#
# This will raise an exception if it's an encrypted private key
# and no password is provided. Unfortunately, the exception type
# is generic and no error string is provided. The purpose here is 
# to determine if this is an encrypted private key or not. If it not,
# then the key will load and return fine. If it is encrypted, then it 
# will load if the correct passphrase is provided, otherwise it will
# throw an exception.
#
def load_privatekey(buf, passphrase=None):
    return crypto.load_privatekey(
        crypto.FILETYPE_PEM,
        buf,
        passphrase=lambda x: str(passphrase) if passphrase else ''
    )


def export_privatekey(buf, passphrase=None):
    key = crypto.load_privatekey(
        crypto.FILETYPE_PEM,
        buf,
        passphrase=str(passphrase) if passphrase else None
    )

    return crypto.dump_privatekey(
        crypto.FILETYPE_PEM,
        key,
        passphrase=str(passphrase) if passphrase else None
    )



def main(certfile,keyfile):
    """ This function reads the certificates that were ported form
    pre-certmanager to 9.3 post-certmanager in the update and
    tries to parse, import and save them into the new Cert UI model db.
    Once it has done so successfully,it then goes ahead to set the webui
    setting's certfile to the above created cert object"""

    # Try to read the certfile and private keyfile and parse them
    # into respective vars, throw appropriate errors if files notice
    # found and then exit with return status 1.
    try:
        with open (certfile, "r") as f:
            crt = f.read()
    except IOError:
        print "Cannot read certfile specified at %s" % certfile
        sys.exit(1)
    try:
        with open (keyfile, "r") as f:
            key = f.read()
    except IOError:
        print "Cannot read keyfile specified at %s" % keyfile
        sys.exit(1)
    
    # Now for the actual parsing to meet the new cert ui reqs
    # as well as the creation of the new cert object in the django db
    cert_info = load_certificate(crt)
    created_cert = Certificate.objects.create(
                       cert_name = "freenas-pre-certui",
                       cert_type = 'CERT_EXISTING',
                       cert_certificate = crt,
                       cert_privatekey = export_privatekey(key), 
                       cert_country = cert_info['country'],
                       cert_state = cert_info['state'],
                       cert_city = cert_info['city'],
                       cert_organization = cert_info['organization'],
                       cert_common = cert_info['common'],
                       cert_email = cert_info['email'],
                       cert_digest_algorithm = cert_info['digest_algorithm']
                   )

    # Now to set this cert as the webui cert in the system settings model
    fnassettings = Settings.objects.all()[0]
    fnassettings.stg_guicertificate = created_cert
    fnassettings.save()
    
    # Note we do not need ot call ix-ssl as this python program is called
    # by ix-update which is higher up in the rcorder than ix-ssl, as a result
    # of which ix-ssl will be called later-on either ways.
    # HOWEVER, if you do run this file as a standalone do call ix-ssl service
    # yourself as well as ix-nginx and the works.
    

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
        main(sys.argv[1],sys.argv[2])
