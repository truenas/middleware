from middlewared.service import ServiceChangeMixin


class CertificateAttachmentDelegate:

    NAMESPACE = NotImplementedError

    def __init__(self, middleware):
        self.middleware = middleware

    async def state(self, cert_id):
        raise NotImplementedError

    async def redeploy(self, cert_id):
        raise NotImplementedError


class CertificateServiceAttachmentDelegate(CertificateAttachmentDelegate, ServiceChangeMixin):

    CERT_FIELD = 'certificate'
    SERVICE = NotImplementedError
    SERVICE_VERB = 'reload'

    async def get_namespace(self):
        return self.SERVICE if self.NAMESPACE is NotImplementedError else self.NAMESPACE

    async def state(self, cert_id):
        config = await self.middleware.call(f'{await self.get_namespace()}.config')
        if isinstance(config[self.CERT_FIELD], dict):
            return config[self.CERT_FIELD]['id'] == cert_id
        else:
            return config[self.CERT_FIELD] == cert_id

    async def redeploy(self, cert_id):
        if await self.middleware.call('service.started', self.SERVICE):
            await self.middleware.call(f'service.{self.SERVICE_VERB}', self.SERVICE)


class CertificateCRUDServiceAttachmentDelegate(CertificateAttachmentDelegate, ServiceChangeMixin):

    CERT_FILTER_KEY = 'certificate'

    async def get_filters(self, cert_id):
        return [[self.CERT_FILTER_KEY, '=', cert_id]]

    async def attachments(self, cert_id):
        return await self.middleware.call(f'{self.NAMESPACE}.query', await self.get_filters(cert_id))

    async def state(self, cert_id):
        return bool(await self.attachments(cert_id))
