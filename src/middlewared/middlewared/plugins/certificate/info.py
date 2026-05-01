from __future__ import annotations

from middlewared.api.current import EKU_OID, ECCurves
from middlewared.service import ServiceContext
from middlewared.utils.country_codes import get_country_codes


def acme_server_choices() -> dict[str, str]:
    return {
        "https://acme-staging-v02.api.letsencrypt.org/directory": "Let's Encrypt Staging Directory",
        "https://acme-v02.api.letsencrypt.org/directory": "Let's Encrypt Production Directory",
    }


def country_choices() -> dict[str, str]:
    return dict(get_country_codes())


def ec_curve_choices() -> dict[str, str]:
    return {k.value: k.value for k in ECCurves}


def extended_key_usage_choices() -> dict[str, str]:
    return {k.value: k.value for k in EKU_OID}


async def get_domain_names(context: ServiceContext, cert_id: int) -> list[str]:
    data = await context.call2(context.s.certificate.get_instance, int(cert_id))
    names: list[str] = []
    if data.common:
        names.append(data.common)
    if data.san:
        names.extend(data.san)
    return names
