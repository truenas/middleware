import time
from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import CrontabSchedule


def generate_alert_text(auth_log):
    alert_text = {}
    for x in auth_log:
        k = f'{x["Authentication"]["clientAccount"] or x["Authentication"]["becameAccount"]} - '
        k += x["Authentication"]["workstation"] or x["Authentication"]["remoteAddress"]

        if k in alert_text:
            alert_text[k]['cnt'] += 1
            continue

        entry = {
            "client": k,
            "address": x["Authentication"]["remoteAddress"],
            "cnt": 1,
        }
        alert_text[k] = entry

    return [str(x) for x in alert_text.values()]


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


class SMBLegacyProtocolAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=1)  # every 24 hours
    run_on_backup_node = False

    async def check(self):
        if not await self.middleware.call('service.started', 'cifs'):
            return

        now = time.time()
        auth_log = await self.middleware.call('smb.status', 'AUTH_LOG', [
            ["timestamp_tval.tv_sec", ">", now - 86400],
            ["Authentication.serviceDescription", "=", "SMB"],
        ])
        if not auth_log:
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
        auth_log = await self.middleware.call('smb.status', 'AUTH_LOG', [
            ["timestamp_tval.tv_sec", ">", now - 86400],
            ["Authentication.passwordType", "=", "NTLMv1"]
        ])
        if not auth_log:
            return

        return Alert(
            NTLMv1AuthenticationAlertClass,
            {'err': ', '.join(generate_alert_text(auth_log))},
            key=None
        )
