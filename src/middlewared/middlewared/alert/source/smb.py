import time
from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, AlertSource, SimpleOneShotAlertClass
from middlewared.alert.schedule import CrontabSchedule
from middlewared.service_exception import ValidationErrors


def generate_alert_text(auth_log):
    alert_text = {}
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


class SMBLegacyProtocolAlertClass(AlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.NOTICE
    title = "SMB1 connections to TrueNAS server have been performed in last 24 hours"
    text = "The following clients have established SMB1 sessions: %(err)s."


class NTLMv1AuthenticationAlertClass(AlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "NTLMv1 authentication has been attempted in the last 24 hours"
    text = "The following clients have attempted NTLMv1 authentication: %(err)s"


class SMBPathAlertClass(AlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.CRITICAL
    title = "SMB share path has unresolvable issues"
    text = "SMB shares have path-related configuration issues that may impact service stability: %(err)s"


class SMBLegacyProtocolAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=1)  # every 24 hours
    run_on_backup_node = False

    async def check(self):
        if not await self.middleware.call('service.started', 'cifs'):
            return

        now = time.time()
        if not (auth_log := await self.middleware.call('audit.query', {
            'services': ['SMB'],
            'query-filters': [
                ['event', '=', 'AUTHENTICATION'],
                ['message_timestamp', '>', now - 86400],
                ['event_data.serviceDescription', '=', 'SMB']
            ],
            'query-options': {'select': [
                ['event_data.clientAccount', 'clientAccount'],
                ['event_data.becameAccount', 'becameAccount'],
                ['event_data.workstation', 'workstation'],
                'address'
            ]}
        })):
            return

        return Alert(
            SMBLegacyProtocolAlertClass,
            {'err': ', '.join(generate_alert_text(auth_log))},
            key=None
        )


class NTLMv1AuthenticationAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=0)  # every 24 hours
    run_on_backup_node = False

    async def check(self):
        if not await self.middleware.call('service.started', 'cifs'):
            return

        smb_conf = await self.middleware.call('smb.config')
        if smb_conf['ntlmv1_auth']:
            return

        now = time.time()
        if not (auth_log := await self.middleware.call('audit.query', {
            'services': ['SMB'],
            'query-filters': [
                ['event', '=', 'AUTHENTICATION'],
                ['message_timestamp', '>', now - 86400],
                ['event_data.serviceDescription', '=', 'SMB'],
                ['event_data.passwordType', '=', 'NTLMv1']
            ],
            'query-options': {'select': [
                ['event_data.clientAccount', 'clientAccount'],
                ['event_data.becameAccount', 'becameAccount'],
                ['event_data.workstation', 'workstation'],
                'address'
            ]}
        })):
            return

        return Alert(
            NTLMv1AuthenticationAlertClass,
            {'err': ', '.join(generate_alert_text(auth_log))},
            key=None
        )


class SMBPathAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=1)  # every 24 hours
    run_on_backup_node = False

    async def smb_path_alert_format(self, verrors):
        errors = []
        for e in verrors:
            errors.append(f'{e[0].split(":")[0]}: {e[1]}')

        return ', '.join(errors)

    async def check(self):
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
            return

        try:
            msg = await self.smb_path_alert_format(verrors)
        except Exception:
            self.middleware.logger.error('Failed to format error message', exc_info=True)
            return

        return Alert(SMBPathAlertClass, {'err': msg}, key=None)


class SMBUserMissingHashAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "SMB user is missing required password hash"
    text = (
        "One or more SMB users do not have a valid SMB password hash. This can happen if the TrueNAS configuration "
        "was restored without the secret seed. This can also happen if an SMB user was created with an empty password "
        "in an older version of TrueNAS. To correct this, do one of these steps: reset the user password in the TrueNAS "
        "UI or API, or disable SMB access for the user. Affected users: %(entries)s"
    )

    async def delete(self, alerts, query):
        return []
