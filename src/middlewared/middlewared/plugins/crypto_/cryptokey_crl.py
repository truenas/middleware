import datetime

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from middlewared.service import Service

from .utils import CERT_BACKEND_MAPPINGS


class CryptoKeyService(Service):

    class Config:
        private = True

    def generate_crl(self, ca, certs, next_update=1):
        # There is a tricky case here - what happens if the root CA is compromised ?
        # In normal world scenarios, that CA is removed from app's trust store and any
        # subsequent certs it had issues wouldn't be validated by the app then. Making a CRL
        # for a revoked root CA in normal cases doesn't make sense as the thief can sign a
        # counter CRL saying that everything is fine. As our environment is controlled,
        # i think we are safe to create a crl for root CA as well which we can publish for
        # services which make use of it i.e openvpn and they'll know that the certs/ca's have been
        # compromised.
        #
        # `ca` is root ca from where the chain `certs` starts.
        # `certs` is a list of all certs ca inclusive which are to be
        # included in the CRL ( if root ca is compromised, it will be in `certs` as well ).
        private_key = self.middleware.call_sync('cryptokey.load_private_key', ca['privatekey'])
        ca_cert = x509.load_pem_x509_certificate(ca['certificate'].encode(), default_backend())

        if not private_key:
            return None

        ca_data = self.middleware.call_sync('cryptokey.load_certificate', ca['certificate'])
        issuer = {k: ca_data.get(v) for k, v in CERT_BACKEND_MAPPINGS.items()}

        crl_builder = x509.CertificateRevocationListBuilder().issuer_name(x509.Name([
            x509.NameAttribute(getattr(NameOID, k.upper()), v)
            for k, v in issuer.items() if v
        ])).last_update(
            datetime.datetime.utcnow()
        ).next_update(
            datetime.datetime.utcnow() + datetime.timedelta(next_update, 300, 0)
        )

        for cert in certs:
            crl_builder = crl_builder.add_revoked_certificate(
                x509.RevokedCertificateBuilder().serial_number(
                    self.middleware.call_sync('cryptokey.load_certificate', cert['certificate'])['serial']
                ).revocation_date(
                    cert['revoked_date']
                ).build(
                    default_backend()
                )
            )

        # https://www.ietf.org/rfc/rfc5280.txt
        # We should add AuthorityKeyIdentifier and CRLNumber at the very least

        crl = crl_builder.add_extension(
            x509.AuthorityKeyIdentifier(
                x509.SubjectKeyIdentifier.from_public_key(
                    ca_cert.public_key()
                ).digest, [x509.DirectoryName(
                    x509.Name([
                        x509.NameAttribute(getattr(NameOID, k.upper()), v)
                        for k, v in issuer.items() if v
                    ])
                )], ca_cert.serial_number
            ), False
        ).add_extension(
            x509.CRLNumber(1), False
        ).sign(
            private_key=private_key, algorithm=self.middleware.call_sync(
                'cryptokey.retrieve_signing_algorithm', {}, private_key
            ), backend=default_backend()
        )

        return crl.public_bytes(serialization.Encoding.PEM).decode()
