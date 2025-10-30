from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertLevel, AlertSource
from middlewared.alert.schedule import CrontabSchedule
from middlewared.utils import ProductType
from middlewared.utils.audit import UNAUTHENTICATED
from time import time


URL = "https://www.truenas.com/docs/scale/scaletutorials/credentials/adminroles/"
MAX_LOGINS_LISTED = 100


class AdminSessionAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Administrator account activity"
    text = (
        "The root or default system administrator account was used to authenticate "
        "to the UI / API %(count)d times in the last 24 hours:</br>%(sessions)s.</br>"
        "To improve security, create one or more administrator accounts (see "
        f"<a href=\"{URL}\" target=\"_blank\">documentation</a>) "
        "with unique usernames and passwords and disable password access for default "
        "administrator accounts (<b>root</b>, <b>admin</b>, or <b>truenas_admin</b>)."
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
    products = (ProductType.ENTERPRISE,)

    async def check(self):
        now = int(time())
        qf = [
            ['message_timestamp', '>', now - 86400],
            ['event', '=', 'AUTHENTICATION'],
            ['username', 'in', ['root', 'admin', 'truenas_admin']],
            ['success', '=', True]
        ]

        admin_login_count = await self.middleware.call('audit.query', {
            'services': ['MIDDLEWARE'],
            'query-filters': qf,
            'query-options': {'count': True}
        })
        if not admin_login_count:
            return

        admin_logins = await self.middleware.call('audit.query', {
            'services': ['MIDDLEWARE'],
            'query-filters': qf,
            'query-options': {
                'select': [
                    'message_timestamp',
                    'event',
                    'session',
                    'username',
                    'address',
                    'success'
                ],
                'order_by': [
                    '-message_timestamp'
                ],
                'limit': MAX_LOGINS_LISTED
            }
        })

        audit_msg = ','.join([audit_entry_to_msg(entry) for entry in admin_logins])
        return Alert(
            AdminSessionAlertClass,
            {'count': admin_login_count, 'sessions': audit_msg},
            key=None
        )


class APIFailedLoginAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=1)  # every 24 hours
    run_on_backup_node = True

    async def check(self):
        now = int(time())
        qf = [
            ['message_timestamp', '>', now - 86400],
            ['event', '=', 'AUTHENTICATION'],
            ['username', '!=', UNAUTHENTICATED],
            ['success', '=', False]
        ]

        auth_failure_count = await self.middleware.call('audit.query', {
            'services': ['MIDDLEWARE'],
            'query-filters': qf,
            'query-options': {'count': True}
        })
        if not auth_failure_count:
            return

        auth_failures = await self.middleware.call('audit.query', {
            'services': ['MIDDLEWARE'],
            'query-filters': qf,
            'query-options': {
                'select': [
                    'message_timestamp',
                    'event',
                    'session',
                    'username',
                    'address',
                    'success'
                ],
                'order_by': [
                    '-message_timestamp'
                ],
                'limit': MAX_LOGINS_LISTED
            }
        })
        if not auth_failures:
            return

        audit_msg = ','.join([audit_entry_to_msg(entry) for entry in auth_failures])
        return Alert(
            APIFailedLoginAlertClass,
            {'count': auth_failure_count, 'sessions': audit_msg},
            key=None
        )
