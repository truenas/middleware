# Copyright 2014 iXsystems, Inc.
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
import logging
import re

from OpenSSL import crypto

from freenasUI.middleware.client import client, ClientException

log = logging.getLogger('common.ssl')
CERT_CHAIN_REGEX = re.compile(r"(-{5}BEGIN[\s\w]+-{5}[^-]+-{5}END[\s\w]+-{5})+", re.M | re.S)


def load_certificate(buf):
    with client as c:
        try:
            return c.call('certificate.load_certificate', buf)
        except ClientException as e:
            raise e


#
# This will raise an exception if it's an encrypted private key
# and no password is provided. Unfortunately, the exception type
# is generic and no error string is provided. The purpose here is
# to determine if this is an encrypted private key or not. If it not,
# then the key will load and return fine. If it is encrypted, then it
# will load if the correct passphrase is provided, otherwise it will
# throw an exception.
#


def export_certificate_chain(buf):
    certificates = []
    matches = CERT_CHAIN_REGEX.findall(buf)
    for m in matches:
        certificate = crypto.load_certificate(crypto.FILETYPE_PEM, m)
        certificates.append(crypto.dump_certificate(crypto.FILETYPE_PEM, certificate))

    return ''.join(certificates).strip()


def export_certificate(buf):
    cert = crypto.load_certificate(crypto.FILETYPE_PEM, buf)
    return crypto.dump_certificate(crypto.FILETYPE_PEM, cert)


def export_privatekey(buf, passphrase=None):
    key = crypto.load_privatekey(
        crypto.FILETYPE_PEM,
        buf,
        passphrase=passphrase.encode() if passphrase else None
    )

    return crypto.dump_privatekey(
        crypto.FILETYPE_PEM,
        key,
        passphrase=passphrase.encode() if passphrase else None
    )


def get_certificate_path(name):
    from freenasUI.system.models import Certificate

    try:
        certificate = Certificate.objects.get(cert_name=name)
        path = certificate.get_certificate_path()
    except Exception:
        path = None

    return path


def get_privatekey_path(name):
    from freenasUI.system.models import Certificate

    try:
        certificate = Certificate.objects.get(cert_name=name)
        path = certificate.get_privatekey_path()
    except Exception:
        path = None

    return path


def get_certificateauthority_path(name):
    from freenasUI.system.models import CertificateAuthority

    try:
        certificate = CertificateAuthority.objects.get(cert_name=name)
        path = certificate.get_certificate_path()
    except Exception:
        path = None

    return path


def get_certificateauthority_privatekey_path(name):
    from freenasUI.system.models import CertificateAuthority

    try:
        certificate = CertificateAuthority.objects.get(cert_name=name)
        path = certificate.get_privatekey_path()
    except Exception:
        path = None

    return path
