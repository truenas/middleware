import contextlib
import pyotp
import typing

from middlewared.test.integration.utils import call


@contextlib.contextmanager
def enabled_twofactor_auth():
    config = call('auth.twofactor.config')
    if not config['enabled']:
        call('auth.twofactor.update', {'enabled': True})
        try:
            yield
        finally:
            call('auth.twofactor.update', {'enabled': False})
    else:
        yield


def get_user_secret(user_id: int, get: typing.Optional[bool] = True) -> typing.Union[dict, list]:
    return call('datastore.query', 'account.twofactor_user_auth', [['user_id', '=', user_id]], {'get': get})


def get_2fa_totp_token(secret: str) -> str:
    twofactor_config = call('auth.twofactor.config')
    return pyotp.TOTP(
        secret,
        interval=twofactor_config['interval'],
        digits=twofactor_config['otp_digits'],
    ).now()
