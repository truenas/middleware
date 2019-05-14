from middlewared.schema import accepts, Bool, Dict, Int, IPAddr, List, Str
from middlewared.service import SystemServiceService, private


class OpenVPN:
    pass


class OpenVPNServerService(SystemServiceService):

    class Config:
        service = 'openvpn_server'
        service_model = 'openvpnserver'
        service_verb = 'restart'

    @accepts(
        Dict(
            'openvpn_server_update',
            Bool('tls_crypt_auth_enabled'),
            Int('netmask'),
            Int('server_certificate', null=True),
            Int('port'),
            Int('root_ca', null=True),
            IPAddr('server', network=True),
            Str('additional_parameters'),
            Str('authentication_algorithm', enum=[], null=True),
            Str('device_type', enum=['TUN', 'TAP']),
            Str('protocol', enum=['UDP', 'TCP']),
            Str('tls_crypt_auth', null=True),
            Str('topology', null=True, enum=['NET30', 'P2P', 'SUBNET']),
            update=True
        )
    )
    async def do_update(self, data):
        return await self.config()


class OpenVPNClientService(SystemServiceService):

    class Config:
        service = 'openvpn_client'
        service_model = 'openvpnclient'
        service_verb = 'restart'

    @accepts(
        Dict(
            'openvpn_client_update',
            Bool('nobind'),
            Bool('tls_crypt_auth_enabled'),
            Int('client_certificate', null=True),
            Int('port'),
            Int('root_ca', null=True),
            Str('additional_parameters'),
            Str('authentication_algorithm', enum=[], null=True),
            Str('device_type', enum=['TUN', 'TAP']),
            Str('protocol', enum=['UDP', 'TCP']),
            Str('remote'),
            Str('tls_crypt_auth', null=True),
            update=True
        )
    )
    async def do_update(self, data):
        return await self.config()
