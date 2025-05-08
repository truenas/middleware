from datetime import time

from middlewared.api import api_method
from middlewared.api.current import PoolResilverEntry, PoolResilverUpdateArgs, PoolResilverUpdateResult
from middlewared.service import ConfigService, private, ValidationErrors
import middlewared.sqlalchemy as sa


class PoolResilverModel(sa.Model):
    __tablename__ = 'storage_resilver'

    id = sa.Column(sa.Integer(), primary_key=True)
    enabled = sa.Column(sa.Boolean(), default=True)
    begin = sa.Column(sa.Time(), default=time(hour=18))
    end = sa.Column(sa.Time(), default=time(hour=9))
    weekday = sa.Column(sa.String(120), default='1,2,3,4,5,6,7')


class PoolResilverService(ConfigService):

    class Config:
        namespace = 'pool.resilver'
        datastore = 'storage.resilver'
        datastore_extend = 'pool.resilver.resilver_extend'
        cli_namespace = 'storage.resilver'
        entry = PoolResilverEntry
        role_prefix = 'POOL'

    @private
    async def resilver_extend(self, data):
        data['begin'] = data['begin'].strftime('%H:%M')
        data['end'] = data['end'].strftime('%H:%M')
        data['weekday'] = [int(v) for v in data['weekday'].split(',') if v]
        return data

    @private
    async def validate_fields_and_update(self, data, schema):
        verrors = ValidationErrors()

        weekdays = data.get('weekday')
        if weekdays:
            data['weekday'] = ','.join([str(day) for day in weekdays])
        else:
            verrors.add(
                f'{schema}.weekday',
                'At least one weekday should be selected'
            )

        return verrors, data

    @api_method(PoolResilverUpdateArgs, PoolResilverUpdateResult, roles=['POOL_WRITE'])
    async def do_update(self, data):
        """
        Configure Pool Resilver Priority.

        If `begin` time is greater than `end` time it means it will rollover the day, e.g.
        begin = "19:00", end = "05:00" will increase pool resilver priority from 19:00 of one day
        until 05:00 of the next day.

        `weekday` follows crontab(5) values 0-7 (0 or 7 is Sun).

        .. examples(websocket)::

          Enable pool resilver priority all business days from 7PM to 5AM.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.resilver.update",
                "params": [{
                    "enabled": true,
                    "begin": "19:00",
                    "end": "05:00",
                    "weekday": [1, 2, 3, 4, 5]
                }]
            }
        """
        config = await self.config()
        original_config = config.copy()
        config.update(data)

        verrors, new_config = await self.validate_fields_and_update(config, 'pool_resilver_update')
        verrors.check()

        # before checking if any changes have been made, original_config needs to be mapped to new_config
        original_config['weekday'] = ','.join([str(day) for day in original_config['weekday']])
        original_config['begin'] = time(*(int(value) for value in original_config['begin'].split(':')))
        original_config['end'] = time(*(int(value) for value in original_config['end'].split(':')))
        if len(set(original_config.items()) ^ set(new_config.items())) > 0:
            # data has changed
            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                new_config['id'],
                new_config
            )

            await self.middleware.call('service.restart', 'cron')
            await self.middleware.call('pool.configure_resilver_priority')

        return await self.config()


async def setup(middleware):
    middleware.create_task(middleware.call('pool.configure_resilver_priority'))
