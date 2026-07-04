from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api.base import EmptyDict
from middlewared.plugins.truenas_connect.utils import TNC_CERT_PREFIX

if TYPE_CHECKING:
    from middlewared.service import ServiceContext


async def syslog_certificate_choices(context: ServiceContext) -> dict[int, str]:
    return {
        i.id: i.name
        for i in await context.call2(
            context.s.certificate.query,
            [
                ['cert_type_CSR', '=', False],
                ['cert_type_CA', '=', False],
                ['name', '!^', TNC_CERT_PREFIX],
            ],
        )
    }


def syslog_certificate_authority_choices() -> EmptyDict:
    return EmptyDict()
