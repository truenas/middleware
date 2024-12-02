from middlewared.service import CallError, job, Service

from .acme_utils import normalize_acme_config
from .cert_utils import generate_csr, get_hostnames_from_hostname_config
from .mixin import TNCAPIMixin
from .urls import ACME_CONFIG_URL
from .utils import get_account_id_and_system_id


class TNCACMEService(Service, TNCAPIMixin):

    class Config:
        private = True
        namespace = 'tn_connect.acme'

    async def call(self, url, mode, payload=None):
        config = await self.middleware.call('tn_connect.config')
        return await self._call(url, mode, payload=payload, headers=await self.auth_headers(config))

    async def config(self):
        config = await self.middleware.call('tn_connect.config')
        creds = get_account_id_and_system_id(config)
        if not config['enabled'] or creds is None:
            return {
                'error': 'TrueNAS Connect is not enabled or not configured properly',
                'tnc_configured': False,
                'acme_details': {},
            }

        resp = await self.call(ACME_CONFIG_URL.format(account_id=creds['account_id']), 'get')
        resp['acme_details'] = resp.pop('response')
        if resp['error'] is None:
            resp = normalize_acme_config(resp)

        return resp | {
            'tnc_configured': True,
        }

    @job()
    async def create_cert(self, job):
        hostname_config = await self.middleware.call('tn_connect.hostname.config')
        if hostname_config['error']:
            raise CallError(f'Failed to fetch TNC hostname configuration: {hostname_config["error"]}')

        acme_config = await self.middleware.call('tn_connect.acme.config')
        if acme_config['error']:
            raise CallError(f'Failed to fetch TNC ACME configuration: {acme_config["error"]}')

        hostnames = get_hostnames_from_hostname_config(hostname_config)
        csr, private_key = generate_csr(hostnames)
        dns_mapping = {f'DNS:{hostname}': None for hostname in hostnames}
        final_order = await self.middleware.call(
            'acme.issue_certificate_impl', type('dummy_job', (object,), {'set_progress': lambda *args: None})(),
            10, acme_config['acme_details'], csr, dns_mapping,
        )

        return {
            'cert': final_order.fullchain_pem,
            'acme_uri': final_order.uri,
            'private_key': private_key,
        }
