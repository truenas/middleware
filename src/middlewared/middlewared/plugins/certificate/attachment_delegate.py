from middlewared.common.attachment.certificate import CertificateAttachmentDelegate
from middlewared.service import CallError

DELEGATES: list[CertificateAttachmentDelegate] = []


def register_attachment_delegate(delegate: CertificateAttachmentDelegate) -> None:
    DELEGATES.append(delegate)


async def in_use_attachments(cert_id: int) -> list[CertificateAttachmentDelegate]:
    return [delegate for delegate in DELEGATES if await delegate.state(cert_id)]


async def get_attachments(cert_id: int) -> list[str | None]:
    return list(filter(bool, [await delegate.consuming_cert_human_output(cert_id) for delegate in DELEGATES]))


async def redeploy_cert_attachments(cert_id: int) -> None:
    for delegate in await in_use_attachments(cert_id):
        await delegate.redeploy(cert_id)


async def check_cert_deps(cert_id: int) -> None:
    if deps := await get_attachments(cert_id):
        deps_str = ''
        for i, svc in enumerate(deps):
            deps_str += f'{i+1}) {svc}\n'

        raise CallError(f'Certificate is being used by following service(s):\n{deps_str}')
