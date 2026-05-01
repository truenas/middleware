import datetime

from middlewared.plugins.truenas_connect.utils import TNC_CERT_PREFIX
from middlewared.service import Service, ValidationErrors, private


class CertificateService(Service):

    class Config:
        cli_namespace = 'system.certificate'
        role_prefix = 'CERTIFICATE'

    @private
    async def cert_services_validation(self, id_, schema_name, raise_verrors=True):
        # General method to check certificate health wrt usage in services
        cert = await self.middleware.call('certificate.query', [['id', '=', id_]])
        verrors = ValidationErrors()
        if cert:
            cert = cert[0]
            if cert['name'].startswith(TNC_CERT_PREFIX):
                # We have added an explicit check here to account for users who already
                # were using TNC and had it configured for UI already as nginx would fail to
                # configure SSL otherwise for them if we fail it here
                ui_cert_id = (await self.middleware.call('system.general.config'))['ui_certificate']
                if not ui_cert_id or ui_cert_id != id_:
                    verrors.add(
                        schema_name,
                        f'Certificate "{cert["name"]}" is reserved for TrueNAS Connect service '
                        'and cannot be used by other services'
                    )

            if cert['cert_type'] != 'CERTIFICATE' or cert['cert_type_CSR'] or cert['cert_type_CA']:
                verrors.add(
                    schema_name,
                    'Selected certificate must be a valid certificate and not a CSR or CA'
                )
            else:
                await self.cert_checks(cert, verrors, schema_name)
        else:
            verrors.add(
                schema_name,
                f'No Certificate found with the provided id: {id_}'
            )

        if raise_verrors:
            verrors.check()
        else:
            return verrors

    @private
    async def cert_checks(self, cert, verrors, schema_name):
        valid_key_size = {'EC': 28, 'RSA': 2048}
        if not cert.get('fingerprint'):
            verrors.add(
                schema_name,
                f'{cert["name"]} certificate is malformed'
            )

        if not cert['privatekey']:
            verrors.add(
                schema_name,
                'Selected certificate does not have a private key'
            )
        elif not cert['key_length']:
            verrors.add(
                schema_name,
                "Failed to parse certificate's private key"
            )
        elif cert['key_length'] < valid_key_size[cert['key_type']]:
            verrors.add(
                schema_name,
                f"{cert['name']}'s private key size is less than {valid_key_size[cert['key_type']]} bits"
            )

        if cert['until'] and datetime.datetime.strptime(
            cert['until'], '%a %b  %d %H:%M:%S %Y'
        ) < datetime.datetime.now():
            verrors.add(
                schema_name,
                f'{cert["name"]!r} has expired (it was valid until {cert["until"]!r})'
            )

        if cert['digest_algorithm'] in ['MD5', 'SHA1']:
            verrors.add(
                schema_name,
                'Please use a certificate whose digest algorithm has at least 112 security bits'
            )

    @private
    async def delete_domains_authenticator(self, auth_id):
        # Delete provided auth_id from all ACME based certs domains_authenticators
        for cert in await self.query([['acme', '!=', None]]):
            if auth_id in cert['domains_authenticators'].values():
                await self.middleware.call(
                    'datastore.update',
                    self._config.datastore,
                    cert['id'],
                    {
                        'domains_authenticators': {
                            k: v for k, v in cert['domains_authenticators'].items()
                            if v != auth_id
                        }
                    },
                    {'prefix': self._config.datastore_prefix}
                )
