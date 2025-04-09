import contextlib
from datetime import datetime
import time
import typing

import pyotp

from middlewared.test.integration.utils import call


@contextlib.contextmanager
def enabled_twofactor_auth(ssh=False):
    try:
        yield call('auth.twofactor.update', {'enabled': True, 'window': 3, 'services': {'ssh': ssh}})
    finally:
        call('auth.twofactor.update', {'enabled': False, 'window': 0, 'services': {'ssh': False}})


def get_user_secret(user_id: int, get: typing.Optional[bool] = True) -> typing.Union[dict, list]:
    return call('datastore.query', 'account.twofactor_user_auth', [['user_id', '=', user_id]], {'get': get})


def get_user_secret_sid(user_sid: str, get: typing.Optional[bool] = True) -> typing.Union[dict, list]:
    return call('datastore.query', 'account.twofactor_user_auth', [['user_sid', '=', user_sid]], {'get': get})


def get_2fa_totp_token(users_config: dict) -> str:
    second = datetime.now().second
    if second >= 55 or second < 5:
        # We allow 5 seconds time difference between NAS and test client, and OTP expiry interval is 60 seconds.
        # So tokens generated within 5 seconds of :00 are not safe to use
        time.sleep(10)

    return pyotp.TOTP(
        users_config['secret'],
        interval=users_config['interval'],
        digits=users_config['otp_digits'],
    ).now()
