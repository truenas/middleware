from __future__ import annotations

import contextlib
import enum
import logging
from typing import Any

from truenas_connect_utils.status import Status

import middlewared.sqlalchemy as sa
from middlewared.api.current import TrueNASConnectEntry, TrueNASConnectUpdate
from middlewared.service import ConfigServicePart, ValidationErrors

from .internal import (
    delete_cert,
    get_effective_ips,
    ha_vips,
    unset_registration_details,
)
from .private_models import TrueNASConnectUpdateEnvironment
from .utils import CLAIM_TOKEN_CACHE_KEY, get_unset_payload


logger = logging.getLogger('truenas_connect')

DATASTORE = 'truenas_connect'


class TrueNASConnectTier(enum.IntEnum):
    FOUNDATION = 1
    PLUS = 2
    BUSINESS = 3


class TrueNASConnectModel(sa.Model):
    __tablename__ = DATASTORE

    id = sa.Column(sa.Integer(), primary_key=True)
    enabled = sa.Column(sa.Boolean(), default=False, nullable=False)
    jwt_token = sa.Column(sa.EncryptedText(), default=None, nullable=True)
    registration_details = sa.Column(sa.JSON(dict), nullable=False)
    status = sa.Column(sa.String(255), default=Status.DISABLED.name, nullable=False)
    certificate_id = sa.Column(sa.ForeignKey('system_certificate.id'), index=True, nullable=True)
    account_service_base_url = sa.Column(
        sa.String(255), nullable=False, default='https://account-service.tys1.truenasconnect.net/'
    )
    leca_service_base_url = sa.Column(
        sa.String(255), nullable=False, default='https://dns-service.tys1.truenasconnect.net/'
    )
    tnc_base_url = sa.Column(
        sa.String(255), nullable=False, default='https://web.truenasconnect.net/'
    )
    heartbeat_url = sa.Column(
        sa.String(255), nullable=False, default='https://heartbeat-service.tys1.truenasconnect.net/'
    )
    last_heartbeat_failure_datetime = sa.Column(sa.String(255), nullable=True, default=None)


class TrueNASConnectConfigServicePart(ConfigServicePart[TrueNASConnectEntry]):
    _datastore = DATASTORE
    _entry = TrueNASConnectEntry

    async def extend(self, data: dict[str, Any]) -> dict[str, Any]:
        data['status_reason'] = Status[data['status']].value
        data.pop('jwt_token', None)
        if data['certificate']:
            data['certificate'] = data['certificate']['id']

        try:
            data['tier'] = TrueNASConnectTier(data['registration_details']['tier']).name
        except (KeyError, ValueError):
            data['tier'] = None

        return data

    async def do_update(self, data: TrueNASConnectUpdate) -> TrueNASConnectEntry:
        old = await self.config()
        new = old.updated(data)

        await self._validate(new)

        db_payload: dict[str, Any] = {
            'enabled': new.enabled,
        }
        tnc_disabled = False

        if old.enabled is False and new.enabled is True:
            # Finalization registration is triggered when claim token is generated
            # We make sure there is no pending claim token
            with contextlib.suppress(KeyError):
                await self.middleware.call('cache.pop', CLAIM_TOKEN_CACHE_KEY)
            db_payload['status'] = Status.CLAIM_TOKEN_MISSING.name
            logger.debug('Removing any stale TNC unconfigured alert or heartbeat alert')
            await self.call2(self.s.alert.oneshot_delete, 'TNCDisabledAutoUnconfigured')
            await self.call2(self.s.alert.oneshot_delete, 'TNCHeartbeatConnectionFailure')
        elif old.enabled is True and new.enabled is False:
            await unset_registration_details(self)
            db_payload.update(get_unset_payload())
            tnc_disabled = True

        await self.middleware.call('datastore.update', DATASTORE, old.id, db_payload)

        if tnc_disabled:
            # If TNC is disabled and was enabled earlier, we will like to restart UI and delete TNC cert
            logger.debug('Restarting nginx to not use TNC certificate anymore')
            await self.middleware.call('system.general.ui_restart', 4)

            if old.certificate is not None:
                await delete_cert(self, old.certificate)

        new_config = await self.config()
        self.middleware.send_event('tn_connect.config', 'CHANGED', fields=new_config.model_dump())

        return new_config

    async def _validate(self, new: TrueNASConnectEntry) -> None:
        verrors = ValidationErrors()
        if new.enabled:
            if await self.middleware.call('system.is_ha_capable'):
                if not await ha_vips(self):
                    verrors.add(
                        'tn_connect_update.enabled',
                        'HA systems must be in a healthy state to enable TNC ensuring '
                        'we have VIP available'
                    )
            else:
                effective_ips = await get_effective_ips(self)
                if not effective_ips:
                    verrors.add(
                        'tn_connect_update.enabled',
                        'System must have at least one IP address configured in System > General settings '
                        'to enable TrueNAS Connect'
                    )

        verrors.check()

    async def update_environment(
        self, data: TrueNASConnectUpdateEnvironment,
    ) -> TrueNASConnectEntry:
        config = await self.config()
        verrors = ValidationErrors()
        if config.enabled:
            for field in (
                'account_service_base_url', 'leca_service_base_url', 'tnc_base_url', 'heartbeat_url',
            ):
                if field not in data.model_fields_set:
                    continue
                # HttpsOnlyURL parses to a Url object — direct equality with a str returns False
                # even for matching strings, so coerce both sides.
                new_val = str(getattr(data, field))
                old_val = str(getattr(config, field))
                if new_val != old_val:
                    verrors.add(
                        f'tn_connect_update_environment.{field}',
                        'This field cannot be changed when TrueNAS Connect is enabled'
                    )

        verrors.check()

        # Coerce HttpsOnlyURL fields to str before datastore write — SQLite stores strings.
        db_payload = {
            k: str(v) for k, v in data.model_dump(exclude_unset=True).items()
        }
        await self.middleware.call('datastore.update', DATASTORE, config.id, db_payload)

        return await self.config()
