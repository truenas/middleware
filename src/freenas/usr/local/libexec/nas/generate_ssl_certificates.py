#!/usr/local/bin/python

import os
import string
import sys

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI'
])

os.environ["DJANGO_SETTINGS_MODULE"] = "freenasUI.settings"

from django.db.models.loading import cache
cache.get_apps()

from freenasUI.system import models


def write_certificates(certs):
    for cert in certs:
        if not os.path.exists(cert.cert_root_path):
            os.mkdir(cert.cert_root_path, 0755)

        if cert.cert_certificate:
            try:
                cert.write_certificate()
            except Exception as e:
                print >> sys.stderr, "ERROR: %s" % e

        if cert.cert_privatekey:
            try:
                cert.write_privatekey()
                os.chmod(cert.get_privatekey_path(), 0400)
            except Exception as e:
                print >> sys.stderr, "ERROR: %s" % e

        if cert.cert_type & models.CERT_TYPE_CSR and cert.cert_CSR:
            try:
                cert.write_CSR()
            except Exception as e:
                print >> sys.stderr, "ERROR: %s" % e


def main():
    CAs = models.CertificateAuthority.objects.all()
    write_certificates(CAs)

    certs = models.Certificate.objects.all()
    write_certificates(certs)

if __name__ == '__main__':
    main()
