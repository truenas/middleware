import contextlib
import pyotp
import typing

from middlewared.test.integration.utils import call


@contextlib.contextmanager
def enabled_twofactor_auth():
    try:
        yield call('auth.twofactor.update', {'enabled': True, 'window': 3})
    finally:
        call('auth.twofactor.update', {'enabled': False, 'window': 0})


def get_user_secret(user_id: int, get: typing.Optional[bool] = True) -> typing.Union[dict, list]:
    return call('datastore.query', 'account.twofactor_user_auth', [['user_id', '=', user_id]], {'get': get})


def get_2fa_totp_token(users_config: dict) -> str:
    return pyotp.TOTP(
        users_config['secret'],
        interval=users_config['interval'],
        digits=users_config['otp_digits'],
    ).now()
