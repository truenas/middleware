from cryptography.hazmat.primitives.asymmetric import dsa, ec, rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from middlewared.service import private, Service

from .query_utils import normalize_cert_attrs
from .utils import (
    CA_TYPE_EXISTING, CA_TYPE_INTERNAL, CA_TYPE_INTERMEDIATE, CERT_TYPE_EXISTING, CERT_TYPE_INTERNAL,
    CERT_TYPE_CSR, RE_CERTIFICATE,
)


class CertificateService(Service):

    class Config:
        cli_namespace = 'system.certificate'

    @private
    async def cert_extend_context(self, rows, extra):
        context = {
            'cas': {
                c['id']: c for c in await self.middleware.call('certificateauthority.query')
            }
        }
        return context

    @private
    async def cert_extend(self, cert):
        """Extend certificate with some useful attributes."""

        if cert.get('signedby'):
            # We query for signedby again to make sure it's keys do not have the "cert_" prefix and it has gone through
            # the cert_extend method
            # Datastore query is used instead of certificate.query to stop an infinite recursive loop

            cert['signedby'] = await self.middleware.call(
                'datastore.query',
                'system.certificateauthority',
                [('id', '=', cert['signedby']['id'])],
                {
                    'prefix': 'cert_',
                    'extend': 'certificate.cert_extend',
                    'get': True
                }
            )

        normalize_cert_attrs(cert)

        if cert['cert_type'] == 'CA':
            # TODO: Should we look for intermediate ca's as well which this ca has signed ?
            cert['signed_certificates'] = len((
                await self.middleware.call(
                    'datastore.query',
                    'system.certificate',
                    [['signedby', '=', cert['id']]],
                    {'prefix': 'cert_'}
                )
            ))

            ca_chain = await self.middleware.call('certificateauthority.get_ca_chain', cert['id'])
            cert.update({
                'revoked_certs': list(filter(lambda c: c['revoked_date'], ca_chain)),
                'can_be_revoked': bool(cert['privatekey']) and not cert['revoked'],
            })
        else:
            cert['can_be_revoked'] = bool(cert['signedby']) and not cert['revoked']

        def cert_issuer(cert):
            issuer = None
            if cert['type'] in (CA_TYPE_EXISTING, CERT_TYPE_EXISTING):
                issuer = "external"
            elif cert['type'] == CA_TYPE_INTERNAL:
                issuer = "self-signed"
            elif cert['type'] in (CERT_TYPE_INTERNAL, CA_TYPE_INTERMEDIATE):
                issuer = cert['signedby']
            elif cert['type'] == CERT_TYPE_CSR:
                issuer = "external - signature pending"
            return issuer

        cert['issuer'] = cert_issuer(cert)

        cert['chain_list'] = []
        certs = []
        if len(RE_CERTIFICATE.findall(cert['certificate'] or '')) > 1:
            certs = RE_CERTIFICATE.findall(cert['certificate'])
        elif cert['type'] != CERT_TYPE_CSR:
            certs = [cert['certificate']]
            signing_CA = cert['issuer']
            # Recursively get all internal/intermediate certificates
            # FIXME: NONE HAS BEEN ADDED IN THE FOLLOWING CHECK FOR CSR'S WHICH HAVE BEEN SIGNED BY A CA
            while signing_CA not in ["external", "self-signed", "external - signature pending", None]:
                certs.append(signing_CA['certificate'])
                signing_CA['issuer'] = cert_issuer(signing_CA)
                signing_CA = signing_CA['issuer']

        failed_parsing = False
        for c in certs:
            if c and await self.middleware.call('cryptokey.load_certificate', c):
                cert['chain_list'].append(c)
            else:
                self.cert_extend_report_error('certificate chain', cert)
                break

        if certs:
            # This indicates cert is not CSR and a cert
            cert_data = await self.middleware.call('cryptokey.load_certificate', cert['certificate'])
            cert.update(cert_data)
            if not cert_data:
                self.cert_extend_report_error('certificate', cert)
                failed_parsing = True

        if cert['privatekey']:
            key_obj = await self.middleware.call('cryptokey.load_private_key', cert['privatekey'])
            if key_obj:
                if isinstance(key_obj, Ed25519PrivateKey):
                    cert['key_length'] = 32
                else:
                    cert['key_length'] = key_obj.key_size
                if isinstance(key_obj, (ec.EllipticCurvePrivateKey, Ed25519PrivateKey)):
                    cert['key_type'] = 'EC'
                elif isinstance(key_obj, rsa.RSAPrivateKey):
                    cert['key_type'] = 'RSA'
                elif isinstance(key_obj, dsa.DSAPrivateKey):
                    cert['key_type'] = 'DSA'
                else:
                    cert['key_type'] = 'OTHER'
            else:
                self.cert_extend_report_error('private key', cert)
                cert['key_length'] = cert['key_type'] = None
        else:
            cert['key_length'] = cert['key_type'] = None

        if cert['type'] == CERT_TYPE_CSR:
            csr_data = await self.middleware.call('cryptokey.load_certificate_request', cert['CSR'])
            if csr_data:
                cert.update(csr_data)

                cert.update({k: None for k in ('from', 'until')})  # CSR's don't have from, until - normalizing keys
            else:
                self.cert_extend_report_error('csr', cert)
                failed_parsing = True

        if failed_parsing:
            # Normalizing cert/csr
            # Should we perhaps set the value to something like "MALFORMED_CERTIFICATE" for this list off attrs ?
            cert.update({
                key: None for key in [
                    'digest_algorithm', 'lifetime', 'country', 'state', 'city', 'from', 'until',
                    'organization', 'organizational_unit', 'email', 'common', 'san', 'serial',
                    'fingerprint', 'extensions'
                ]
            })

        cert['parsed'] = not failed_parsing

        return cert

    cert_extend_reported_errors = set()

    @private
    def cert_extend_report_error(self, title, cert):
        item = (title, cert['name'])
        if item not in self.cert_extend_reported_errors:
            self.logger.debug('Failed to load %s of %s', title, cert['name'])
            self.cert_extend_reported_errors.add(item)
