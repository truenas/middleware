from dataclasses import dataclass
import time
from typing import Any

from middlewared.alert.base import (
    Alert,
    AlertCategory,
    AlertClass,
    AlertClassConfig,
    AlertLevel,
    AlertSource,
    OneShotAlertClass,
)
from middlewared.alert.schedule import CrontabSchedule
from middlewared.service_exception import ValidationErrors

AUDIT_MAX_QUERY_ENTRIES = 1000


def generate_alert_text(auth_log: list[dict[str, Any]]) -> list[str]:
    alert_text: dict[str, dict[str, Any]] = {}
    for x in auth_log:
        k = f'{x["clientAccount"] or x["becameAccount"]} - '
        k += x["workstation"] or x["address"]

        if k in alert_text:
            alert_text[k]['cnt'] += 1
            continue

        entry = {
            "client": k,
            "address": x["address"],
            "cnt": 1,
        }
        alert_text[k] = entry

    return [f"{entry['client']} at {entry['address']} ({entry['cnt']} times)" for entry in alert_text.values()]


@dataclass(kw_only=True)
class SMBLegacyProtocolAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.NOTICE,
        title="SMB1 connections to TrueNAS server have been performed in last 24 hours",
        text="The following clients have established SMB1 sessions: %(err)s.",
    )

    err: str

    @classmethod
    def key_from_args(cls, args: Any) -> None:
        return None


@dataclass(kw_only=True)
class NTLMv1AuthenticationAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title="NTLMv1 authentication has been attempted in the last 24 hours",
        text="The following clients have attempted NTLMv1 authentication: %(err)s",
    )

    err: str

    @classmethod
    def key_from_args(cls, args: Any) -> None:
        return None


@dataclass(kw_only=True)
class SMBPathAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.CRITICAL,
        title="SMB share path has unresolvable issues",
        text="SMB shares have path-related configuration issues that may impact service stability: %(err)s",
    )

    err: str

    @classmethod
    def key_from_args(cls, args: Any) -> None:
        return None


class SMBLegacyProtocolAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=1)  # every 24 hours
    run_on_backup_node = False

    async def check(self) -> Alert[Any] | None:
        if not await self.middleware.call('service.started', 'cifs'):
            return None

        now = time.time()
        if not (auth_log := await self.middleware.call('audit.query', {
            'services': ['SMB'],
            'query-filters': [
                ['event', '=', 'AUTHENTICATION'],
                ['message_timestamp', '>', now - 86400],
                ['event_data.serviceDescription', '=', 'SMB']
            ],
            'query-options': {
                'select': ['event_data', 'address'],
                'limit': AUDIT_MAX_QUERY_ENTRIES,
            }
        })):
            return None

        parsed = []
        for entry in auth_log:
            parsed.append({
                'address': entry['address'],
                'clientAccount': entry['event_data'].get('clientAccount'),
                'becameAccount': entry['event_data'].get('becameAccount'),
                'workstation': entry['event_data'].get('workstation'),
            })

        return Alert(SMBLegacyProtocolAlert(
            err=', '.join(generate_alert_text(parsed)),
        ))


class NTLMv1AuthenticationAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=0)  # every 24 hours
    run_on_backup_node = False

    async def check(self) -> Alert[Any] | None:
        if not await self.middleware.call('service.started', 'cifs'):
            return None

        smb_conf = await self.middleware.call('smb.config')
        if smb_conf['ntlmv1_auth']:
            return None

        now = time.time()
        if not (auth_log := await self.middleware.call('audit.query', {
            'services': ['SMB'],
            'query-filters': [
                ['event', '=', 'AUTHENTICATION'],
                ['message_timestamp', '>', now - 86400],
                ['event_data.serviceDescription', '=', 'SMB'],
                ['event_data.passwordType', '=', 'NTLMv1']
            ],
            'query-options': {
                'select': ['event_data', 'address'],
                'limit': AUDIT_MAX_QUERY_ENTRIES,
            }
        })):
            return None

        parsed = []
        for entry in auth_log:
            parsed.append({
                'address': entry['address'],
                'clientAccount': entry['event_data'].get('clientAccount'),
                'becameAccount': entry['event_data'].get('becameAccount'),
                'workstation': entry['event_data'].get('workstation'),
            })

        return Alert(NTLMv1AuthenticationAlert(
            err=', '.join(generate_alert_text(parsed)),
        ))


class SMBPathAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=1)  # every 24 hours
    run_on_backup_node = False

    async def smb_path_alert_format(self, verrors: ValidationErrors) -> str:
        errors: list[str] = []
        for e in verrors:
            errors.append(f'{e[0].split(":")[0]}: {e[1]}')

        return ', '.join(errors)

    async def check(self) -> Alert[Any] | None:
        verrors = ValidationErrors()

        for share in await self.middleware.call('sharing.smb.query', [['enabled', '=', True], ['locked', '=', False]]):
            try:
                await self.middleware.call(
                    'sharing.smb.validate_path_field',
                    share, f'{share["name"]}:', verrors
                )
            except Exception:
                self.middleware.logger.error('Failed to validate path field', exc_info=True)

        if not verrors:
            return None

        try:
            msg = await self.smb_path_alert_format(verrors)
        except Exception:
            self.middleware.logger.error('Failed to format error message', exc_info=True)
            return None

        return Alert(SMBPathAlert(err=msg))


@dataclass(kw_only=True)
class SMBUserMissingHashAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title="SMB user is missing required password hash",
        text=(
            "One or more SMB users do not have a valid SMB password hash. This can happen if the TrueNAS configuration "
            "was restored without the secret seed. This can also happen if an SMB user was created with an empty "
            "password in an older version of TrueNAS. To correct this, do one of these steps: reset the user password "
            "in the TrueNAS UI or API, or disable SMB access for the user. Affected users: %(entries)s"
        ),
        keys=[],
    )

    entries: str
