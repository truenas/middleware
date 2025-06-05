import enum
from dataclasses import dataclass

from middlewared.utils.account.faillock import FAIL_INTERVAL, MAX_FAILURE, UNLOCK_TIME


class PAMModule(enum.StrEnum):
    DENY = 'pam_deny.so'
    ENV = 'pam_env.so'
    KEYINIT = 'pam_keyinit.so'
    MKHOMEDIR = 'pam_mkhomedir.so'
    LIMITS = 'pam_limits.so'
    LOGINUID = 'pam_loginuid.so'
    MOTD = 'pam_motd.so'
    PERMIT = 'pam_permit.so'
    OATH = 'pam_oath.so'
    UNIX = 'pam_unix.so'
    SSS = 'pam_sss.so'
    TDB = 'pam_tdb.so'
    TTY_AUDIT = 'pam_tty_audit.so'
    WINBIND = 'pam_winbind.so'
    FAILLOCK = 'pam_faillock.so'


class PAMService(enum.StrEnum):
    ACCOUNT = 'account'
    AUTH = 'auth'
    PASSWORD = 'password'
    SESSION = 'session'


class PAMSimpleControl(enum.StrEnum):
    # Subset of the simple (historical) pam control values
    # See man(5) pam.conf

    # Equivalent to [success=ok new_authtok_reqd=ok ignore=ignore default=bad]
    REQUIRED = 'required'
    # Equivalent to [success=ok new_authtok_reqd=ok ignore=ignore default=die]
    REQUISITE = 'requisite'
    # Equivalent to [success=ok new_authtok_reqd=done ignore=ignore]
    SUFFICIENT = 'sufficient'
    # Equivalent to [success=ok new_authtok_reqd=ok ignore=ignore]
    OPTIONAL = 'optional'


class PAMResponse(enum.StrEnum):
    # Subset of possible control keys for pam line
    # See man(5) pam.conf and _pam_types.h from pam development libraries
    DEFAULT = 'default'
    SUCCESS = 'success'
    NEW_AUTHTOK_REQD = 'new_authtok_reqd'
    USER_UNKNOWN = 'user_unknown'


class PAMAction(enum.StrEnum):
    # Subset of possible actions for control keys in pam line
    IGNORE = 'ignore'
    BAD = 'bad'
    DIE = 'die'
    OK = 'ok'
    DONE = 'done'
    RESET = 'reset'


@dataclass(slots=True, frozen=True)
class PAMControl:
    response: PAMResponse
    action: PAMAction | int

    def as_conf(self):
        return f'{self.response}={self.action}'


@dataclass(slots=True, frozen=True)
class PAMLine:
    pam_service: PAMService
    pam_control: PAMSimpleControl | tuple[PAMControl]
    pam_module: PAMModule
    pam_module_args: tuple[str] | None = None

    def __dump_control(self):
        if isinstance(self.pam_control, PAMSimpleControl):
            return self.pam_control

        return f'[{" ".join(ctrl.as_conf() for ctrl in self.pam_control)}]'

    def as_conf(self):
        if self.pam_module_args is None:
            return '\t'.join([
                self.pam_service,
                self.__dump_control(),
                self.pam_module
            ])

        return '\t'.join([
            self.pam_service,
            self.__dump_control(),
            self.pam_module,
            ' '.join(self.pam_module_args)
        ])


@dataclass(slots=True, frozen=True)
class PAMConfLines:
    service: PAMService
    primary: tuple[PAMLine]
    secondary: tuple[PAMLine] | None = None


# Below this point are intialized PAM configuration objects for use in mako files

STANDALONE_ACCOUNT = PAMConfLines(
    service=PAMService.ACCOUNT,
    primary=(
        PAMLine(
            pam_service=PAMService.ACCOUNT,
            pam_control=(
                PAMControl(PAMResponse.SUCCESS, 1),
                PAMControl(PAMResponse.NEW_AUTHTOK_REQD, PAMAction.DONE),
                PAMControl(PAMResponse.DEFAULT, PAMAction.IGNORE)
            ),
            pam_module=PAMModule.UNIX
        ),
    )
)

AD_ACCOUNT = PAMConfLines(
    service=PAMService.ACCOUNT,
    primary=(
        PAMLine(
            pam_service=PAMService.ACCOUNT,
            pam_control=(
                PAMControl(PAMResponse.SUCCESS, 2),
                PAMControl(PAMResponse.NEW_AUTHTOK_REQD, PAMAction.DONE),
                PAMControl(PAMResponse.DEFAULT, PAMAction.IGNORE)
            ),
            pam_module=PAMModule.UNIX
        ),
        PAMLine(
            pam_service=PAMService.ACCOUNT,
            pam_control=(
                PAMControl(PAMResponse.SUCCESS, 1),
                PAMControl(PAMResponse.NEW_AUTHTOK_REQD, PAMAction.DONE),
                PAMControl(PAMResponse.DEFAULT, PAMAction.IGNORE)
            ),
            pam_module=PAMModule.WINBIND,
            pam_module_args=('krb5_auth', 'krb5_ccache_type=FILE')
        )
    )
)

SSS_ACCOUNT = PAMConfLines(
    service=PAMService.ACCOUNT,
    primary=(
        PAMLine(
            pam_service=PAMService.ACCOUNT,
            pam_control=(
                PAMControl(PAMResponse.SUCCESS, 1),
                PAMControl(PAMResponse.NEW_AUTHTOK_REQD, PAMAction.DONE),
                PAMControl(PAMResponse.DEFAULT, PAMAction.IGNORE)
            ),
            pam_module=PAMModule.UNIX
        ),
    ),
    secondary=(
        PAMLine(
            pam_service=PAMService.ACCOUNT,
            pam_control=(
                PAMControl(PAMResponse.SUCCESS, PAMAction.OK),
                PAMControl(PAMResponse.NEW_AUTHTOK_REQD, PAMAction.DONE),
                PAMControl(PAMResponse.USER_UNKNOWN, PAMAction.IGNORE),
                PAMControl(PAMResponse.DEFAULT, PAMAction.BAD)
            ),
            pam_module=PAMModule.SSS
        ),
    )
)

