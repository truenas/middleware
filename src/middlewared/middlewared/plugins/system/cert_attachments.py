from middlewared.common.attachment.certificate import CertificateServiceAttachmentDelegate


class SystemGeneralCertificateAttachmentDelegate(CertificateServiceAttachmentDelegate):

    CERT_FIELD = 'ui_certificate'
    HUMAN_NAME = 'UI Service'
    NAMESPACE = 'system.general'
    SERVICE = 'http'

    async def redeploy(self, cert_id):
        await super().redeploy(cert_id)
        # The served UI cert just changed (e.g. ACME renewal), so refresh the SCRAM-PLUS
        # server channel binding that pam_truenas reads. etc.generate('pam') re-runs
        # pam_keyring, which republishes the tls-server-end-point value.
        await self.middleware.call('etc.generate', 'pam')


class SystemAdvancedCertificateAttachmentDelegate(CertificateServiceAttachmentDelegate):

    # CERT_FIELD is unused
    HUMAN_NAME = 'Syslog Service'
    NAMESPACE = 'system.advanced'
    SERVICE = 'syslogd'

    async def state(self, cert_id):
        config = await self.middleware.call('system.advanced.config')
        return any(server['tls_certificate'] == cert_id for server in config['syslogservers'])


async def setup(middleware):
    await middleware.call(
        'certificate.register_attachment_delegate', SystemGeneralCertificateAttachmentDelegate(middleware)
    )
    await middleware.call(
        'certificate.register_attachment_delegate', SystemAdvancedCertificateAttachmentDelegate(middleware)
    )
