from __future__ import annotations

from middlewared.service import ServiceContext


async def delete_domains_authenticator(context: ServiceContext, auth_id: int) -> None:
    # Delete provided auth_id from all ACME based certs domains_authenticators
    certs = await context.call2(context.s.certificate.query, [['acme', '!=', None]])
    for cert in certs:
        if cert.domains_authenticators and auth_id in cert.domains_authenticators.values():
            await context.middleware.call(
                'datastore.update',
                'system.certificate',
                cert.id,
                {
                    'domains_authenticators': {
                        k: v for k, v in cert.domains_authenticators.items()
                        if v != auth_id
                    },
                },
                {'prefix': 'cert_'},
            )
