import subprocess

from middlewared.service import CallError, SystemServiceService, private
from middlewared.schema import accepts, Bool, Dict, Int, IPAddr, Str, ValidationErrors
from middlewared.validators import Port, Range


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
    async def common_validation(middleware, data, schema, mode):
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
        datastore_extend = 'openvpn.server.server_extend'

    @private
    async def server_extend(self, data):
        data['server_certificate'] = None if not data['server_certificate'] else data['server_certificate']['id']
        data['root_ca'] = None if not data['root_ca'] else data['root_ca']['id']
        return data

    @private
    async def config_valid(self):
        config = await self.config()
        if not config['root_ca']:
            raise CallError('Please configure root_ca first.')
        else:
            if not await self.middleware.call(
                'certificateauthority.query', [
                    ['id', '=', config['root_ca']],
                    ['revoked', '=', False]
                ]
            ):
                raise CallError('Root CA has been revoked. Please select another Root CA.')

        if not config['server_certificate']:
            raise CallError('Please configure server certificate first.')
        else:
            if not await self.middleware.call(
                'certificate.query', [
                    ['id', '=', config['server_certificate']],
                    ['revoked', '=', False]
                ]
            ):
                raise CallError('Server certificate has been revoked. Please select another Server certificate.')

        if not await self.validate_nobind(config):
            raise CallError(
                'Please enable "nobind" on OpenVPN Client to concurrently run OpenVPN Server/Client '
                'on the same local port without any issues.'
            )

    @accepts()
    async def authentication_algorithm_choices(self):
        return OpenVPN.digests()

    @accepts()
    async def cipher_choices(self):
        return OpenVPN.ciphers()

    @private
    async def validate(self, data, schema_name):
        verrors = await OpenVPN.common_validation(
            self.middleware, data, schema_name, 'server'
        )

        if not await self.validate_nobind(data):
            verrors.add(
                f'{schema_name}.nobind',
                'Please enable "nobind" on OpenVPN Client to concurrently run OpenVPN Server/Client '
                'on the same local port without any issues.'
            )

        verrors.check()

    @private
    async def validate_nobind(self, config):
        client_config = await self.middleware.call('openvpn.client.config')
        if (
            await self.middleware.call(
                'service.started',
                'openvpn_client'
            ) and config['port'] == client_config['port'] and not client_config['nobind']
        ):
            return False
        else:
            return True

    @accepts(
        Dict(
            'openvpn_server_update',
            Bool('tls_crypt_auth_enabled'),
            Int('netmask', validators=[Range(min=0, max=32)]),
            Int('server_certificate'),
            Int('port', validators=[Port()]),
            Int('root_ca'),
            IPAddr('server'),
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
        old_config = await self.config()
        config = old_config.copy()

        config.update(data)

        await self.validate(config, 'openvpn_server_update')

        await self._update_service(old_config, config)

        return await self.config()


class OpenVPNClientService(SystemServiceService):

    class Config:
        namespace = 'openvpn.client'
        service = 'openvpn_client'
        service_model = 'openvpnclient'
        service_verb = 'restart'
        datastore_extend = 'openvpn.client.client_extend'

    @private
    async def client_extend(self, data):
        data['client_certificate'] = None if not data['client_certificate'] else data['client_certificate']['id']
        data['root_ca'] = None if not data['root_ca'] else data['root_ca']['id']
        return data

    @accepts()
    async def authentication_algorithm_choices(self):
        return OpenVPN.digests()

    @accepts()
    async def cipher_choices(self):
        return OpenVPN.ciphers()

    @private
    async def validate(self, data, schema_name):
        verrors = await OpenVPN.common_validation(
            self.middleware, data, schema_name, 'client'
        )

        if not data.get('remote'):
            verrors.add(
                f'{schema_name}.remote',
                'This field is required.'
            )

        if not await self.validate_nobind(data):
            verrors.add(
                f'{schema_name}.nobind',
                'Please enable this to concurrently run OpenVPN Server/Client on the same local port.'
            )

        verrors.check()

    @private
    async def validate_nobind(self, config):
        if (
            await self.middleware.call(
                'service.started',
                'openvpn_server'
            ) and config['port'] == (
                await self.middleware.call('openvpn.server.config')
            )['port'] and not config['nobind']
        ):
            return False
        else:
            return True

    @accepts(
        Dict(
            'openvpn_client_update',
            Bool('nobind'),
            Bool('tls_crypt_auth_enabled'),
            Int('client_certificate'),
            Int('root_ca'),
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
        old_config = await self.config()
        config = old_config.copy()

        config.update(data)

        await self.validate(config, 'openvpn_client_update')

        await self._update_service(old_config, config)

        return await self.config()
