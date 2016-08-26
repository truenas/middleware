from middlewared.schema import Ref, accepts
from middlewared.service import Service, private
from OpenSSL import crypto

import dateutil
import dateutil.parser
import logging
import os
import re

CA_TYPE_EXISTING = 0x01
CA_TYPE_INTERNAL = 0x02
CA_TYPE_INTERMEDIATE = 0x04
CERT_TYPE_EXISTING = 0x08
CERT_TYPE_INTERNAL = 0x10
CERT_TYPE_CSR = 0x20

CERT_ROOT_PATH = '/etc/certificates'
CERT_CA_ROOT_PATH = '/etc/certificates/CA'
RE_CERTIFICATE = re.compile(r"(-{5}BEGIN[\s\w]+-{5}[^-]+-{5}END[\s\w]+-{5})+", re.M | re.S)
logger = logging.getLogger('plugins.crypto')


class CertificateService(Service):

    @accepts(Ref('query-filters'), Ref('query-options'))
    def query(self, filters=None, options=None):
        if options is None:
            options = {}
        options['extend'] = 'certificate.cert_extend'
        return self.middleware.call('datastore.query', 'system.certificate', filters, options)

    @private
    def cert_extend(self, cert):
        """Extend certificate with some useful attributes."""
        if cert['cert_type'] in (
            CA_TYPE_EXISTING, CA_TYPE_INTERNAL, CA_TYPE_INTERMEDIATE
        ):
            root_path = CERT_CA_ROOT_PATH
        else:
            root_path = CERT_ROOT_PATH
        cert['cert_root_path'] = root_path
        cert['cert_certificate_path'] = os.path.join(
            root_path, '{0}.crt'.format(cert['cert_name'])
        )
        cert['cert_privatekey_path'] = os.path.join(
            root_path, '{0}.key'.format(cert['cert_name'])
        )
        cert['cert_csr_path'] = os.path.join(
            root_path, '{0}.csr'.format(cert['cert_name'])
        )

        def cert_issuer(cert):
            issuer = None
            if cert['cert_type'] in (CA_TYPE_EXISTING, CERT_TYPE_EXISTING):
                issuer = "external"
            elif cert['cert_type'] == CA_TYPE_INTERNAL:
                issuer = "self-signed"
            elif cert['cert_type'] in (CERT_TYPE_INTERNAL, CA_TYPE_INTERMEDIATE):
                issuer = cert['cert_signedby']
            elif cert['cert_type'] == CERT_TYPE_CSR:
                issuer = "external - signature pending"
            return issuer
        cert['cert_issuer'] = cert_issuer(cert)

        cert['cert_chain_list'] = []
        if cert['cert_chain']:
            certs = RE_CERTIFICATE.findall(cert['cert_certificate'])
        else:
            certs = [cert['cert_certificate']]
            signing_CA = cert['cert_issuer']
            # Recursively get all internal/intermediate certificates
            while signing_CA not in ["external", "self-signed", "external - signature pending"]:
                certs.append(signing_CA['cert_certificate'])
                signing_CA['cert_issuer'] = cert_issuer(signing_CA)
                signing_CA = signing_CA['cert_issuer']
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

        cert['cert_internal'] = 'NO' if cert['cert_type'] in (CA_TYPE_EXISTING, CERT_TYPE_EXISTING) else 'YES'

        if cert['cert_type'] == CERT_TYPE_CSR:
            obj = csr_obj
            # date not applicable for CSR
            cert['cert_from'] = None
            cert['cert_until'] = None
        else:
            obj = cert_obj
            notBefore = obj.get_notBefore()
            t1 = dateutil.parser.parse(notBefore)
            t2 = t1.astimezone(dateutil.tz.tzutc())
            cert['cert_from'] = t2.ctime()

            notAfter = obj.get_notAfter()
            t1 = dateutil.parser.parse(notAfter)
            t2 = t1.astimezone(dateutil.tz.tzutc())
            cert['cert_until'] = t2.ctime()

        cert['cert_DN'] = '/' + '/'.join([
            '%s=%s' % (c[0], c[1])
            for c in obj.get_subject().get_components()
        ])

        return cert


class CertificateauthorityService(Service):

    @accepts(Ref('query-filters'), Ref('query-options'))
    def query(self, filters=None, options=None):
        if options is None:
            options = {}
        options['extend'] = 'certificate.cert_extend'
        return self.middleware.call('datastore.query', 'system.certificateauthority', filters, options)
