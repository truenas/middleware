from middlewared.schema import accepts, Bool, Dict, Int, Patch, Ref, returns, Str
from middlewared.service import Service, ValidationErrors


class KeychainCredentialService(Service):

    @accepts(
        Dict(
            'setup_ssh_connection',
            Dict(
                'private_key',
                Bool('generate_key', default=True),
                Int('existing_key_id'),
                Str('name', empty=False),
            ),
            Str('connection_name', required=True),
            Str('setup_type', required=True, enum=['SEMI-AUTOMATIC', 'MANUAL'], default='MANUAL'),
            Patch(
                'keychain_remote_ssh_semiautomatic_setup', 'semi_automatic_setup',
                ('rm', {'name': 'name'}),
                ('rm', {'name': 'private_key'}),
                ('attr', {'null': True}),
                ('attr', {'default': None}),
            ),
            Dict(
                'manual_setup',
                additional_attrs=True,
                null=True,
                default=None,
            )
        ),
        roles=['KEYCHAIN_CREDENTIAL_WRITE'],
    )
    @returns(Ref('keychain_credential_entry'))
    async def setup_ssh_connection(self, options):
        """
        Creates a SSH Connection performing the following steps:

        1) Generating SSH Key Pair if required
        2) Setting up SSH Credentials based on `setup_type`

        In case (2) fails, it will be ensured that SSH Key Pair generated ( if applicable ) in the process is
        removed.
        """
        verrors = ValidationErrors()
        pkey_config = options['private_key']
        schema_name = 'setup_ssh_connection'
        if pkey_config['generate_key']:
            if pkey_config.get('existing_key_id'):
                verrors.add(
                    f'{schema_name}.private_key.existing_key_id', 'Should not be specified when "generate_key" is set'
                )
            if not pkey_config.get('name'):
                verrors.add(f'{schema_name}.private_key.name', 'Must be set when SSH Key pair is to be generated')
            elif await self.middleware.call('keychaincredential.query', [['name', '=', pkey_config['name']]]):
                verrors.add(f'{schema_name}.private_key.name', 'Is already in use by another SSH Key pair')
        else:
            if not pkey_config.get('existing_key_id'):
                verrors.add(
                    f'{schema_name}.private_key.existing_key_id',
                    'Must be specified when SSH Key pair is not to be generated'
                )
            elif not await self.middleware.call(
                'keychaincredential.query', [['id', '=', pkey_config['existing_key_id']]]
            ):
                verrors.add(f'{schema_name}.private_key.existing_key_id', 'SSH Key Pair not found')

        mapping = {'SEMI-AUTOMATIC': 'semi_automatic_setup', 'MANUAL': 'manual_setup'}
        for setup_type, opposite_type in filter(
            lambda x: x[0] == options['setup_type'], [['SEMI-AUTOMATIC', 'MANUAL'], ['MANUAL', 'SEMI-AUTOMATIC']]
        ):
            if not options[mapping[setup_type]]:
                verrors.add(f'{schema_name}.{mapping[setup_type]}', f'Must be specified for {setup_type!r} setup')
            if options[mapping[opposite_type]]:
                verrors.add(
                    f'{schema_name}.{mapping[opposite_type]}', f'Must not be specified for {setup_type!r} setup'
                )

        if await self.middleware.call('keychaincredential.query', [['name', '=', options['connection_name']]]):
            verrors.add(f'{schema_name}.connection_name', 'Is already in use by another Keychain Credential')

        verrors.check()

        # We are going to generate a SSH Key pair now if required
        if pkey_config['generate_key']:
            key_config = await self.middleware.call('keychaincredential.generate_ssh_key_pair')
            ssh_key_pair = await self.middleware.call('keychaincredential.create', {
                'name': pkey_config['name'],
                'type': 'SSH_KEY_PAIR',
                'attributes': key_config,
            })
        else:
            ssh_key_pair = await self.middleware.call('keychaincredential.get_instance', pkey_config['existing_key_id'])

        try:
            if options['setup_type'] == 'SEMI-AUTOMATIC':
                resp = await self.middleware.call(
                    'keychaincredential.remote_ssh_semiautomatic_setup', {
                        **options['semi_automatic_setup'],
                        'private_key': ssh_key_pair['id'],
                        'name': options['connection_name'],
                    }
                )
            else:
                resp = await self.middleware.call(
                    'keychaincredential.create', {
                        'type': 'SSH_CREDENTIALS',
                        'name': options['connection_name'],
                        'attributes': {
                            **options['manual_setup'],
                            'private_key': ssh_key_pair['id'],
                        }
                    }
                )
        except Exception:
            if pkey_config['generate_key']:
                await self.middleware.call('keychaincredential.delete', ssh_key_pair['id'])
            raise
        else:
            return resp