STANDALONE_AUTH = PAMConfLines(
    service=PAMService.AUTH,
    primary=(
        PAMLine(
            pam_service=PAMService.AUTH,
            pam_control=(
                PAMControl(PAMResponse.SUCCESS, 1),
                PAMControl(PAMResponse.DEFAULT, PAMAction.IGNORE)
            ),
            pam_module=PAMModule.UNIX
        ),
    ),
)

AD_AUTH = PAMConfLines(
    service=PAMService.AUTH,
    primary=(
        PAMLine(
            pam_service=PAMService.AUTH,
            pam_control=(
                PAMControl(PAMResponse.SUCCESS, 2),
                PAMControl(PAMResponse.DEFAULT, PAMAction.IGNORE)
            ),
            pam_module=PAMModule.UNIX
        ),
        PAMLine(
            pam_service=PAMService.AUTH,
            pam_control=(
                PAMControl(PAMResponse.SUCCESS, 1),
                PAMControl(PAMResponse.DEFAULT, PAMAction.IGNORE)
            ),
            pam_module=PAMModule.WINBIND,
            pam_module_args=('try_first_pass', 'try_authtok', 'krb5_auth')
        )
    )
)

SSS_AUTH = PAMConfLines(
    service=PAMService.AUTH,
    primary=(
        PAMLine(
            pam_service=PAMService.AUTH,
            pam_control=(
                PAMControl(PAMResponse.SUCCESS, 2),
                PAMControl(PAMResponse.DEFAULT, PAMAction.IGNORE)
            ),
            pam_module=PAMModule.UNIX
        ),
        PAMLine(
            pam_service=PAMService.AUTH,
            pam_control=(
                PAMControl(PAMResponse.SUCCESS, 1),
                PAMControl(PAMResponse.DEFAULT, PAMAction.IGNORE)
            ),
            pam_module=PAMModule.SSS,
            pam_module_args=('ignore_unknown_user', 'use_first_pass')
        )
    )
)

STANDALONE_SESSION = PAMConfLines(
    service=PAMService.SESSION,
    primary=(),
    secondary=(
        PAMLine(
            pam_service=PAMService.SESSION,
            pam_control=PAMSimpleControl.REQUIRED,
            pam_module=PAMModule.UNIX
        ),
        PAMLine(
            pam_service=PAMService.SESSION,
            pam_control=PAMSimpleControl.REQUIRED,
            pam_module=PAMModule.MKHOMEDIR
        )
    )
)

AD_SESSION = PAMConfLines(
    service=PAMService.SESSION,
    primary=(),
    secondary=(
        PAMLine(
            pam_service=PAMService.SESSION,
            pam_control=PAMSimpleControl.REQUIRED,
            pam_module=PAMModule.UNIX
        ),
        PAMLine(
            pam_service=PAMService.SESSION,
            pam_control=PAMSimpleControl.REQUIRED,
            pam_module=PAMModule.MKHOMEDIR
        ),
        PAMLine(
            pam_service=PAMService.SESSION,
            pam_control=PAMSimpleControl.OPTIONAL,
            pam_module=PAMModule.WINBIND,
            # We have pam_winbind handle mkhomedir because pam_mkhomedir
            # is erratic for automatic home directory creation for AD users.
            # This is simpler than fixing pam_mkhomedir.
            pam_module_args=('mkhomedir',)
        ),
    )
)

SSS_SESSION = PAMConfLines(
    service=PAMService.SESSION,
    primary=(),
    secondary=(
        PAMLine(
            pam_service=PAMService.SESSION,
            pam_control=PAMSimpleControl.REQUIRED,
            pam_module=PAMModule.UNIX
        ),
        PAMLine(
            pam_service=PAMService.SESSION,
            pam_control=PAMSimpleControl.OPTIONAL,
            pam_module=PAMModule.SSS,
        ),
        PAMLine(
            pam_service=PAMService.SESSION,
            pam_control=PAMSimpleControl.REQUIRED,
            pam_module=PAMModule.MKHOMEDIR
        )
    )
)


TTY_AUDIT_LINE = PAMLine(
    pam_service=PAMService.SESSION,
    pam_control=PAMSimpleControl.REQUIRED,
    pam_module=PAMModule.TTY_AUDIT,
    pam_module_args=('disable=*', 'enable=root')
)


FAILLOCK_AUTH_FAIL = PAMLine(
    pam_service=PAMService.AUTH,
    pam_control=(PAMControl(PAMResponse.DEFAULT, PAMAction.DIE),),
    pam_module=PAMModule.FAILLOCK,
    pam_module_args=(
        'authfail',
        f'deny={MAX_FAILURE}',
        f'unlock_time={UNLOCK_TIME}',
        f'fail_interval={FAIL_INTERVAL}',
    )
)


FAILLOCK_AUTH_SUCC = PAMLine(
    pam_service=PAMService.AUTH,
    pam_control=PAMSimpleControl.REQUIRED,
    pam_module=PAMModule.FAILLOCK,
    pam_module_args=(
        'authsucc',
        f'deny={MAX_FAILURE}',
        f'unlock_time={UNLOCK_TIME}',
        f'fail_interval={FAIL_INTERVAL}',
    )
)
