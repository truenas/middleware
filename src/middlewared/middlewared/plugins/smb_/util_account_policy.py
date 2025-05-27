import enum

from subprocess import run
from .constants import SMBCmd


class SMBAccountPolicy(enum.StrEnum):
    MIN_PASSWORD_AGE = 'minimum password age'
    MAX_PASSWORD_AGE = 'maximum password age'
    MIN_PASSWORD_LENGTH = 'min password length'

    @property
    def default(self):
        # Samba passdb defaults
        match self:
            case SMBAccountPolicy.MIN_PASSWORD_AGE:
                return 0
            case SMBAccountPolicy.MAX_PASSWORD_AGE:
                return 2 ** 32 - 1
            case SMBAccountPolicy.MIN_PASSWORD_LENGTH:
                return 5
            case _:
                raise ValueError(f'{self}: unexpected AccountPolicy')


def get_account_policy(policy: SMBAccountPolicy) -> int:
    rv = run([SMBCmd.PDBEDIT.value, '-P', str(policy)], capture_output=True, check=False)
    if rv.returncode:
        raise RuntimeError(f'{policy}: Failed to get account policy: {rv.stderr.decode()}')

    value = rv.stdout.decode().split('value is:')[1].strip()
    return int(value)


def set_account_policy(policy: SMBAccountPolicy, value: int) -> None:
    rv = run([SMBCmd.PDBEDIT.value, '-P', str(policy), '-C', str(value)], capture_output=True, check=False)
    if rv.returncode:
        raise RuntimeError(f'Failed to set {policy} to {value}: {rv.stderr.decode()}')


def sync_account_policy(security: dict) -> None:
    for account_policy in SMBAccountPolicy:
        sec_key = account_policy.name.lower()

        match sec_key:
            case 'min_password_age' | 'max_password_age':
                if security[sec_key] is None:
                    value = account_policy.default
                else:
                    value = security[sec_key] * 86400  # passdb expects in seconds rather than days
            case _:
                value = security[sec_key] or account_policy.default

        set_account_policy(account_policy, value)
