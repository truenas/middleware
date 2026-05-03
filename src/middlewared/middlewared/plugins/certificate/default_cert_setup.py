from __future__ import annotations

from truenas_crypto_utils.generate_self_signed import generate_self_signed_certificate

from middlewared.service import ServiceContext

from .utils import CERT_TYPE_EXISTING, DEFAULT_CERT_NAME


async def setup_self_signed_cert_for_ui(context: ServiceContext, cert_name: str = DEFAULT_CERT_NAME) -> None:
    cert_id: int | None = None
    index = 1
    while not cert_id:
        certs = await context.call2(context.s.certificate.query, [["name", "=", cert_name]])
        if certs:
            cert = certs[0]
            if await context.call2(
                context.s.certificate.cert_services_validation,
                cert.id,
                "certificate",
                False,
            ):
                cert_name = f"{cert_name}_{index}"
                index += 1
            else:
                cert_id = cert.id
                context.logger.debug("Using %r certificate for System UI", cert_name)
        else:
            cert_id = await setup_self_signed_cert_for_ui_impl(context, cert_name)
            context.logger.debug("Default certificate for System created")

    await context.middleware.call(
        "datastore.update",
        "system.settings",
        (await context.middleware.call("system.general.config"))["id"],
        {"stg_guicertificate": cert_id},
    )

    await (await context.middleware.call("service.control", "START", "ssl")).wait(raise_error=True)


async def setup_self_signed_cert_for_ui_impl(context: ServiceContext, cert_name: str) -> int:
    cert, key = await context.to_thread(generate_self_signed_certificate)

    cert_dict = {
        "certificate": cert,
        "privatekey": key,
        "name": cert_name,
        "type": CERT_TYPE_EXISTING,
    }

    # We use datastore.insert to directly insert in db as this is a self-signed cert
    # and we don't allow that via regular api
    new_id: int = await context.middleware.call(
        "datastore.insert", "system.certificate", cert_dict, {"prefix": "cert_"}
    )
    return new_id
