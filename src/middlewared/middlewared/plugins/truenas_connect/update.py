import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import TNCEntry, TNCUpdateArgs, TNCUpdateResult, TNCIPChoicesArgs, TNCIPChoicesResult
from middlewared.service import ConfigService, private, ValidationErrors

from .status_utils import Status


class TrueNASConnectModel(sa.Model):
    __tablename__ = 'truenas_connect'

    id = sa.Column(sa.Integer(), primary_key=True)
    enabled = sa.Column(sa.Boolean(), default=False, nullable=False)
    jwt_token = sa.Column(sa.EncryptedText(), default=None, nullable=True)
    registration_details = sa.Column(sa.JSON(dict), nullable=False)
    ips = sa.Column(sa.JSON(list), nullable=False)
    status = sa.Column(sa.String(255), default=Status.DISABLED.name, nullable=False)


class TrueNASConnectService(ConfigService):

    # TODO: Add roles
    class Config:
        datastore = 'truenas_connect'
        datastore_extend = 'tn_connect.config_extend'
        cli_private = True
        namespace = 'tn_connect'
        entry = TNCEntry

    @private
    async def config_extend(self, config):
        config['status_reason'] = Status(config['status']).value
        return config

    @private
    async def validate_data(self, old_config, data):
        verrors = ValidationErrors()
        if data['enabled'] and not data['ips']:
            verrors.add('tn_connect_update.ips', 'This field is required when TrueNAS Connect is enabled')

        ip_choices = await self.ip_choices()
        for index, ip in enumerate(data['ips']):
            if ip not in ip_choices:
                verrors.add(f'tn_connect_update.ips.{index}', 'Provided IP is not valid')

        ips_changed = set(old_config['ips']) != set(data['ips'])
        if ips_changed and (
            data['enabled'] is True and old_config['status'] not in (Status.DISABLED.name, Status.CONFIGURED.name)
        ):
            verrors.add(
                'tn_connect_update.ips',
                'IPs cannot be changed when TrueNAS Connect is in a state other than disabled or completely configured'
            )

        verrors.check()

    @api_method(TNCUpdateArgs, TNCUpdateResult)
    async def do_update(self, data):
        """
        Update TrueNAS Connect configuration.
        """
        config = await self.config()
        data = config | data
        await self.validate_data(config, data)

        db_payload = {'enabled': data['enabled'], 'ips': data['ips']}
        if config['enabled'] is False and data['enabled'] is True:
            # TODO: We should make sure to reset any pending registration details
            db_payload['status'] = Status.CLAIM_TOKEN_MISSING.name
        elif config['enabled'] is True and data['enabled'] is False:
            db_payload['status'] = Status.DISABLED.name

        await self.middleware.call('datastore.update', self._config.datastore, config['id'], db_payload)

        # TODO: Handle the case where user imports same db in a different system
        # TODO: Trigger a job to update the registration details if ips are changed

        return await self.config()

    @api_method(TNCIPChoicesArgs, TNCIPChoicesResult)
    async def ip_choices(self):
        """
        Returns IP choices which can be used with TrueNAS Connect.
        """
        return {
            ip['address']: ip['address']
            for ip in await self.middleware.call('interface.ip_in_use', {'static': True, 'any': False})
        }
