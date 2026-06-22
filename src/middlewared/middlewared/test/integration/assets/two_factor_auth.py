import contextlib
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


# Tracks the last TOTP token handed out per secret so the same one is never returned
# twice: pam_oath enforces RFC 6238 one-time use and rejects a replayed token.
_last_totp_token: dict[str, str] = {}


def get_2fa_totp_token(users_config: dict) -> str:
    """ Return a fresh, single-use TOTP token for the given 2FA config.

    pam_oath rejects a token that has already authenticated within its time step
    (RFC 6238 one-time use), so callers that authenticate repeatedly with the same
    secret (e.g. STIG setup/teardown) must not be handed the same token twice. Wait
    for the next time step when the current token was already used, or is within a few
    seconds of rolling over before the server can validate it.
    """
    secret = users_config['secret']
    interval = users_config['interval']
    totp = pyotp.TOTP(secret, interval=interval, digits=users_config['otp_digits'])

    token = totp.now()
    seconds_left = interval - (time.time() % interval)
    if _last_totp_token.get(secret) == token or seconds_left < 5:
        time.sleep(seconds_left + 1)
        token = totp.now()

    _last_totp_token[secret] = token
    return token
