import asyncio
import contextlib
import datetime
import logging

from truenas_connect_utils.config import get_account_id_and_system_id
from truenas_connect_utils.status import Status
from truenas_connect_utils.urls import get_heartbeat_url

from middlewared.service import CallError, Service
from middlewared.utils.disks_.disk_class import iterate_disks
from middlewared.utils.version import parse_version_string

from .mixin import TNCAPIMixin
from .utils import calculate_sleep, CONFIGURED_TNC_STATES, get_unset_payload, HEARTBEAT_INTERVAL


logger = logging.getLogger('truenas_connect')


class TNCHeartbeatService(Service, TNCAPIMixin):

    class Config:
        namespace = 'tn_connect.heartbeat'
        private = True

    async def call(self, url, mode, payload=None, **kwargs):
        config = await self.middleware.call('tn_connect.config_internal')
        return await self._call(url, mode, payload=payload, headers=await self.auth_headers(config), **(kwargs or {}))

    async def start(self):
        logger.debug('TNC Heartbeat: Starting heartbeat service')
        tnc_config = await self.middleware.call('tn_connect.config_internal')
        creds = get_account_id_and_system_id(tnc_config)
        if tnc_config['status'] != Status.CONFIGURED.name or creds is None:
            raise CallError('TrueNAS Connect is not configured properly')

        heartbeat_url = get_heartbeat_url(tnc_config).format(
            system_id=creds['system_id'],
            version=parse_version_string(await self.middleware.call('system.version_short')),
        )
        disk_mapping = {i.name: i.identifier for i in iterate_disks()}
        while tnc_config['status'] in CONFIGURED_TNC_STATES:
            sleep_error = False
            resp = await self.call(heartbeat_url, 'post', await self.payload(disk_mapping), get_response=False)
            if resp['error'] is not None and resp['status_code'] is None:
                logger.debug('TNC Heartbeat: Failed to connect to heart beat service (%s)', resp['error'])
                sleep_error = True
            else:
                match resp['status_code']:
                    case 202 | 200:
                        # Just keeping this here for valid codes, we don't need to do anything
                        pass
                    case 400:
                        logger.debug('TNC Heartbeat: Received 400')
                        sleep_error = True
                    case 401:
                        logger.debug('TNC Heartbeat: Received 401, unsetting TNC')
                        with contextlib.suppress(Exception):
                            # This is called to just make sure that we setup a self-signed certificate and
                            # remove any alerts which might be there as we are going to unset TNC
                            await self.middleware.call('tn_connect.unset_registration_details', False)
                        await self.middleware.call('datastore.update', 'truenas_connect', tnc_config['id'], {
                            'enabled': False,
                        } | get_unset_payload())
                        self.middleware.send_event(
                            'tn_connect.config', 'CHANGED', fields=await self.middleware.call('tn_connect.config')
                        )
                        await self.middleware.call('alert.oneshot_create', 'TNCDisabledAutoUnconfigured', None)
                        return
                    case 500:
                        logger.debug('TNC Heartbeat: Received 500')
                        sleep_error = True
                    case _:
                        logger.debug('TNC Heartbeat: Received unknown status code %r', resp['status_code'])
                        sleep_error = True

            if sleep_error:
                if tnc_config['last_heartbeat_failure_datetime'] is None:
                    last_failure = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
                    await self.middleware.call('datastore.update', 'truenas_connect', tnc_config['id'], {
                        'last_heartbeat_failure_datetime': last_failure,
                    })
                else:
                    last_failure = tnc_config['last_heartbeat_failure_datetime']

                sleep_secs = calculate_sleep(last_failure, HEARTBEAT_INTERVAL)
                if sleep_secs is None:
                    # This means that either we have a time mismatch or it's been 48 hours and we have
                    # not been able to establish contact with TNC, so an alert should be raised
                    logger.debug(
                        'TNC Heartbeat: Unable to calculate sleep time, raising alert as it has likely been 48 hours '
                        'since the last successful heartbeat (last failure: %s)', last_failure,
                    )
                    await self.middleware.call('alert.oneshot_create', 'TNCHeartbeatConnectionFailure', None)
                    break
                else:
                    logger.debug(
                        'TNC Heartbeat: Sleeping for %d seconds based off last failure (%s)', sleep_secs, last_failure
                    )
                    await asyncio.sleep(sleep_secs)
            else:
                if tnc_config['last_heartbeat_failure_datetime'] is not None:
                    await self.middleware.call('datastore.update', 'truenas_connect', tnc_config['id'], {
                        'last_heartbeat_failure_datetime': None,
                    })
                    logger.debug('TNC Heartbeat: Resetting last heartbeat failure datetime')


                await self.middleware.call('alert.oneshot_delete', 'TNCHeartbeatConnectionFailure')
                await asyncio.sleep(HEARTBEAT_INTERVAL)

            tnc_config = await self.middleware.call('tn_connect.config_internal')

    async def payload(self, disk_mapping=None):
        return {
            'alerts': await self.middleware.call('alert.list'),
            'stats': await self.middleware.call('reporting.realtime.stats', disk_mapping),
        }


async def check_status(middleware):
    tnc_config = await middleware.call('tn_connect.config')
    if tnc_config['status'] in CONFIGURED_TNC_STATES:
        middleware.create_task(middleware.call('tn_connect.heartbeat.start'))


async def _event_system_ready(middleware, event_type, args):
    await check_status(middleware)


async def setup(middleware):
    middleware.event_subscribe('system.ready', _event_system_ready)
    if await middleware.call('system.ready'):
        await check_status(middleware)
