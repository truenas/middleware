import asyncio
import datetime
import logging

from truenas_connect_utils.config import get_account_id_and_system_id
from truenas_connect_utils.urls import get_heartbeat_url

from middlewared.service import CallError, Service
from middlewared.utils.disks_.disk_class import iterate_disks
from middlewared.utils.version import parse_version_string

from .mixin import TNCAPIMixin
from .utils import (
    calculate_sleep, CONFIGURED_TNC_STATES, decode_and_validate_token, HEARTBEAT_INTERVAL,
)


logger = logging.getLogger('truenas_connect')


class TNCHeartbeatService(Service, TNCAPIMixin):

    class Config:
        namespace = 'tn_connect.heartbeat'
        private = True

    async def call(self, url, mode, payload=None, **kwargs):
        config = await self.middleware.call('tn_connect.config_internal')
        return await self._call(url, mode, payload=payload, headers=await self.auth_headers(config), **(kwargs or {}))

    async def persist_new_token(self, tnc_config, new_token):
        try:
            decoded_token = decode_and_validate_token(new_token)
        except ValueError as e:
            logger.error('TNC Heartbeat: failed to validate rotated token: %s', e)
            return

        await self.middleware.call(
            'datastore.update',
            'truenas_connect',
            tnc_config['id'],
            {
                'jwt_token': new_token,
                'registration_details': decoded_token,
            },
        )
        # Keep the in-memory config in sync so the very next request authenticates with the new token.
        tnc_config.update({
            'jwt_token': new_token,
            'registration_details': decoded_token,
        })
        logger.info('TNC Heartbeat: rotated to new token')

    async def maybe_install_license(self, pem):
        # TNC re-sends the same PEM until our heartbeat reports its id, so skip when it is already
        # installed; reinstalling would needlessly re-run etc.generate / license hooks / ctdb restart.
        current = await self.middleware.call('system.license', True)
        if current and (current.get('raw_license') or '').strip() == pem.strip():
            logger.debug('TNC Heartbeat: delivered license already installed, skipping')
            return

        try:
            await self.middleware.call('truenas.license.upload', pem)
        except Exception:
            logger.error('TNC Heartbeat: failed to install delivered license', exc_info=True)
        else:
            logger.info('TNC Heartbeat: installed license delivered by TNC')

    async def handle_response(self, tnc_config, status_code, body):
        # Act on what the body carries, not on the token_status/license_status strings: a new token
        # can be issued while the presented one is still active, and an error response would not carry
        # the heartbeat body at all. Field presence is the safer, decoupled trigger.
        new_token = body.get('new_token')
        pem = body.get('license')

        if new_token:
            await self.persist_new_token(tnc_config, new_token)
        if pem:
            await self.maybe_install_license(pem)

        # A 205 means the body carries an artifact the NAS must install before its next heartbeat. If
        # it carries neither a license nor a new token, TNC violated its own contract; surface it
        # rather than silently skipping. A 202 with a pending license but no PEM is normal (signing in
        # progress), so it is intentionally not flagged here.
        if status_code == 205 and not new_token and not pem:
            logger.warning('TNC Heartbeat: received 205 but the response carried no license or token to install')

    async def start(self):
        logger.debug('TNC Heartbeat: Starting heartbeat service')
        tnc_config = await self.middleware.call('tn_connect.config_internal')
        creds = get_account_id_and_system_id(tnc_config)
        if tnc_config['status'] not in CONFIGURED_TNC_STATES or creds is None:
            raise CallError('TrueNAS Connect is not configured properly')

        heartbeat_url = get_heartbeat_url(tnc_config).format(
            system_id=creds['system_id'],
            version=parse_version_string(await self.middleware.call('system.version_short')),
        )
        disk_mapping = {i.name: i.identifier for i in iterate_disks()}
        while tnc_config['status'] in CONFIGURED_TNC_STATES:
            sleep_error = False
            resp = await self.call(heartbeat_url, 'post', await self.payload(disk_mapping))
            if resp['error'] is not None and resp['status_code'] is None:
                logger.debug('TNC Heartbeat: Failed to connect to heart beat service (%s)', resp['error'])
                sleep_error = True
            else:
                match resp['status_code']:
                    case 202 | 205:
                        await self.handle_response(tnc_config, resp['status_code'], resp['response'] or {})
                    case 401:
                        # An error response is an ErrorResponse ({"error": ..., "data": {...}}), not the
                        # heartbeat body, so the token_status reason lives under "data" when present.
                        reason = (resp['response'] or {}).get('data') or {}
                        logger.info(
                            'TNC Heartbeat: Received 401 (token_status=%s), unsetting TNC',
                            reason.get('token_status'),
                        )
                        await self.middleware.call('tn_connect.handle_tnc_deregistration')
                        return
                    case 400 | 500:
                        logger.debug('TNC Heartbeat: Received %r', resp['status_code'])
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
        stats = await self.middleware.call('reporting.realtime.stats', disk_mapping)
        # We would like to add app/vm stats here as well now
        apps = await self.middleware.call('app.query')
        vms = await self.middleware.call('vm.query')
        stats.update({
            'apps': {
                'total': len(apps),
                'running': len([app for app in apps if app['state'] == 'RUNNING']),
            },
            'vms': {
                'total': len(vms),
                'running': len([vm for vm in vms if vm['status']['state'] == 'RUNNING']),
            },
        })

        # A fingerprint hiccup must not take down the heartbeat, so degrade to null on failure.
        try:
            fingerprint = await self.middleware.call('truenas.license.fingerprint')
        except Exception:
            logger.error('TNC Heartbeat: failed to compute system fingerprint', exc_info=True)
            fingerprint = None

        # license_id is the delivery acknowledgement: once we report the id of an installed license,
        # TNC marks it accepted and stops resending the PEM. Null when we hold no valid license.
        license_info = await self.middleware.call('truenas.license.info')

        return {
            'alerts': await self.middleware.call('alert.list'),
            'stats': stats,
            'fingerprint': fingerprint,
            'license_id': license_info['id'] if license_info else None,
        }
