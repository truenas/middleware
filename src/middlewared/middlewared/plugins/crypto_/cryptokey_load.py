import dateutil
import dateutil.parser
import re

from OpenSSL import crypto

from middlewared.schema import accepts, Str
from middlewared.service import Service

from .utils import RE_CERTIFICATE


class CryptoKeyService(Service):

    class Config:
        private = True

    def parse_cert_date_string(self, date_value):
        t1 = dateutil.parser.parse(date_value)
        t2 = t1.astimezone(dateutil.tz.tzlocal())
        return t2.ctime()

    @accepts(
        Str('certificate', required=True, max_length=None)
    )
    def load_certificate(self, certificate):
        try:
            # digest_algorithm, lifetime, country, state, city, organization, organizational_unit,
            # email, common, san, serial, chain, fingerprint
            cert = crypto.load_certificate(
                crypto.FILETYPE_PEM,
                certificate
            )
        except crypto.Error:
            return {}
        else:
            cert_info = self.get_x509_subject(cert)

            valid_algos = ('SHA1', 'SHA224', 'SHA256', 'SHA384', 'SHA512', 'ED25519')
            signature_algorithm = cert.get_signature_algorithm().decode()
            # Certs signed with RSA keys will have something like
            # sha256WithRSAEncryption
            # Certs signed with EC keys will have something like
            # ecdsa-with-SHA256
            m = re.match('^(.+)[Ww]ith', signature_algorithm)
            if m:
                cert_info['digest_algorithm'] = m.group(1).upper()

            if cert_info.get('digest_algorithm') not in valid_algos:
                cert_info['digest_algorithm'] = (signature_algorithm or '').split('-')[-1].strip()

            if cert_info['digest_algorithm'] not in valid_algos:
                # Let's log this please
                self.logger.debug(f'Failed to parse signature algorithm {signature_algorithm} for {certificate}')

            cert_info.update({
                'lifetime': (
                    dateutil.parser.parse(cert.get_notAfter()) - dateutil.parser.parse(cert.get_notBefore())
                ).days,
                'from': self.parse_cert_date_string(cert.get_notBefore()),
                'until': self.parse_cert_date_string(cert.get_notAfter()),
                'serial': cert.get_serial_number(),
                'chain': len(RE_CERTIFICATE.findall(certificate)) > 1,
                'fingerprint': cert.digest('sha1').decode(),
            })

            return cert_info

    def get_x509_subject(self, obj):
        cert_info = {
            'country': obj.get_subject().C,
            'state': obj.get_subject().ST,
            'city': obj.get_subject().L,
            'organization': obj.get_subject().O,
            'organizational_unit': obj.get_subject().OU,
            'common': obj.get_subject().CN,
            'san': [],
            'email': obj.get_subject().emailAddress,
            'DN': '',
            'subject_name_hash': obj.subject_name_hash() if not isinstance(obj, crypto.X509Req) else None,
            'extensions': {},
        }

        for ext in filter(
            lambda e: e.get_short_name().decode() != 'UNDEF',
            map(
                lambda i: obj.get_extension(i),
                range(obj.get_extension_count())
            ) if isinstance(obj, crypto.X509) else obj.get_extensions()
        ):
            if 'subjectAltName' == ext.get_short_name().decode():
                cert_info['san'] = [s.strip() for s in ext.__str__().split(',') if s]

            try:
                ext_name = re.sub(r"^(\S)", lambda m: m.group(1).upper(), ext.get_short_name().decode())
                cert_info['extensions'][ext_name] = 'Unable to parse extension'
                cert_info['extensions'][ext_name] = ext.__str__()
            except crypto.Error as e:
                # some certificates can have extensions with binary data which we can't parse without
                # explicit mapping for each extension. The current case covers the most of extensions nicely
                # and if it's required to map certain extensions which can't be handled by above we can do
                # so as users request.
                self.middleware.logger.error('Unable to parse extension: %s', e)

        dn = []
        subject = obj.get_subject()
        for k in filter(
            lambda k: k != 'subjectAltName' and hasattr(subject, k),
            map(lambda v: v[0].decode(), subject.get_components())
        ):
            dn.append(f'{k}={getattr(subject, k)}')

        cert_info['DN'] = f'/{"/".join(dn)}'

        if cert_info['san']:
            # We should always trust the extension instead of the subject for SAN
            cert_info['DN'] += f'/subjectAltName={", ".join(cert_info["san"])}'

        return cert_info

    @accepts(
        Str('csr', required=True, max_length=None)
    )
    def load_certificate_request(self, csr):
        try:
            csr_obj = crypto.load_certificate_request(crypto.FILETYPE_PEM, csr)
        except crypto.Error:
            return {}
        else:
            return self.get_x509_subject(csr_obj)
