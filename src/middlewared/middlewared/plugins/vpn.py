import subprocess

from middlewared.service import SystemServiceService, private
from middlewared.schema import accepts, Bool, Dict, Int, IPAddr, List, Str, ValidationErrors
from middlewared.validators import Port


class OpenVPN:
    CIPHERS = {}
    DIGESTS = {}

    @staticmethod
    def ciphers():
        if not OpenVPN.CIPHERS:
            proc = subprocess.Popen(
                ['openvpn', '--show-ciphers'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, stderr = proc.communicate()
            if not proc.returncode:
                OpenVPN.CIPHERS = {
                    v.split(' ')[0].strip(): v.split(' ', 1)[1].strip()
                    for v in
                    filter(
                        lambda v: v and v.split(' ')[0].strip() == v.split(' ')[0].strip().upper(),
                        stdout.decode('utf8').split('\n')
                    )
                }

        return OpenVPN.CIPHERS

    @staticmethod
    def digests():
        if not OpenVPN.DIGESTS:
            proc = subprocess.Popen(
                ['openvpn', '--show-digests'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, stderr = proc.communicate()
            if not proc.returncode:
                OpenVPN.DIGESTS = {
                    v.split(' ')[0].strip(): v.split(' ', 1)[1].strip()
                    for v in
                    filter(
                        lambda v: v and v.endswith('bit digest size'),
                        stdout.decode('utf8').split('\n')
                    )
                }

        return OpenVPN.DIGESTS

    @staticmethod
    async def common_validation(self, middleware, data, schema, mode):
        verrors = ValidationErrors()

        if data['cipher'] and data['cipher'] not in OpenVPN.ciphers():
            verrors.add(
                f'{schema}.cipher',
                'Please specify a valid cipher.'
            )

        if data['authentication_algorithm'] and data['authentication_algorithm'] not in OpenVPN.digests():
            verrors.add(
                f'{schema}.authentication_algorithm',
                'Please specify a valid authentication_algorithm.'
            )

        # TODO: Let's add checks for cert extensions as well please
        if not await middleware.call(
            'certificateauthority.query', [
                ['id', '=', data['root_ca']],
                ['revoked', '=', False]
            ]
        ):
            verrors.add(
                f'{schema}.root_ca',
                'Please provide a valid id for Root Certificate Authority which exists on the system '
                'and hasn\'t been revoked.'
            )

        if not await middleware.call(
            'certificate.query', [
                ['id', '=', data[f'{mode}_certificate']],
                ['revoked', '=', False]
            ]
        ):
            verrors.add(
                f'{schema}.certificate',
                f'Please provide a valid id for {mode.capitalize()} certificate which exists on '
                'the system and hasn\'t been revoked.'
            )

        return verrors


class OpenVPNServerService(SystemServiceService):

    class Config:
        namespace = 'openvpn.server'
        service = 'openvpn_server'
        service_model = 'openvpnserver'
        service_verb = 'restart'

    @accepts(
        Dict(
            'openvpn_server_update',
            Bool('tls_crypt_auth_enabled'),
            Int('netmask'),
            Int('server_certificate', null=True),
            Int('port', validators=[Port()]),
            Int('root_ca', null=True),
            IPAddr('server', network=True),
            Str('additional_parameters'),
            Str('authentication_algorithm', null=True),
            Str('cipher', null=True),
            Str('compression', null=True, enum=['LZO', 'LZ4']),
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
        namespace = 'openvpn.client'
        service = 'openvpn_client'
        service_model = 'openvpnclient'
        service_verb = 'restart'

    @accepts(
        Dict(
            'openvpn_client_update',
            Bool('nobind'),
            Bool('tls_crypt_auth_enabled'),
            Int('client_certificate', null=True),
            Int('root_ca', null=True),
            Int('port', validators=[Port()]),
            Str('additional_parameters'),
            Str('authentication_algorithm', null=True),
            Str('cipher', null=True),
            Str('compression', null=True, enum=['LZO', 'LZ4']),
            Str('device_type', enum=['TUN', 'TAP']),
            Str('protocol', enum=['UDP', 'TCP']),
            Str('remote'),
            Str('tls_crypt_auth', null=True),
            update=True
        )
    )
    async def do_update(self, data):
        return await self.config()
