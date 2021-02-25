from middlewared.service import Service


class CertificateService(Service):

    class Config:
        cli_namespace = 'system.certificate'

    def __init__(self, *args, **kwargs):
        super(CertificateService, self).__init__(*args, **kwargs)
        self.delegates = []

    async def register_attachment_delegate(self, delegate):
        self.delegates.append(delegate)

    async def in_use_attachments(self, cert_id):
        return [delegate for delegate in self.delegates if delegate.state(cert_id)]

    async def redeploy_cert_attachments(self, cert_id):
        for delegate in await self.in_use_attachments(cert_id):
            await delegate.redeploy(cert_id)
