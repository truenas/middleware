from __future__ import annotations

import datetime

from middlewared.api.current import CertificateEntry
from middlewared.plugins.truenas_connect.utils import TNC_CERT_PREFIX
from middlewared.service import ServiceContext, ValidationErrors


def _cert_checks(cert: CertificateEntry, verrors: ValidationErrors, schema_name: str) -> None:
    valid_key_size = {'EC': 28, 'RSA': 2048}
    if not cert.fingerprint:
        verrors.add(
            schema_name,
            f'{cert.name} certificate is malformed',
        )

    # `cert.privatekey` is a Secret wrapper; unwrap to inspect the underlying value.
    pk_secret = cert.privatekey
    pk_inner = pk_secret.get_secret_value() if pk_secret is not None else None
    if not pk_inner:
        verrors.add(
            schema_name,
            'Selected certificate does not have a private key',
        )
    elif not cert.key_length:
        verrors.add(
            schema_name,
            "Failed to parse certificate's private key",
        )
    elif cert.key_type and cert.key_length < valid_key_size[cert.key_type]:
        verrors.add(
            schema_name,
            f"{cert.name}'s private key size is less than {valid_key_size[cert.key_type]} bits",
        )

    if cert.until and datetime.datetime.strptime(
        cert.until, '%a %b  %d %H:%M:%S %Y'
    ) < datetime.datetime.now():
        verrors.add(
            schema_name,
            f'{cert.name!r} has expired (it was valid until {cert.until!r})',
        )

    if cert.digest_algorithm in ['MD5', 'SHA1']:
        verrors.add(
            schema_name,
            'Please use a certificate whose digest algorithm has at least 112 security bits',
        )


async def cert_services_validation(
    context: ServiceContext, id_: int, schema_name: str, raise_verrors: bool = True,
) -> ValidationErrors | None:
    # General method to check certificate health wrt usage in services
    certs = await context.call2(context.s.certificate.query, [['id', '=', id_]])
    verrors = ValidationErrors()
    if certs:
        cert = certs[0]
        if cert.name.startswith(TNC_CERT_PREFIX):
            # We have added an explicit check here to account for users who already
            # were using TNC and had it configured for UI already as nginx would fail to
            # configure SSL otherwise for them if we fail it here
            ui_cert_id = (await context.middleware.call('system.general.config'))['ui_certificate']
            if not ui_cert_id or ui_cert_id != id_:
                verrors.add(
                    schema_name,
                    f'Certificate "{cert.name}" is reserved for TrueNAS Connect service '
                    'and cannot be used by other services',
                )

        if cert.cert_type != 'CERTIFICATE' or cert.cert_type_CSR or cert.cert_type_CA:
            verrors.add(
                schema_name,
                'Selected certificate must be a valid certificate and not a CSR or CA',
            )
        else:
            _cert_checks(cert, verrors, schema_name)
    else:
        verrors.add(
            schema_name,
            f'No Certificate found with the provided id: {id_}',
        )

    if raise_verrors:
        verrors.check()
        return None
    return verrors
