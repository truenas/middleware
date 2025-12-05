# -*- coding=utf-8 -*-
import errno
import logging

from aiohttp import ClientSession, ClientTimeout, ClientError

from middlewared.api import api_method
from middlewared.api.current import NetworkConfigurationActivityChoicesArgs, NetworkConfigurationActivityChoicesResult
from middlewared.service import CallError, NetworkActivityDisabled, private, Service

logger = logging.getLogger(__name__)


CONNECTIVITY_CHECK_URL = 'http://www.gstatic.com/generate_204'
CONNECTIVITY_CHECK_TIMEOUT = 10


class NetworkConfigurationService(Service):
    class Config:
        namespace = 'network.configuration'

    @api_method(
        NetworkConfigurationActivityChoicesArgs,
        NetworkConfigurationActivityChoicesResult,
        roles=["NETWORK_GENERAL_READ"]
    )
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
    async def check_internet_connectivity(self):
        """
        Check internet connectivity by making an HTTP request to a known endpoint.
        This verifies both DNS resolution and network connectivity.
        Returns True if connected, raises CallError otherwise.
        """
        try:
            async with ClientSession(
                timeout=ClientTimeout(total=CONNECTIVITY_CHECK_TIMEOUT),
                trust_env=True
            ) as session:
                async with session.get(CONNECTIVITY_CHECK_URL) as resp:
                    if resp.status == 204:
                        return True
                    raise CallError(
                        f'Unexpected response from connectivity check: {resp.status}',
                        errno.ENETUNREACH
                    )
        except ClientError as e:
            raise CallError(
                f'Internet connectivity check failed: {e}',
                errno.ENETUNREACH
            )
        except TimeoutError:
            raise CallError(
                'Internet connectivity check timed out',
                errno.ETIMEDOUT
            )

    @private
    async def will_perform_activity(self, name, check_connectivity=False):
        if not await self.middleware.call('network.general.can_perform_activity', name):
            raise NetworkActivityDisabled(f'Network activity "{self.activities[name]}" is disabled')

        if check_connectivity:
            await self.check_internet_connectivity()
