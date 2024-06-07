from middlewared.service import CallError, private, Service


class CertificateService(Service):

    @private
    async def check_cert_deps(self, cert_id):
        if deps := await self.middleware.call('certificate.get_attachments', cert_id):
            deps_str = ''
            for i, svc in enumerate(deps):
                deps_str += f'{i+1}) {svc}\n'
            raise CallError(f'Certificate is being used by following service(s):\n{deps_str}')
