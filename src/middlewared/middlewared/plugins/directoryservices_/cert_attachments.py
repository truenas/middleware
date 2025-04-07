from middlewared.utils.directoryservices.constants import DSType
from middlewared.utils.directoryservices.credential import DSCredType
from middlewared.common.attachment.certificate import CertificateServiceAttachmentDelegate


class DSCertificateAttachmentDelegate(CertificateServiceAttachmentDelegate):

    HUMAN_NAME = 'Directory Services'

    async def state(self, cert_id):
        ds_config = await self.middleware.call('datastore.config', 'directoryservices')
        if not ds_config['enable']:
            return False

        # currently certs only used by mtls auth for LDAP
        if ds_config['service_type'] != DSType.LDAP.value:
            return False

        if ds_config['cred_type'] != DSCredType.LDAP_MTLS:
            return False

        return cert_id == ds_config['cred_ldap_mtls_cert_id']

    async def redelpoy(self, cert_id):
        await self.middleware.call('directoryservices.health.recover')


async def setup(middleware):
    await middleware.call('certificate.register_attachment_delegate', DSCertificateAttachmentDelegate(middleware))
