from middlewared.api import api_method
from middlewared.api.current import (
    SystemAdvancedSyslogCertificateChoicesArgs, SystemAdvancedSyslogCertificateChoicesResult,
    SystemAdvancedSyslogCertificateAuthorityChoicesArgs, SystemAdvancedSyslogCertificateAuthorityChoicesResult
)
from middlewared.service import Service


class SystemAdvancedService(Service):

    class Config:
        namespace = 'system.advanced'
        cli_namespace = 'system.advanced'

    @api_method(
        SystemAdvancedSyslogCertificateChoicesArgs,
        SystemAdvancedSyslogCertificateChoicesResult,
        roles=['READONLY_ADMIN']
    )
    async def syslog_certificate_choices(self):
        """
        Return choices of certificates which can be used for `syslogservers.N.tls_certificate`.
        """
        return {
            i['id']: i['name']
            for i in await self.middleware.call(
                'certificate.query', [
                    ['cert_type_CSR', '=', False],
                    ['cert_type_CA', '=', False]
                ]
            )
        }

    @api_method(
        SystemAdvancedSyslogCertificateAuthorityChoicesArgs,
        SystemAdvancedSyslogCertificateAuthorityChoicesResult,
        authorization_required=False
    )
    async def syslog_certificate_authority_choices(self):
        """
        Return choices of certificate authorities which can be used for `syslog_tls_certificate_authority`.
        ---- NO LONGER USED: TO BE REMOVED AFTER UI UPDATE ----
        """
        # return {
        #     i['id']: i['name']
        #     for i in await self.middleware.call('certificateauthority.query', [['revoked', '=', False]])
        # }
        return {}
