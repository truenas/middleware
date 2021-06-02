# -*- coding=utf-8 -*-
import logging

from middlewared.schema import List, returns, Str
from middlewared.service import accepts, CallError, private, Service

logger = logging.getLogger(__name__)


class NetworkConfigurationService(Service):
    class Config:
        namespace = 'network.configuration'

    @accepts()
    @returns(List('activity_choices', items=[List('activity_choice', items=[Str('activity')])]))
    async def activity_choices(self):
        """
        Returns allowed/forbidden network activity choices.
        """
        return await self.middleware.call('network.general.activity_choices')


class NetworkGeneralService(Service):
    class Config:
        namespace = 'network.general'

    activities = {}

    @private
    def register_activity(self, name, description):
        if name in self.activities:
            raise RuntimeError(f'Network activity {name} is already registered')

        self.activities[name] = description

    @private
    def activity_choices(self):
        return sorted([[k, v] for k, v in self.activities.items()], key=lambda t: t[1].lower())

    @private
    async def can_perform_activity(self, name):
        if name not in self.activities:
            raise RuntimeError(f'Unknown network activity {name}')

        config = await self.middleware.call('network.configuration.config')
        if config['activity']['type'] == 'ALLOW':
            return name in config['activity']['activities']
        else:
            return name not in config['activity']['activities']

    @private
    async def will_perform_activity(self, name):
        if not await self.middleware.call('network.general.can_perform_activity', name):
            raise CallError(f'Network activity "{self.activities[name]}" is disabled')
