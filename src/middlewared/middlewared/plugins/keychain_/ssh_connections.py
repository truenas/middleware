from middlewared.api import api_method
from middlewared.api.current import (
    KeychainCredentialSetupSshConnectionArgs, KeychainCredentialSetupSshConnectionResult
)
from middlewared.service import Service, ValidationErrors


class KeychainCredentialService(Service):

    async def _validate_options(self, options):
        """
        If `generate_key` is set, ensure that no key with the given name already exists.
        Otherwise, ensure that a key with the given `existing_key_id` does exist.

        Also ensure that a key with the name `connection_name` does not exist yet.
        """
        pkey_config_ = options['private_key']
        schema_name = 'setup_ssh_connection'
        verrors = ValidationErrors()

        if pkey_config_['generate_key']:
            if await self.middleware.call('keychaincredential.query', [['name', '=', pkey_config_['name']]]):
                verrors.add(f'{schema_name}.private_key.name', 'Is already in use by another SSH Key pair')

        elif not await self.middleware.call(
            'keychaincredential.query',
            [['id', '=', pkey_config_['existing_key_id']]]
        ):
            verrors.add(f'{schema_name}.private_key.existing_key_id', 'SSH Key Pair not found')

        if await self.middleware.call('keychaincredential.query', [['name', '=', options['connection_name']]]):
            verrors.add(f'{schema_name}.connection_name', 'Is already in use by another Keychain Credential')

        verrors.check()

    @api_method(
        KeychainCredentialSetupSshConnectionArgs,
        KeychainCredentialSetupSshConnectionResult,
        roles=['KEYCHAIN_CREDENTIAL_WRITE'],
        audit="Setup SSH Connection:",
        audit_extended=lambda options: options["connection_name"]
    )
    async def setup_ssh_connection(self, options):
        """
        Creates an SSH Connection performing the following steps:

        1) Generate SSH Key Pair if required
        2) Set up SSH Credentials based on `setup_type`

        In case (2) fails, it will be ensured that SSH Key Pair generated (if applicable) in the process is
        removed.
        """
        await self._validate_options(options)

        pkey_config_ = options['private_key']
        gen_key_ = pkey_config_['generate_key']

        # We are going to generate a SSH Key pair now if required
        if gen_key_:
            key_config = await self.middleware.call('keychaincredential.generate_ssh_key_pair')
            ssh_key_pair = await self.middleware.call('keychaincredential.create', {
                'name': pkey_config_['name'],
                'type': 'SSH_KEY_PAIR',
                'attributes': key_config,
            })
        else:
            ssh_key_pair = await self.middleware.call(
                'keychaincredential.get_instance',
                pkey_config_['existing_key_id']
            )

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
            if gen_key_:
                await self.middleware.call('keychaincredential.delete', ssh_key_pair['id'])
            raise
        else:
            return resp
