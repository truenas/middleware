import ipaddress
import os
import subprocess
import tempfile

from middlewared.service import CallError, SystemServiceService, private
from middlewared.schema import accepts, Bool, Dict, Int, IPAddr, Str, ValidationErrors
from middlewared.utils import run
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

        if data['tls_crypt_auth_enabled'] and not data['tls_crypt_auth']:
            verrors.add(
                f'{schema}.tls_crypt_auth',
                'Please provide static key for authentication/encryption of all control '
                'channel packets when tls_crypt_auth_enabled is enabled.'
            )

        data['tls_crypt_auth'] = None if not data.pop('tls_crypt_auth_enabled') else data['tls_crypt_auth']

        return verrors, data


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
        data['tls_crypt_auth_enabled'] = bool(data['tls_crypt_auth'])
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
        verrors, data = await OpenVPN.common_validation(
            self.middleware, data, schema_name, 'server'
        )

        if not await self.validate_nobind(data):
            verrors.add(
                f'{schema_name}.nobind',
                'Please enable "nobind" on OpenVPN Client to concurrently run OpenVPN Server/Client '
                'on the same local port without any issues.'
            )

        if ipaddress.ip_address(data['server']).version == 4 and data['netmask'] > 32:
            verrors.add(
                f'{schema_name}.netmask',
                'For IPv4 server addresses please provide a netmask value from 0-32.'
            )

        verrors.check()

        return data

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

    @private
    async def generate_static_key(self):
        keyfile = tempfile.NamedTemporaryFile(mode='w+', dir='/tmp/')
        await run(
            ['openvpn', '--genkey', '--secret', keyfile.name]
        )
        keyfile.seek(0)
        key = keyfile.read()
        keyfile.close()
        return key.strip()

    @accepts()
    async def renew_static_key(self):
        return await self.update({
            'tls_crypt_auth': (await self.generate_static_key()),
            'tls_crypt_auth_enabled': True
        })

    @accepts(
        Int('client_certificate_id'),
        Str('server_address', null=True)
    )
    async def client_configuration_generation(self, client_certificate_id, server_address=None):
        await self.config_valid()
        config = await self.config()
        root_ca = await self.middleware.call(
            'certificateauthority.query', [
                ['id', '=', config['root_ca']]
            ], {
                'get': True
            }
        )
        client_cert = await self.middleware.call(
            'certificate.query', [
                ['id', '=', client_certificate_id],
                ['revoked', '=', False]
            ]
        )
        if not client_cert:
            raise CallError(
                'Please provide a client certificate id for a certificate which exists on '
                'the system and hasn\'t been marked as revoked.'
            )
        else:
            client_cert = client_cert[0]

        client_config = [
            'client',
            f'dev {config["device_type"].lower()}',
            f'proto {config["protocol"].lower()}',
            f'port {config["port"]}',
            f'remote "{server_address or "PLEASE FILL OUT SERVER DOMAIN/IP HERE"}"',
            'user nobody',
            'group nobody',
            'persist-key',
            'persist-tun',
            '<ca>',
            f'{root_ca["certificate"]}',
            '</ca>',
            '<cert>',
            client_cert['certificate'],
            '</cert>',
            '<key>',
            client_cert['privatekey'],
            '</key>',
            'verb 3',
            'remote-cert-tls server',
            f'compress {config["compression"].lower()}' if config['compression'] else None,
            f'auth {config["authentication_algorithm"]}' if config['authentication_algorithm'] else None,
            f'cipher {config["cipher"]}' if config['cipher'] else None,
        ]

        if config['tls_crypt_auth_enabled']:
            client_config.extend([
                '<tls-crypt>',
                config['tls_crypt_auth'],
                '</tls-crypt>'
            ])

        return (
            '\n'.join(
                filter(
                    bool,
                    client_config
                )
            ) + f'\n{config["additional_parameters"]}'
        ).strip()

    @accepts(
        Dict(
            'openvpn_server_update',
            Bool('tls_crypt_auth_enabled'),
            Int('netmask', validators=[Range(min=0, max=128)]),
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

        # If tls_crypt_auth_enabled is set and we don't have a tls_crypt_auth key,
        # let's generate one please
        if config['tls_crypt_auth_enabled'] and not config['tls_crypt_auth']:
            config['tls_crypt_auth'] = await self.generate_static_key()

        config = await self.validate(config, 'openvpn_server_update')

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
        data['tls_crypt_auth_enabled'] = bool(data['tls_crypt_auth'])
        return data

    @accepts()
    async def authentication_algorithm_choices(self):
        return OpenVPN.digests()

    @accepts()
    async def cipher_choices(self):
        return OpenVPN.ciphers()

    @private
    async def validate(self, data, schema_name):
        verrors, data = await OpenVPN.common_validation(
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

        return data

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

        if not config['client_certificate']:
            raise CallError('Please configure client certificate first.')
        else:
            if not await self.middleware.call(
                'certificate.query', [
                    ['id', '=', config['client_certificate']],
                    ['revoked', '=', False]
                ]
            ):
                raise CallError('Client certificate has been revoked. Please select another Client certificate.')

        if not config['remote']:
            raise CallError('Please configure remote first.')

        if not await self.validate_nobind(config):
            raise CallError(
                'Please enable "nobind" to concurrently run OpenVPN Server/Client on the same local port.'
            )

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

        config = await self.validate(config, 'openvpn_client_update')

        await self._update_service(old_config, config)

        return await self.config()


def setup(middleware):
    for srv in ('openvpn_client', 'openvpn_server'):
        if not os.path.exists(f'/etc/local/rc.d/{srv}'):
            os.symlink('/usr/local/etc/rc.d/openvpn', f'/usr/local/etc/rc.d/{srv}')
