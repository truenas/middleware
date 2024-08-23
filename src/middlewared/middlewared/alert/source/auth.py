from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertLevel, AlertSource
from middlewared.alert.schedule import CrontabSchedule
from middlewared.utils.audit import UNAUTHENTICATED
from time import time


class AdminSessionAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Administrator account activity"
    text = (
        "The system administrator account was used to authenticate to the UI / API "
        "%(count)d times in the last 24 hours:\n%(sessions)s"
    )


class APIFailedLoginAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "API Login Failures"
    text = (
        "%(count)d API login failures in the last 24 hours:\n%(sessions)s"
    )


def audit_entry_to_msg(entry):
    return (
        f'(username={entry["username"]},'
        f'session_id={entry["session"]},'
        f'address={entry["address"]})'
    )


class AdminSessionAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=1)  # every 24 hours
    run_on_backup_node = True
    products = ('SCALE_ENTERPRISE',)

    async def check(self):
        now = int(time())
        admin_logins = await self.middleware.call('audit.query', {
            'services': ['MIDDLEWARE'],
            'query-filters': [
                ['message_timestamp', '>', now - 86400],
                ['event', '=', 'AUTHENTICATION'],
                ['username', 'in', ['root', 'admin', 'truenas_admin']],
                ['success', '=', True]
            ],
            'query-options': {
                'select': [
                    'message_timestamp',
                    'event',
                    'session',
                    'username',
                    'address',
                    'success'
                ]
            }
        })
        if not admin_logins:
            return

        audit_msg = ','.join([audit_entry_to_msg(entry) for entry in admin_logins])
        return Alert(
            AdminSessionAlertClass,
            {'count': len(admin_logins), 'sessions': audit_msg},
            key=None
        )


class APIFailedLoginAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=1)  # every 24 hours
    run_on_backup_node = True

    async def check(self):
        now = int(time())
        auth_failures = await self.middleware.call('audit.query', {
            'services': ['MIDDLEWARE'],
            'query-filters': [
                ['message_timestamp', '>', now - 86400],
                ['event', '=', 'AUTHENTICATION'],
                ['username', '!=', UNAUTHENTICATED],
                ['success', '=', False]
            ],
            'query-options': {
                'select': [
                    'message_timestamp',
                    'event',
                    'session',
                    'username',
                    'address',
                    'success'
                ]
            }
        })
        if not auth_failures:
            return

        audit_msg = ','.join([audit_entry_to_msg(entry) for entry in auth_failures])
        return Alert(
            APIFailedLoginAlertClass,
            {'count': len(auth_failures), 'sessions': audit_msg},
            key=None
        )
