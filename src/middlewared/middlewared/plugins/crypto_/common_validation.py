import re


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
