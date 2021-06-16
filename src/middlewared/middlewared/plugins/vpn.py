import ipaddress
import os
import subprocess
import tempfile

from middlewared.common.listen import SystemServiceListenSingleDelegate
from middlewared.service import CallError, SystemServiceService, private
from middlewared.schema import accepts, Bool, Dict, Int, IPAddr, Patch, Ref, returns, Str, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils import osc, run
from middlewared.validators import Port, Range


PROTOCOLS = ['UDP', 'UDP4', 'UDP6', 'TCP', 'TCP4', 'TCP6']


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
    async def cert_validation(middleware, data, schema, mode, verrors):
        root_ca = await middleware.call(
            'certificateauthority.query', [
                ['id', '=', data['root_ca']],
                ['revoked', '=', False]
            ]
        )

        if not root_ca:
            verrors.add(
                f'{schema}.root_ca',
                'Please provide a valid id for Root Certificate Authority which exists on the system '
                'and hasn\'t been revoked.'
            )
        else:
            # Validate root ca
            root_ca = root_ca[0]
            extensions = root_ca['extensions']
            for ext in ('BasicConstraints', 'KeyUsage', 'SubjectKeyIdentifier'):
                if not extensions.get(ext):
                    verrors.add(
                        f'{schema}.root_ca',
                        f'Root CA must have {ext} extension set.'
                    )

            if 'CA:TRUE' not in (extensions.get('BasicConstraints') or ''):
                verrors.add(
                    f'{schema}.root_ca',
                    'Root CA must have CA=TRUE set for BasicConstraints extension.'
                )

            for k in ('Certificate Sign', 'CRL Sign'):
                if k not in (extensions.get('KeyUsage') or ''):
                    verrors.add(
                        f'{schema}.root_ca',
                        f'Root CA must have {k} set for KeyUsage extension.'
                    )

        cert_id = data[f'{mode}_certificate']
        if not cert_id:
            return verrors

        cert = await middleware.call(
            'certificate.query', [
                ['id', '=', cert_id],
                ['revoked', '=', False]
            ]
        )

        if not cert:
            verrors.add(
                f'{schema}.{mode}_certificate',
                f'Please provide a valid id for {mode.capitalize()} certificate which exists on '
                'the system and hasn\'t been revoked.'
            )
        else:
            # Validate server/client cert
            cert = cert[0]
            if root_ca and not await middleware.call(
                'cryptokey.validate_cert_with_chain',
                cert['certificate'], [root_ca['certificate']]
            ):
                verrors.add(
                    f'{schema}.{mode}_certificate',
                    f'{mode} certificate chain could not be verified with specified root CA.'
                )
            extensions = cert['extensions']
            for ext in ('KeyUsage', 'SubjectKeyIdentifier', 'ExtendedKeyUsage'):
                if not extensions.get(ext):
                    verrors.add(
                        f'{schema}.{mode}_certificate',
                        f'{mode.capitalize()} certificate must have {ext} extension set.'
                    )

            if mode == 'client':
                if not cert['common']:
                    # This is required for openvpn clients - https://community.openvpn.net/openvpn/ticket/81
                    # Otherwise we get "VERIFY ERROR: could not extract CN from X509 subject string"
                    verrors.add(
                        f'{schema}.client_certificate',
                        'Client certificate requires common name (CN) to be set to verify properly.'
                    )
                if not any(
                    k in (extensions.get('KeyUsage') or '')
                    for k in ('Digital Signature', 'Key Agreement')
                ):
                    verrors.add(
                        f'{schema}.client_certificate',
                        'Client certificate must have "Digital Signature" and/or '
                        '"Key Agreement" set for KeyUsage extension.'
                    )

                if 'TLS Web Client Authentication' not in (extensions.get('ExtendedKeyUsage') or ''):
                    verrors.add(
                        f'{schema}.client_certificate',
                        'Client certificate must have "TLS Web Client Authentication" '
                        'set in ExtendedKeyUsage extension.'
                    )
            else:
                if not any(
                    k in (extensions.get('KeyUsage') or '')
                    for k in ('Key Encipherment', 'Key Agreement')
                ) or 'Digital Signature' not in (extensions.get('KeyUsage') or ''):
                    verrors.add(
                        f'{schema}.server_certificate',
                        'Server certificate must have "Digital Signature" and either '
                        '"Key Agreement" or "Key Encipherment" set for KeyUsage extension.'
                    )

                if 'TLS Web Server Authentication' not in (extensions.get('ExtendedKeyUsage') or ''):
                    verrors.add(
                        f'{schema}.server_certificate',
                        'Server certificate must have "TLS Web Server Authentication" '
                        'set in ExtendedKeyUsage extension.'
                    )

        return verrors

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

        if data['root_ca']:
            verrors = await OpenVPN.cert_validation(middleware, data, schema, mode, verrors)

        if data['tls_crypt_auth_enabled'] and not data['tls_crypt_auth']:
            verrors.add(
                f'{schema}.tls_crypt_auth',
                'Please provide static key for authentication/encryption of all control '
                'channel packets when tls_crypt_auth_enabled is enabled.'
            )

        data['tls_crypt_auth'] = None if not data.pop('tls_crypt_auth_enabled') else data['tls_crypt_auth']

        return verrors, data


