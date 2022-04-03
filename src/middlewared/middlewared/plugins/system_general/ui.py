import asyncio
import psutil

from middlewared.schema import accepts, Dict, Int, returns, Str
from middlewared.service import CallError, rest_api_metadata, private, Service
from middlewared.validators import Range

from .utils import HTTPS_PROTOCOLS


class SystemGeneralService(Service):

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
        kwargs = {'static': True} if (await self.middleware.call('failover.licensed')) else {}

        # http is always used
        http_proto = 'http://'
        http_port = config['ui_port']
        http_default_port = config['ui_port'] == 80

        # populate https data if necessary
        https_proto = https_port = https_default_port = None
        if config['ui_certificate']:
            https_proto = 'https://'
            https_port = config['ui_httpsport']
            https_default_port = config['ui_httpsport'] == 443

        nginx_ips = {}
        for i in psutil.net_connections():
            if i.laddr.port in (http_port, https_port):
                nginx_ips.update({i.laddr.ip: i.family.name})

        all_ip4 = '0.0.0.0' in nginx_ips
        all_ip6 = '::' in nginx_ips

        urls = []
        if all_ip4 or all_ip6:
            for i in await self.middleware.call('interface.ip_in_use', kwargs):

                # nginx could be listening to all IPv4 IPs but not all IPv6 IPs
                # or vice versa
                if i['type'] == 'INET' and all_ip4:
                    http_url = f'{http_proto}{i["address"]}'
                    if not http_default_port:
                        http_url += f':{http_port}'
                    urls.append(http_url)
                    if https_proto is not None:
                        https_url = f'{https_proto}{i["address"]}'
                        if not https_default_port:
                            https_url += f':{https_port}'
                        urls.append(https_url)

                elif i['type'] == 'INET6' and all_ip6:
                    http_url = f'{http_proto}[{i["address"]}]'
                    if not http_default_port:
                        http_url += f':{http_port}'
                    urls.append(http_url)
                    if https_proto is not None:
                        https_url = f'{https_proto}[{i["address"]}]'
                        if not https_default_port:
                            https_url += f':{https_port}'
                        urls.append(https_url)

        for k, v in nginx_ips.items():
            # 0.0.0.0 and/or :: is handled above
            if k not in ('0.0.0.0', '::'):
                if v == 'AF_INET':
                    http_url = f'{http_proto}{k}'
                    if not http_default_port:
                        http_url += f':{http_port}'
                    urls.append(http_url)
                    if https_proto is not None:
                        https_url = f'{https_proto}{k}'
                        if not https_default_port:
                            https_url += f':{https_port}'
                        urls.append(https_url)

                elif v == 'AF_INET6':
                    http_url = f'{http_proto}[{k}]'
                    if not http_default_port:
                        http_url += f':{http_port}'
                    urls.append(http_url)
                    if https_proto is not None:
                        https_url = f'{https_proto}[{k}]'
                        if not https_default_port:
                            https_url += f':{https_port}'
                        urls.append(https_url)

        return sorted(set(urls))
