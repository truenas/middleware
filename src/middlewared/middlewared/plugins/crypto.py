from middlewared.service import Service

import os

CERT_ROOT_PATH = '/etc/certificates'


class CertificateService(Service):

    def query(self, filters=None, options=None):
        if options is None:
            options = {}
        options['extend'] = 'certificate.cert_extend'
        return self.middleware.call('datastore.query', 'system.certificate', filters, options)

    def cert_extend(self, cert):
        """Extend certificate with some useful attributes

        @private
        """
        cert['cert_certificate_path'] = os.path.join(
            CERT_ROOT_PATH, '{0}.crt'.format(cert['cert_name'])
        )
        cert['cert_privatekey_path'] = os.path.join(
            CERT_ROOT_PATH, '{0}.key'.format(cert['cert_name'])
        )
        cert['cert_csr_path'] = os.path.join(
            CERT_ROOT_PATH, '{0}.csr'.format(cert['cert_name'])
        )
        return cert