class OpenVPNServerModel(sa.Model):
    __tablename__ = 'services_openvpnserver'

    id = sa.Column(sa.Integer(), primary_key=True)
    port = sa.Column(sa.Integer(), default=1194)
    protocol = sa.Column(sa.String(4), default='UDP')
    device_type = sa.Column(sa.String(4), default='TUN')
    authentication_algorithm = sa.Column(sa.String(32), nullable=True)
    tls_crypt_auth = sa.Column(sa.Text(), nullable=True)
    cipher = sa.Column(sa.String(32), nullable=True)
    compression = sa.Column(sa.String(32), nullable=True)
    additional_parameters = sa.Column(sa.Text())
    server_certificate_id = sa.Column(sa.ForeignKey('system_certificate.id'), index=True, nullable=True)
    root_ca_id = sa.Column(sa.ForeignKey('system_certificateauthority.id'), index=True, nullable=True)
    server = sa.Column(sa.String(45))
    topology = sa.Column(sa.String(16), nullable=True)
    netmask = sa.Column(sa.Integer(), default=24)


class OpenVPNServerService(SystemServiceService):

    class Config:
        namespace = 'openvpn.server'
        service = 'openvpn_server'
        service_model = 'openvpnserver'
        service_verb = 'restart'
        datastore_extend = 'openvpn.server.server_extend'
        cli_namespace = 'service.openvpn.server'

    ENTRY = Dict(
        'openvpn_server_entry',
        Bool('tls_crypt_auth_enabled', required=True),
        Int('id', required=True),
        Int('netmask', validators=[Range(min=0, max=128)], required=True),
        Int('server_certificate', null=True, required=True),
        Int('port', validators=[Port()], required=True),
        Int('root_ca', null=True, required=True),
        IPAddr('server', required=True),
        Str('additional_parameters', required=True),
        Str('authentication_algorithm', null=True, required=True),
        Str('cipher', null=True, required=True),
        Str('compression', null=True, enum=['LZO', 'LZ4'], required=True),
        Str('device_type', enum=['TUN', 'TAP'], required=True),
        Str('protocol', enum=PROTOCOLS, required=True),
        Str('tls_crypt_auth', null=True, required=True),
        Str('topology', null=True, enum=['NET30', 'P2P', 'SUBNET'], required=True),
        Str('interface', required=True),
    )

    @private
    async def server_extend(self, data):
        data.update({
            'server_certificate': None if not data['server_certificate'] else data['server_certificate']['id'],
            'root_ca': None if not data['root_ca'] else data['root_ca']['id'],
            'tls_crypt_auth_enabled': bool(data['tls_crypt_auth']),
            'interface': 'openvpn-server',
        })
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
    @returns(Dict(
        'openvpn_authentication_algorithm_choices',
        additional_attrs=True,
        register=True,
        example={'RSA-SHA512': '512 bit digest size'}
    ))
    async def authentication_algorithm_choices(self):
        """
        Returns a dictionary of valid authentication algorithms which can be used with OpenVPN server.
        """
        return OpenVPN.digests()

    @accepts()
    @returns(Dict(
        'openvpn_cipher_choices',
        additional_attrs=True,
        example={'RC2-40-CBC': '(40 bit key by default, 64 bit block)'},
        register=True,
    ))
    async def cipher_choices(self):
        """
        Returns a dictionary of valid ciphers which can be used with OpenVPN server.
        """
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
    @returns(Ref('openvpn_server_entry'))
    async def renew_static_key(self):
        """
        Reset OpenVPN server's TLS static key which will be used to encrypt/authenticate control channel packets.
        """
        return await self.update({
            'tls_crypt_auth': (await self.generate_static_key()),
            'tls_crypt_auth_enabled': True
        })

    @accepts(
        Int('client_certificate_id'),
        Str('server_address', null=True, default=None)
    )
    @returns(Str('openvpn_client_config', max_length=None))
    async def client_configuration_generation(self, client_certificate_id, server_address):
        """
        Returns a configuration for OpenVPN client which can be used with any client to connect to FN/TN OpenVPN
        server.

        `client_certificate_id` should be a valid certificate issued for use with OpenVPN client service.

        `server_address` if specified auto-fills the remote directive in the OpenVPN configuration enabling the end
        user to use the file without making any edits to connect to OpenVPN server.
        """
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
            verrors = (
                await OpenVPN.common_validation(
                    self.middleware, {
                        **config,
                        'client_certificate': client_certificate_id
                    }, '', 'client'
                )
            )[0]
            if verrors:
                err_str = '\n'.join([f'{i + 1}) {error.errmsg}' for i, error in enumerate(verrors.errors)])

                raise CallError(
                    f'Please ensure provided client certificate is valid, following errors were found:\n{err_str}'
                )

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

        return '\n'.join(filter(bool, client_config)).strip()

    @accepts(
        Patch(
            'openvpn_server_entry', 'openvpn_server_update',
            ('rm', {'name': 'id'}),
            ('rm', {'name': 'interface'}),
            ('attr', {'update': True}),
        ),
    )
    async def do_update(self, data):
        """
        Update OpenVPN Server configuration.

        When `tls_crypt_auth_enabled` is enabled and `tls_crypt_auth` not provided, a static key is automatically
        generated to be used with OpenVPN server.
        """
        old_config = await self.config()
        old_config.pop('interface')
        config = old_config.copy()

        config.update(data)

        # If tls_crypt_auth_enabled is set and we don't have a tls_crypt_auth key,
        # let's generate one please
        if config['tls_crypt_auth_enabled'] and not config['tls_crypt_auth']:
            config['tls_crypt_auth'] = await self.generate_static_key()

        config = await self.validate(config, 'openvpn_server_update')

        await self._update_service(old_config, config)

        return await self.config()


