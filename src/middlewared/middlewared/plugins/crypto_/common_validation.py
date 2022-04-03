import re

from middlewared.async_validators import validate_country

from .utils import RE_CERTIFICATE


async def validate_cert_name(middleware, cert_name, datastore, verrors, name):
    certs = await middleware.call(
        'datastore.query',
        datastore,
        [('cert_name', '=', cert_name)]
    )
    if certs:
        verrors.add(
            name,
            'A certificate with this name already exists'
        )

    if cert_name in ("external", "self-signed", "external - signature pending"):
        verrors.add(
            name,
            f'{cert_name} is a reserved internal keyword for Certificate Management'
        )
    reg = re.search(r'^[a-z0-9_\-]+$', cert_name or '', re.I)
    if not reg:
        verrors.add(
            name,
            'Use alphanumeric characters, "_" and "-".'
        )


async def _validate_common_attributes(middleware, data, verrors, schema_name):

    country = data.get('country')
    if country:
        await validate_country(middleware, country, verrors, f'{schema_name}.country')

    certificate = data.get('certificate')
    if certificate:
        matches = RE_CERTIFICATE.findall(certificate)

        if not matches or not await middleware.call('cryptokey.load_certificate', certificate):
            verrors.add(
                f'{schema_name}.certificate',
                'Not a valid certificate'
            )

    private_key = data.get('privatekey')
    passphrase = data.get('passphrase')
    if private_key:
        await middleware.call('cryptokey.validate_private_key', private_key, verrors, schema_name, passphrase)

    signedby = data.get('signedby')
    if signedby:
        valid_signing_ca = await middleware.call(
            'certificateauthority.query',
            [
                ('certificate', '!=', None),
                ('privatekey', '!=', None),
                ('certificate', '!=', ''),
                ('privatekey', '!=', ''),
                ('id', '=', signedby)
            ],
        )

        if not valid_signing_ca:
            verrors.add(
                f'{schema_name}.signedby',
                'Please provide a valid signing authority'
            )

    csr = data.get('CSR')
    if csr:
        if not await middleware.call('cryptokey.load_certificate_request', csr):
            verrors.add(
                f'{schema_name}.CSR',
                'Please provide a valid CSR'
            )

    csr_id = data.get('csr_id')
    if csr_id and not await middleware.call('certificate.query', [['id', '=', csr_id], ['CSR', '!=', None]]):
        verrors.add(
            f'{schema_name}.csr_id',
            'Please provide a valid csr_id which has a valid CSR filed'
        )

    await middleware.call(
        'cryptokey.validate_certificate_with_key', certificate, private_key, schema_name, verrors, passphrase
    )

    key_type = data.get('key_type')
    if key_type:
        if key_type != 'EC':
            if not data.get('key_length'):
                verrors.add(
                    f'{schema_name}.key_length',
                    'RSA-based keys require an entry in this field.'
                )
            if not data.get('digest_algorithm'):
                verrors.add(
                    f'{schema_name}.digest_algorithm',
                    'This field is required.'
                )

    if not verrors and data.get('cert_extensions'):
        verrors.extend(
            (await middleware.call('cryptokey.validate_extensions', data['cert_extensions'], schema_name))
        )
