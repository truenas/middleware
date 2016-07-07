from middlewared.service import Service
from OpenSSL import crypto

import logging
import os
import re

CERT_ROOT_PATH = '/etc/certificates'
RE_CERTIFICATE = re.compile(r"(-{5}BEGIN[\s\w]+-{5}[^-]+-{5}END[\s\w]+-{5})+", re.M | re.S)
logger = logging.getLogger('plugins.crypto')


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
        cert['cert_chain_list'] = []
        if cert['cert_chain']:
            certs = RE_CERTIFICATE.findall(cert['cert_certificate'])
        else:
            certs = [cert['cert_certificate']]
        try:
            for c in certs:
                # XXX Why load certificate if we are going to dump it right after?
                # Maybe just to verify its integrity?
                # Logic copied from freenasUI
                cert_obj = crypto.load_certificate(crypto.FILETYPE_PEM, c)
                cert['cert_chain_list'].append(
                    crypto.dump_certificate(crypto.FILETYPE_PEM, cert_obj)
                )
        except:
            logger.debug('Failed to load certificate {0}'.format(cert['cert_name']), exc_info=True)

        try:
            if cert['cert_privatekey']:
                key_obj = crypto.load_privatekey(crypto.FILETYPE_PEM, cert['cert_privatekey'])
                cert['cert_privatekey'] = crypto.dump_privatekey(crypto.FILETYPE_PEM, key_obj)
        except:
            logger.debug('Failed to load privatekey {0}'.format(cert['cert_name']), exc_info=True)

        try:
            if cert['cert_CSR']:
                csr_obj = crypto.load_certificate_request(crypto.FILETYPE_PEM, cert['cert_CSR'])
                cert['cert_CSR'] = crypto.dump_certificate_request(crypto.FILETYPE_PEM, csr_obj)
        except:
            logger.debug('Failed to load csr {0}'.format(cert['cert_name']), exc_info=True)

        return cert
