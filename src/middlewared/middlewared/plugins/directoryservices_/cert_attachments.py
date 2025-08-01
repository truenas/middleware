from middlewared.utils.directoryservices.constants import DSType
from middlewared.utils.directoryservices.credential import DSCredType
from middlewared.utils.directoryservices.ipa_constants import IpaConfigName
from middlewared.common.attachment.certificate import CertificateServiceAttachmentDelegate


class DSCertificateAttachmentDelegate(CertificateServiceAttachmentDelegate):

    HUMAN_NAME = 'Directory Services'

    async def state(self, cert_id):
        ds_config = await self.middleware.call('datastore.config', 'directoryservices')
        if not ds_config['enable']:
            return False

        # currently certs only used by mtls auth for LDAP
        match ds_config['service_type']:
            case DSType.IPA.value:
                # IPA bind may rely on the presence of the IPA server's cacert
                cert_name = (await self.middleware.call('certificate.get_instance', cert_id))['name']
                return cert_name == IpaConfigName.IPA_CACERT
            case DSType.LDAP.value:
                # Check is below
                pass
            case _:
                # AD does not currently have any cert dependencies
                return False

        if ds_config['cred_type'] != DSCredType.LDAP_MTLS:
            return False

        return cert_id == ds_config['cred_ldap_mtls_cert_id']

    async def redeploy(self, cert_id):
        await self.middleware.call('directoryservices.health.recover')


async def setup(middleware):
    await middleware.call('certificate.register_attachment_delegate', DSCertificateAttachmentDelegate(middleware))