class OpenVPNClientModel(sa.Model):
    __tablename__ = 'services_openvpnclient'

    id = sa.Column(sa.Integer(), primary_key=True)
    port = sa.Column(sa.Integer(), default=1194)
    protocol = sa.Column(sa.String(4), default='UDP')
    device_type = sa.Column(sa.String(4), default='TUN')
    nobind = sa.Column(sa.Boolean(), default=True)
    authentication_algorithm = sa.Column(sa.String(32), nullable=True)
    tls_crypt_auth = sa.Column(sa.Text(), nullable=True)
    cipher = sa.Column(sa.String(32), nullable=True)
    compression = sa.Column(sa.String(32), nullable=True)
    additional_parameters = sa.Column(sa.Text())
    client_certificate_id = sa.Column(sa.ForeignKey('system_certificate.id'), index=True, nullable=True)
    root_ca_id = sa.Column(sa.ForeignKey('system_certificateauthority.id'), index=True, nullable=True)
    remote = sa.Column(sa.String(120))


class OpenVPNClientService(SystemServiceService):

    class Config:
        namespace = 'openvpn.client'
        service = 'openvpn_client'
        service_model = 'openvpnclient'
        service_verb = 'restart'
        datastore_extend = 'openvpn.client.client_extend'
        cli_namespace = 'service.openvpn.client'

    ENTRY = Dict(
        'openvpn_client_entry',
        Bool('nobind', required=True),
        Bool('tls_crypt_auth_enabled', required=True),
        Int('client_certificate', null=True, required=True),
        Int('id', required=True),
        Int('root_ca', null=True, required=True),
        Int('port', validators=[Port()], required=True),
        Str('additional_parameters', required=True),
        Str('authentication_algorithm', null=True, required=True),
        Str('cipher', null=True, required=True),
        Str('compression', null=True, enum=['LZO', 'LZ4'], required=True),
        Str('device_type', enum=['TUN', 'TAP'], required=True),
        Str('interface', required=True),
        Str('protocol', enum=PROTOCOLS, required=True),
        Str('remote', required=True),
        Str('tls_crypt_auth', null=True, required=True),
    )

    @private
    async def client_extend(self, data):
        data.update({
            'client_certificate': None if not data['client_certificate'] else data['client_certificate']['id'],
            'root_ca': None if not data['root_ca'] else data['root_ca']['id'],
            'tls_crypt_auth_enabled': bool(data['tls_crypt_auth']),
            'interface': 'openvpn-client',
        })
        return data

    @accepts()
    @returns(Ref('openvpn_authentication_algorithm_choices'))
    async def authentication_algorithm_choices(self):
        """
        Returns a dictionary of valid authentication algorithms which can be used with OpenVPN server.
        """
        return OpenVPN.digests()

    @accepts()
    @returns(Ref('openvpn_cipher_choices'))
    async def cipher_choices(self):
        """
        Returns a dictionary of valid ciphers which can be used with OpenVPN server.
        """
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
        Patch(
            'openvpn_client_entry', 'openvpn_client_update',
            ('rm', {'name': 'id'}),
            ('rm', {'name': 'interface'}),
            ('attr', {'update': True}),
        ),
    )
    async def do_update(self, data):
        """
        Update OpenVPN Client configuration.

        `remote` can be a valid ip address / domain which openvpn will try to connect to.

        `nobind` must be enabled if OpenVPN client / server are to run concurrently.
        """
        old_config = await self.config()
        old_config.pop('interface')
        config = old_config.copy()

        config.update(data)

        config = await self.validate(config, 'openvpn_client_update')

        await self._update_service(old_config, config)

        return await self.config()


async def _event_system(middleware, event_type, args):

    # TODO: Let's please make sure openvpn functions as desired in scale
    if osc.IS_FREEBSD and args['id'] == 'ready':
        for srv in await middleware.call(
            'service.query', [
                ['enable', '=', True], ['OR', [['service', '=', 'openvpn_server'], ['service', '=', 'openvpn_client']]]
            ]
        ):
            await middleware.call('service.start', srv['service'])


async def setup(middleware):
    await middleware.call(
        'interface.register_listen_delegate',
        SystemServiceListenSingleDelegate(middleware, 'openvpn.server', 'server'),
    )
    middleware.event_subscribe('system', _event_system)
    if not os.path.exists('/usr/local/etc/rc.d/openvpn'):
        return
    for srv in ('openvpn_client', 'openvpn_server'):
        if not os.path.exists(f'/etc/local/rc.d/{srv}'):
            os.symlink('/usr/local/etc/rc.d/openvpn', f'/usr/local/etc/rc.d/{srv}')
