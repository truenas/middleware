from middlewared.schema import accepts, Dict, Ref, returns, Str
from middlewared.service import private, Service

from .utils import EC_CURVES, EKU_OIDS


class CertificateService(Service):

    class Config:
        cli_namespace = 'system.certificate'

    @private
    async def get_domain_names(self, cert_id):
        data = await self.middleware.call('certificate.get_instance', int(cert_id))
        names = [data['common']] if data['common'] else []
        names.extend(data['san'])
        return names

    @accepts()
    @returns(Ref('country_choices'))
    async def country_choices(self):
        """
        Returns country choices for creating a certificate/csr.
        """
        return await self.middleware.call('system.general.country_choices')

    @accepts()
    @returns(Dict('acme_server_choices', additional_attrs=True))
    async def acme_server_choices(self):
        """
        Dictionary of popular ACME Servers with their directory URI endpoints which we display automatically
        in UI
        """
        return {
            'https://acme-staging-v02.api.letsencrypt.org/directory': 'Let\'s Encrypt Staging Directory',
            'https://acme-v02.api.letsencrypt.org/directory': 'Let\'s Encrypt Production Directory'
        }

    @accepts()
    @returns(Dict(
        'ec_curve_choices',
        *[Str(k, enum=[k]) for k in EC_CURVES]
    ))
    async def ec_curve_choices(self):
        """
        Dictionary of supported EC curves.
        """
        return {k: k for k in EC_CURVES}

    @accepts()
    @returns(Dict(
        'private_key_type_choices',
        *[Str(k, enum=[k]) for k in ('RSA', 'EC')]
    ))
    async def key_type_choices(self):
        """
        Dictionary of supported key types for certificates.
        """
        return {k: k for k in ['RSA', 'EC']}

    @accepts()
    @returns(Dict(
        'extended_key_usage_choices',
        *[Str(k, enum=[k]) for k in EKU_OIDS]
    ))
    async def extended_key_usage_choices(self):
        """
        Dictionary of choices for `ExtendedKeyUsage` extension which can be passed over to `usages` attribute.
        """
        return {k: k for k in EKU_OIDS}
