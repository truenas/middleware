from middlewared.schema import accepts, Dict, returns
from middlewared.service import Service


class SystemAdvancedService(Service):

    class Config:
        namespace = 'system.advanced'
        cli_namespace = 'system.advanced'

    @accepts()
    @returns(Dict(
        additional_attrs=True,
        title='Syslog Certificate Choices',
    ))
    async def syslog_certificate_choices(self):
        """
        Return choices of certificates which can be used for `syslog_tls_certificate`.
        """
        return {
            i['id']: i['name']
            for i in await self.middleware.call('certificate.query', [('cert_type_CSR', '=', False)])
        }

    @accepts()
    @returns(Dict(
        additional_attrs=True,
        title='Syslog Certificate Authority Choices',
    ))
    async def syslog_certificate_authority_choices(self):
        """
        Return choices of certificate authorities which can be used for `syslog_tls_certificate_authority`.
        """
        return {
            i['id']: i['name']
            for i in await self.middleware.call('certificateauthority.query', [['revoked', '=', False]])
        }
