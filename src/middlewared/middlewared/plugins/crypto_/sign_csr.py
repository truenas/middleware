from middlewared.schema import accepts, Dict, Int, Ref, returns, Str
from middlewared.service import private, Service, ValidationErrors

from .utils import CERT_TYPE_INTERNAL


class CertificateAuthorityService(Service):

    class Config:
        cli_namespace = 'system.certificate.authority'

    @accepts(
        Dict(
            'ca_sign_csr',
            Int('ca_id', required=True),
            Int('csr_cert_id', required=True),
            Str('name', required=True),
            Ref('cert_extensions'),
            register=True
        )
    )
    @returns(Ref('certificate_entry'))
    async def ca_sign_csr(self, data):
        """
        Sign CSR by Certificate Authority of `ca_id`

        Sign CSR's and generate a certificate from it. `ca_id` provides which CA is to be used for signing
        a CSR of `csr_cert_id` which exists in the system

        `cert_extensions` can be specified if specific extensions are to be set in the newly signed certificate.

        .. examples(websocket)::

          Sign CSR of `csr_cert_id` by Certificate Authority of `ca_id`

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "certificateauthority.ca_sign_csr",
                "params": [{
                    "ca_id": 1,
                    "csr_cert_id": 1,
                    "name": "signed_cert"
                }]
            }
        """
        return await self.ca_sign_csr_impl(data)

    @accepts(
        Ref('ca_sign_csr'),
        Str('schema_name', default='certificate_authority_update')
    )
    @private
    async def ca_sign_csr_impl(self, data, schema_name):
        verrors = ValidationErrors()

        ca_data = await self.middleware.call('certificateauthority.query', [('id', '=', data['ca_id'])])
        csr_cert_data = await self.middleware.call('certificate.query', [('id', '=', data['csr_cert_id'])])

        if not ca_data:
            verrors.add(
                f'{schema_name}.ca_id',
                f'No Certificate Authority found for id {data["ca_id"]}'
            )
        else:
            ca_data = ca_data[0]
            if not ca_data.get('privatekey'):
                verrors.add(
                    f'{schema_name}.ca_id',
                    'Please use a CA which has a private key assigned'
                )

        if not csr_cert_data:
            verrors.add(
                f'{schema_name}.csr_cert_id',
                f'No Certificate found for id {data["csr_cert_id"]}'
            )
        else:
            csr_cert_data = csr_cert_data[0]
            if not csr_cert_data.get('CSR'):
                verrors.add(
                    f'{schema_name}.csr_cert_id',
                    'No CSR has been filed by this certificate'
                )
            else:
                if not await self.middleware.call('cryptokey.load_certificate_request', csr_cert_data['CSR']):
                    verrors.add(
                        f'{schema_name}.csr_cert_id',
                        'CSR not valid'
                    )
                if not csr_cert_data['privatekey']:
                    verrors.add(
                        f'{schema_name}.csr_cert_id',
                        'Private key not found for specified CSR.'
                    )

        if await self.middleware.call('certificate.query', [['name', '=', data['name']]]):
            verrors.add(f'{schema_name}.name', 'A certificate with this name already exists')

        verrors.check()

        serial = await self.middleware.call('certificateauthority.get_serial_for_certificate', ca_data['id'])

        new_cert = await self.middleware.call(
            'cryptokey.sign_csr_with_ca',
            {
                'ca_certificate': ca_data['certificate'],
                'ca_privatekey': ca_data['privatekey'],
                'csr': csr_cert_data['CSR'],
                'csr_privatekey': csr_cert_data['privatekey'],
                'serial': serial,
                'digest_algorithm': ca_data['digest_algorithm'],
                'cert_extensions': data['cert_extensions']
            }
        )

        new_csr = {
            'type': CERT_TYPE_INTERNAL,
            'name': data['name'],
            'certificate': new_cert,
            'privatekey': csr_cert_data['privatekey'],
            'signedby': ca_data['id']
        }

        new_csr_id = await self.middleware.call(
            'datastore.insert',
            'system.certificate',
            new_csr,
            {'prefix': 'cert_'}
        )

        await self.middleware.call('service.start', 'ssl')

        return await self.middleware.call(
            'certificate.query',
            [['id', '=', new_csr_id]],
            {'get': True}
        )
