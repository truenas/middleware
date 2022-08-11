import asyncio

from middlewared.schema import accepts, Dict, Int, returns, Str
from middlewared.service import CallError, rest_api_metadata, private, Service
from middlewared.validators import Range

from .utils import HTTPS_PROTOCOLS


class SystemGeneralService(Service):

    ui_allowlist = []

    class Config:
        namespace = 'system.general'
        cli_namespace = 'system.general'

    @accepts()
    @returns(Dict('available_ui_address_choices', additional_attrs=True, title='Available UI IPv4 Address Choices'))
    async def ui_address_choices(self):
        """
        Returns UI ipv4 address choices.
        """
        return {
            d['address']: d['address'] for d in await self.middleware.call(
                'interface.ip_in_use', {'ipv4': True, 'ipv6': False, 'any': True, 'static': True}
            )
        }

    @accepts()
    @returns(Dict('available_ui_v6address_choices', additional_attrs=True, title='Available UI IPv6 Address Choices'))
    async def ui_v6address_choices(self):
        """
        Returns UI ipv6 address choices.
        """
        return {
            d['address']: d['address'] for d in await self.middleware.call(
                'interface.ip_in_use', {'ipv4': False, 'ipv6': True, 'any': True, 'static': True}
            )
        }

    @accepts()
    @returns(Dict(
        'ui_https_protocols',
        *[Str(k, enum=[k]) for k in HTTPS_PROTOCOLS],
        title='UI HTTPS Protocol Choices'
    ))
    def ui_httpsprotocols_choices(self):
        """
        Returns available HTTPS protocols.
        """
        return dict(zip(HTTPS_PROTOCOLS, HTTPS_PROTOCOLS))

    @accepts()
    @returns(Dict('ui_certificate_choices', additional_attrs=True, title='UI Certificate Choices'))
    async def ui_certificate_choices(self):
        """
        Return choices of certificates which can be used for `ui_certificate`.
        """
        return {
            i['id']: i['name']
            for i in await self.middleware.call('certificate.query', [
                ('cert_type_CSR', '=', False)
            ])
        }

    @rest_api_metadata(extra_methods=['GET'])
    @accepts(Int('delay', default=3, validators=[Range(min=0)]))
    async def ui_restart(self, delay):
        """
        Restart HTTP server to use latest UI settings.

        HTTP server will be restarted after `delay` seconds.
        """
        event_loop = asyncio.get_event_loop()
        event_loop.call_later(delay, lambda: asyncio.ensure_future(self.middleware.call('service.restart', 'http')))

    @accepts()
    @returns(Str('local_url'))
    async def local_url(self):
        """
        Returns configured local url in the format of protocol://host:port
        """
        config = await self.middleware.call('system.general.config')

        if config['ui_certificate']:
            protocol = 'https'
            port = config['ui_httpsport']
        else:
            protocol = 'http'
            port = config['ui_port']

        if '0.0.0.0' in config['ui_address'] or '127.0.0.1' in config['ui_address']:
            hosts = ['127.0.0.1']
        else:
            hosts = config['ui_address']

        errors = []
        for host in hosts:
            try:
                reader, writer = await asyncio.wait_for(asyncio.open_connection(
                    host,
                    port=port,
                ), timeout=5)
                writer.close()

                return f'{protocol}://{host}:{port}'

            except Exception as e:
                errors.append(f'{host}: {e}')

        raise CallError('Unable to connect to any of the specified UI addresses:\n' + '\n'.join(errors))

    @private
    async def get_ui_urls(self):

        config = await self.middleware.call('system.general.config')
        kwargs = {'static': True} if await self.middleware.call('failover.licensed') else {}

        # http is always used
        http_proto = 'http://'
        http_port = config['ui_port']

        # populate https data if necessary
        https_proto = https_port = None
        if config['ui_certificate']:
            https_proto = 'https://'
            https_port = config['ui_httpsport']

        all_ip4 = '0.0.0.0' in config['ui_address']
        all_ip6 = '::' in config['ui_v6address']

        urls = set()
        for i in await self.middleware.call('interface.ip_in_use', kwargs):
            http_url = http_proto + i["address"] if i['type'] == 'INET' else f'[{i["address"]}]'
            http_url += f':{http_port}'

            https_url = None
            if https_proto is not None:
                https_url = https_proto + i["address"] if i['type'] == 'INET' else f'[{i["address"]}]'
                https_url += f':{https_port}'

            if all_ip4 or all_ip6:
                urls.add(http_url)
                if https_url:
                    urls.add(https_url)
            elif i['address'] in config['ui_address'] or i['address'] in config['ui_v6address']:
                urls.add(http_url)
                if https_url:
                    urls.add(https_url)

        return sorted(urls)

    @private
    async def get_ui_allowlist(self):
        """
        We store this in a state and not read this configuration variable directly from the database so it is
        synchronized with HTTP service restarts and HTTP configuration commit/rollback works properly.
        Otherwise, changing `ui_allowlist` would immediately block/unblock new connections (we want to block/unblock
        them only after explicit HTTP service restart).
        """
        return self.ui_allowlist

    @private
    async def update_ui_allowlist(self):
        self.ui_allowlist = (await self.middleware.call('system.general.config'))['ui_allowlist']


async def setup(middleware):
    await middleware.call('system.general.update_ui_allowlist')
