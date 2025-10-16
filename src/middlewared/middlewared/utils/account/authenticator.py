# middlewared python pam authenticator
#
# WARNING:
# We have to reimplement much of python-pam correctly here because the upstream library
# defines the python function that is passed by reference as the pam_conv callback function
# within the scope of authenticate() call. This means any PAM module attempting to continue
# conversation outside of scope of authenticate() will trigger a NULL dereference and crash
# the middlewared process.

import ctypes
import enum
import os
import pam
import threading
from dataclasses import dataclass
from datetime import datetime, UTC
from ipaddress import ip_address
from middlewared.plugins.account_.constants import ADMIN_UID
from middlewared.utils.auth import OTPW_MANAGER, OTPWResponseCode
from middlewared.utils.directoryservices.constants import DSType
from middlewared.utils.directoryservices.health import DSHealthObj
from middlewared.utils.nss.nss_common import NssModule
from middlewared.utils.nss.grp import getgrgid
from middlewared.utils.nss.pwd import getpwnam
from middlewared.utils.origin import ConnectionOrigin
from pam.__internals import PamHandle, PamConv, conv_func, my_conv
from socket import AF_UNIX
from .faillock import is_tally_locked
from .oath import iter_oath_users
from .utmp import login, logout, PyUtmpEntry, PyUtmpExit, PyUtmpType, UTMP_LOCK, utmp_query

MIDDLEWARE_HOST_PREFIX = 'tn-mw'
UTMP_MAX_SESSIONS = 10000
libc = ctypes.CDLL('libc.so.6', use_errno=True)
try:
    PAM_REF = pam.pam()  # dlopen PAM libraries and define ctypes
except AttributeError:
    # The dlopen may fail when this file is imported into python script running
    # in squashfs filesystem during upgrades. We'll just initialize PAM_REF to None
    # here since the upgrade doesn't need to create authenticated middleware sessions
    PAM_REF = None


# utmp is basically treated as a key-value store based on the tn_line field. We
# populate it with, for instance, "wss/<id>", but the total buffer size for this
# string is small (32 bytes) this means that we'll keep a set of available ids
# and pop them off on login, and add back on logout. Using cryptographic method
# here would expose us to the birthday problem and possible collisions.
AVAILABLE_SESSION_IDS = set(range(1, UTMP_MAX_SESSIONS))


class MiddlewarePamFile(enum.StrEnum):
    DEFAULT = '/etc/pam.d/middleware'
    """ used for regular username / password authentication """
    API_KEY = '/etc/pam.d/middleware-api-key'
    """ used for authentication with API key """
    UNIX = '/etc/pam.d/middleware-unix'
    """ used for authentication via unix socket """
    COMMON_SESSION = '/etc/pam.d/middleware-session'
    """ session-related modules common to all middleware authenticators """

    @property
    def service(self):
        return os.path.basename(self.value)


class TrueNASAuthenticatorStage(enum.StrEnum):
    START = 'START'
    AUTH = 'AUTH'
    OPEN_SESSION = 'OPEN_SESSION'
    CLOSE_SESSION = 'CLOSE_SESSION'
    LOGIN = 'LOGIN'
    LOGOUT = 'LOGOUT'


class AccountFlag(enum.StrEnum):
    # Account-specific flags
    SYS_ADMIN = 'SYS_ADMIN'  # account is root or truenas_admin
    DIRECTORY_SERVICE = 'DIRECTORY_SERVICE'  # account is provided by a directory service
    LOCAL = 'LOCAL'  # account is provided by the passwd file (and hopefully in our config)
    ACTIVE_DIRECTORY = 'ACTIVE_DIRECTORY'  # account is provided by AD
    IPA = 'IPA'  # account is provided by FreeIPA
    LDAP = 'LDAP'  # account is provided by ordinary LDAP server

    # Flags about how authenticated
    TWOFACTOR = '2FA'  # Account requires 2FA (NOTE: PAM currently isn't evaluating second factor)
    API_KEY = 'API_KEY'  # Account authenticated by API key
    OTPW = 'OTPW'  # Account authenticated by a single-use password
    PASSWORD_CHANGE_REQUIRED = 'PASSWORD_CHANGE_REQUIRED'  # Password change for account is required


class MiddlewareTTYName(enum.StrEnum):
    """ Names for the ut_id and ut_line fields """
    WEBSOCKET = 'ws'
    WEBSOCKET_SECURE = 'wss'
    WEBSOCKET_UNIX = 'wsu'


@dataclass(slots=True)
class PamConvCallbackState:
    username: bytes
    password: bytes
    messages: list
    encoding: str = 'utf-8'


@dataclass(slots=True)
class TrueNASAuthenticatorState:
    service: MiddlewarePamFile = MiddlewarePamFile.DEFAULT
    """ pam service file path to be used for handle. This currently differentiates
    between API key authentication and regular username / password authentication.
    In future we can expand to also have a module that uses pam_oath for twofactor
    conversation."""
    stage: TrueNASAuthenticatorStage = TrueNASAuthenticatorStage.START
    """ Stage of PAM session / conversation. This is used to inform of next steps
    and validate whether method being called is valid. """
    otpw_possible: bool = True
    """ The authenticator supports authentication using single-use passwords. """
    twofactor_possible: bool = True
    """ The authenticator supports two-factor authentication """
    utmp_entry: PyUtmpEntry | None = None
    """ Utmp entry for the login. This is used to log out the account. """
    login_at: datetime | None = None
    """ Time at which session performed actual login """
    passwd: dict | None = None
    """ passwd dict entry for user """
    utmp_session_id: int | None = None
    """ The identifier for this particular conversation. It is popped from the
    AVAILABLE_SESSION_IDS set defined above, and re-added on deallocation. """
    libpam_state: PamConvCallbackState | None = None
    """ State passed into pam_conv(3) """
    origin: ConnectionOrigin | None = None
    """ Initialized ConnectionOrigin provided during authenticate() call """

    def __del__(self):
        if self.utmp_session_id:
            AVAILABLE_SESSION_IDS.add(self.utmp_session_id)
            self.utmp_session_id = None


@dataclass(frozen=True, slots=True)
class TrueNASAuthenticatorResponse:
    stage: TrueNASAuthenticatorStage
    code: int  # PAM response code (pam.PAM_SUCCESS, pam.PAM_AUTH_ERR, etc)
    reason: str | None  # reason for non-success
    user_info: dict | None = None  # passwd dict (only populated on authenticate calls)


DEFAULT_LOGIN_SUCCESS = TrueNASAuthenticatorResponse(
    TrueNASAuthenticatorStage.LOGIN, pam.PAM_SUCCESS, None
)

DEFAULT_LOGIN_FAIL = TrueNASAuthenticatorResponse(
    TrueNASAuthenticatorStage.LOGIN, pam.PAM_SYSTEM_ERR, 'Unexpected Session Manager'
)

DEFAULT_LOGOUT_SUCCESS = TrueNASAuthenticatorResponse(
    TrueNASAuthenticatorStage.LOGOUT, pam.PAM_SUCCESS, None
)

DEFAULT_LOGOUT_FAIL = TrueNASAuthenticatorResponse(
    TrueNASAuthenticatorStage.LOGOUT, pam.PAM_SYSTEM_ERR, 'Unexpected Session Manager'
)


@conv_func
def _conv(n_messages, messages, p_response, app_data):
    pyob = ctypes.cast(app_data, ctypes.py_object).value

    msg_list = pyob.messages
    password = pyob.password
    encoding = pyob.encoding

    return my_conv(n_messages, messages, p_response, libc, msg_list, password, encoding)


class UserPamAuthenticator(pam.PamAuthenticator):
    """
    TrueNAS authenticator object. These are allocated per middleware session and hold an
    open pam handle with state information about the particular session. This includes the
    utmp entry generated for the authenticated user. Thread-safety for the individual PAM
    handle is ensured by using a threading lock on a per-authenticator basis (global mutex
    is not required). login and logoff methods provided by utmp.py are protected by a
    separate global threading lock.
    """
    def __init__(self):
        # We intentionally don't super().init() here because we python-pam will
        # search for libraries every time the object is created. We just use references
        # to ctype functions that we looked up once
        self.truenas_state = TrueNASAuthenticatorState()
        self.TRUENAS_LOCK = threading.Lock()
        self.truenas_pam_conv = None  # reference to initialized pam_conv object
        self.libc = libc
        self.handle = None
        self.pam_start = PAM_REF.pam_start
        self.pam_acct_mgmt = PAM_REF.pam_acct_mgmt
        self.pam_set_item = PAM_REF.pam_set_item
        self.pam_setcred = PAM_REF.pam_setcred
        self.pam_strerror = PAM_REF.pam_strerror
        self.pam_authenticate = PAM_REF.pam_authenticate
        self.pam_open_session = PAM_REF.pam_open_session
        self.pam_close_session = PAM_REF.pam_close_session
        self.pam_putenv = PAM_REF.pam_putenv
        self.pam_misc_setenv = PAM_REF.pam_misc_setenv
        self.pam_getenv = PAM_REF.pam_getenv
        self.pam_getenvlist = PAM_REF.getenvlist

    def _get_user_obj(self, username):
        # populate our internal passwd reference. This should only be called once during authentication
        passwd = getpwnam(username, as_dict=True)
        grouplist = []
        for grp in os.getgrouplist(passwd['pw_name'], passwd['pw_gid']):
            try:
                if getgrgid(grp).source != passwd['source']:
                    # Enforce that users can't have groups from other providers
                    continue
            except Exception:
                # Possibly a TOCTOU issue. Play it safe and reject the group membership
                continue

            grouplist.append(grp)

        self.truenas_state.passwd = passwd | {
            'grouplist': tuple(grouplist),
            'local': passwd['source'] == NssModule.FILES.name,
            'account_attributes': []
        }
        passwd = self.truenas_state.passwd

        # Swap out the NSS module name with strings middleware expects and begin populating account flags
        match passwd['source']:
            case NssModule.FILES.name:
                passwd['source'] = 'LOCAL'
                passwd['account_attributes'] = [AccountFlag.LOCAL]
            case NssModule.WINBIND.name:
                passwd['source'] = 'ACTIVEDIRECTORY'
                passwd['account_attributes'] = [
                    AccountFlag.DIRECTORY_SERVICE, AccountFlag.ACTIVE_DIRECTORY
                ]
            case NssModule.SSS.name:
                passwd['source'] = 'LDAP'
                if DSHealthObj.dstype is DSType.IPA:
                    passwd['account_attributes'] = [AccountFlag.DIRECTORY_SERVICE, AccountFlag.IPA]
                else:
                    passwd['account_attributes'] = [AccountFlag.DIRECTORY_SERVICE, AccountFlag.LDAP]

        if self.truenas_state.service is MiddlewarePamFile.API_KEY:
            passwd['account_attributes'].append(AccountFlag.API_KEY)

        # Compare normalized username from NSS with usernames in the /etc/users.oath file
        elif self.truenas_state.twofactor_possible and any(user == passwd['pw_name'] for user in iter_oath_users()):
            passwd['account_attributes'].append(AccountFlag.TWOFACTOR)

        if passwd['pw_uid'] in (0, ADMIN_UID):
            passwd['account_attributes'].append(AccountFlag.SYS_ADMIN)
            if not passwd['local']:
                raise ValueError("System administrator account is being provided by non-local source")

        # Retrieve via property getter to ensure we're returning a proper copy
        return self.truenas_user_obj

    @property
    def truenas_user_obj(self):
        """ Create a copy of the stored passwd dict for user. """
        if self.truenas_state.passwd is None:
            raise ValueError('passwd entry not set')

        out = self.truenas_state.passwd.copy()
        out['account_attributes'] = out['account_attributes'].copy()
        return out

    def truenas_check_stage(self, expected: TrueNASAuthenticatorStage):
        if self.truenas_state.stage is not expected:
            raise RuntimeError(
                f'{self.truenas_state.stage}: unexpected authenticator run state. Expected: {expected}'
            )

    def start(self, username: str, password: str) -> TrueNASAuthenticatorResponse:
        """ This function assumes self.TRUENAS_LOCK held """
        self.truenas_check_stage(TrueNASAuthenticatorStage.START)

        self.handle = PamHandle()
        if len(username) == 0:
            raise ValueError('username is required')

        self.truenas_state.libpam_state = PamConvCallbackState(
            username=username.encode(),
            password=password.encode(),
            messages=[]
        )

        # Get pointer to the libpam state dataclass and recast to void for pam_conv(3)
        p_libpam_state = ctypes.c_void_p.from_buffer(ctypes.py_object(self.truenas_state.libpam_state))
        self.truenas_pam_conv = PamConv(_conv, p_libpam_state)
        reason = None
        retval = self.pam_start(
            self.truenas_state.service.encode(),
            username.encode(),
            ctypes.byref(self.truenas_pam_conv),
            ctypes.byref(self.handle)
        )
        if retval == pam.PAM_SUCCESS:
            origin = str(self.truenas_state.origin).encode()
            self.truenas_state.stage = TrueNASAuthenticatorStage.AUTH
            # pam_set_item(3) interally performs strdup on string and so we don't have
            # to worry about ctypes deallocating the string once it's outside of scope
            #
            # This sets the rhost internally in the pam handle to our ConnectionOrigin string.
            # The pam rhost appears as the source of authentication failures in pam_faillock tally
            # file and associated audit entries.
            self.pam_set_item(self.handle, pam.PAM_RHOST, ctypes.c_char_p(origin))
        else:
            reason = self.pam_strerror(self.handle, retval).encode()

        return TrueNASAuthenticatorResponse(TrueNASAuthenticatorStage.START, retval, reason)

    def _pam_start_account_no_password(self, username: str, do_acct_mgmt=True) -> TrueNASAuthenticatorResponse:
        """ This function assumes self.TRUENAS_LOCK held """
        try:
            passwd = self._get_user_obj(username)
        except KeyError:
            return TrueNASAuthenticatorResponse(
                TrueNASAuthenticatorStage.AUTH,
                pam.PAM_USER_UNKNOWN,
                f'{username}: User does not exist'
            )

        pam_resp = self.start(passwd['pw_name'], '')
        if pam_resp.code != pam.PAM_SUCCESS:
            return pam_resp

        # Verify that account not disabled / expired
        if do_acct_mgmt:
            retval = self.pam_acct_mgmt(self.handle, 0)
        else:
            # If someone user has managed to totally break the root account we don't want the
            # backend middleware processes to break
            retval = pam.PAM_SUCCESS

        reason = None
        if retval == pam.PAM_SUCCESS:
            self.truenas_state.passwd = passwd
            self.truenas_state.stage = TrueNASAuthenticatorStage.LOGIN
        else:
            reason = self.pam_strerror(self.handle, retval)

        return TrueNASAuthenticatorResponse(TrueNASAuthenticatorStage.AUTH, retval, reason, passwd)

    def __otpw_authenticate(self, password, passwd_entry):
        """ When autenticated uses may generate a single-use password for an account. If
        regular PAM auth fails for non-api-key case, we should check it against our single-use
        passwords. """
        if not self.truenas_state.otpw_possible:
            return

        otpw_resp = OTPW_MANAGER.authenticate(passwd_entry['pw_uid'], password)
        match otpw_resp.code:
            case OTPWResponseCode.SUCCESS:
                self.truenas_state.passwd['account_attributes'].append(AccountFlag.OTPW)
                # PASSWORD_CHANGE_REQUIRED can only be set for local accounts. We don't allow
                # password changes through middleware currently for directory services.
                if otpw_resp.data['password_set_override'] and passwd_entry['source'] == 'LOCAL':
                    self.truenas_state.passwd['account_attributes'].append(AccountFlag.PASSWORD_CHANGE_REQUIRED)

                code = pam.PAM_SUCCESS
                reason = None
            case OTPWResponseCode.EXPIRED:
                code = pam.PAM_CRED_EXPIRED
                reason = 'Onetime password is expired'
            case OTPWResponseCode.NO_KEY:
                # Indicate to caller to send original PAM response
                return
            case _:
                code = pam.PAM_AUTH_ERR
                reason = f'Onetime password authentication failed: {otpw_resp.code}'

        return code, reason

    def authenticate(
        self,
        username: str,
        password: str,
        origin: ConnectionOrigin,
    ) -> TrueNASAuthenticatorResponse:
        stage = TrueNASAuthenticatorStage.AUTH
        self.truenas_state.origin = origin

        try:
            pw = self._get_user_obj(username)
        except KeyError:
            return TrueNASAuthenticatorResponse(stage, pam.PAM_AUTH_ERR, f'{username}: user does not exist')

        code = None
        reason = None

        # Compare normalized username from NSS with usernames in the /etc/users.oath file
        if not os.path.exists(self.truenas_state.service):
            # Explicitly raise an exception if our service file doesn't exist. If we proceed
            # then PAM will fallback to using defaults. We want caller to catch this error and
            # regenerate pam configuraiton.
            raise FileNotFoundError(self.truenas_state.service)

        with self.TRUENAS_LOCK:
            # Authenticate using normalized name rather than user-provided name so that we ensure PAM_USER
            # is set consistently. In AD case bob@acme.internal and ACME\\Bob both resolve to ACME\\bob
            pam_resp = self.start(pw['pw_name'], password)
            if pam_resp.code != pam.PAM_SUCCESS:
                # failure to pam_start() is a auto-failure
                return pam_resp

            code = self.pam_authenticate(self.handle, 0)
            # pam_faillock changes pam_authenticate() responses to either PAM_SUCCESS or PAM_PERM_DENIED
            if code == pam.PAM_PERM_DENIED:
                # Convert to AUTH_ERR to normalize responses
                code = pam.PAM_AUTH_ERR

            if code != pam.PAM_SUCCESS:
                reason = self.pam_strerror(self.handle, code).decode()
                # pam_faillock changes pam_authenticate() responses to eihter PAM_SUCCESS or PAM_PERM_DENIED
                if code == pam.PAM_AUTH_ERR and self.truenas_state.service is MiddlewarePamFile.DEFAULT:
                    # This is possibly due to faillock. In this case we'll change PAM code to reflect locked
                    # status
                    if is_tally_locked(pw['pw_name']):
                        code = pam.PAM_PERM_DENIED
                        reason = 'Account is locked due to failed login attempts.'
                    else:
                        resp = self.__otpw_authenticate(password, pw)
                        if resp:
                            code, reason = resp

            if code == pam.PAM_SUCCESS:
                # pam_acct_mgmt(3) determines whether the user's account is valid. This
                # includes things like account expiration and access restrictions. Failure
                # here is considered an overall authentication failure, exact PAM response
                # depends on the PAM modules implementing pam_sm_acct_mgmt().
                code = self.pam_acct_mgmt(self.handle, 0)
                if code != pam.PAM_SUCCESS:
                    reason = self.pam_strerror(self.handle, code).decode()
                    match code:
                        case pam.PAM_AUTH_ERR:
                            # pam_unix will fail with PAM_AUTH_ERR for expired passwords due to password aging
                            # If password is expired, convert to PAM_EXPIRED
                            pam_messages = self.truenas_state.libpam_state.messages
                            if any([msg.startswith('Your account has expired') for msg in pam_messages]):
                                code = pam.PAM_ACCT_EXPIRED
                                reason = 'Account expired due to aging rules'

                        case _:
                            pass

            if code == pam.PAM_SUCCESS:
                self.truenas_state.stage = TrueNASAuthenticatorStage.LOGIN
                # Grab fresh copy since account flags may have changed due to OTPW login
                pw = self.truenas_user_obj
            else:
                # Authentication failure and so we should close our PAM handle
                self.end()

        return TrueNASAuthenticatorResponse(stage, code, reason, pw)

    def open_session(self) -> TrueNASAuthenticatorResponse:
        self.truenas_check_stage(TrueNASAuthenticatorStage.LOGIN)
        with self.TRUENAS_LOCK:
            # In some situations we may have pam_limits enabled. The PAM module
            # interacts with the utmp file in pam_sm_open_session() and so we need
            # to acquire a global middleware lock on the utmp file before opening
            # the session
            with UTMP_LOCK:
                resp = super().open_session()

        reason = self.pam_strerror(self.handle, resp).decode()
        return TrueNASAuthenticatorResponse(TrueNASAuthenticatorStage.OPEN_SESSION, resp, reason)

    def close_session(self) -> TrueNASAuthenticatorResponse:
        self.truenas_check_stage(TrueNASAuthenticatorStage.LOGOUT)
        with self.TRUENAS_LOCK:
            resp = super().close_session()

        reason = self.pam_strerror(self.handle, resp)
        return TrueNASAuthenticatorResponse(TrueNASAuthenticatorStage.CLOSE_SESSION, resp, reason)

    def end(self) -> None:
        super().end()
        # Clear state
        self.state = TrueNASAuthenticatorState()
        self.truenas_pam_conv = None

    def logout(self) -> TrueNASAuthenticatorResponse:
        self.truenas_check_stage(TrueNASAuthenticatorStage.LOGOUT)
        # Close the open PAM session
        self.close_session()

        try:
            with self.TRUENAS_LOCK:
                logout(self.truenas_state.utmp_entry)
        except Exception as exc:
            # In case of error session id will be recovered when object deallocated
            code = pam.PAM_SYSTEM_ERR
            reason = str(exc)
        else:
            # Immediately return the session id to the pool
            if self.truenas_state.utmp_session_id:
                AVAILABLE_SESSION_IDS.add(self.truenas_state.utmp_session_id)
                self.truenas_state.utmp_session_id = None

            code = pam.PAM_SUCCESS
            reason = None

        self.end()
        return TrueNASAuthenticatorResponse(TrueNASAuthenticatorStage.LOGOUT, code, reason)

    def __recover_ids(self):
        entries = utmp_query([['ut_type_str', '=', 'USER_PROCESS'], ['ut_line', '^', 'ws']])
        consumed_ids = set([int(entry['ut_line'].split('/')[1]) for entry in entries])
        AVAILABLE_SESSION_IDS.update(set(range(1, UTMP_MAX_SESSIONS)) - consumed_ids)

    def login(self, middleware_session_id: str) -> TrueNASAuthenticatorResponse:
        """ create utmp + wtmp entry and call pam_open_session() """
        self.truenas_check_stage(TrueNASAuthenticatorStage.LOGIN)
        origin = self.truenas_state.origin

        resp = self.open_session()
        if resp.code != pam.PAM_SUCCESS:
            self.end()
            return resp

        pid = os.getpid()
        if origin.family == AF_UNIX:
            ut_id = MiddlewareTTYName.WEBSOCKET_UNIX.value
            # Append PID to ut_host so that it's clearer which process is to blame
            ut_host = f'{MIDDLEWARE_HOST_PREFIX}.{middleware_session_id}.PID{origin.pid}'
            addr = ip_address('0.0.0.0')
        else:
            if origin.ssl:
                ut_id = MiddlewareTTYName.WEBSOCKET_SECURE.value
            else:
                ut_id = MiddlewareTTYName.WEBSOCKET.value

            if origin.rem_addr is None:
                raise ValueError(f'{str(origin)}: invalid remote address')

            addr = ip_address(origin.rem_addr)
            ut_host = f'{MIDDLEWARE_HOST_PREFIX}.{middleware_session_id}.IP{origin.rem_addr}'

        with self.TRUENAS_LOCK:
            with UTMP_LOCK:
                try:
                    utmp_sid = AVAILABLE_SESSION_IDS.pop()
                except KeyError:
                    # We possibly have a leak of session IDs (bug in the code somewhere). Attempt scavenging,
                    # but in a noisy way to caller.
                    self.__recover_ids()
                    # avoid extra checks for login state so that we can cleanly restart a pam_open_session call
                    super().close_session()
                    utmp_sid = None

        if utmp_sid is None:
            # Return to caller that we're dealing with an issue.
            return TrueNASAuthenticatorResponse(
                TrueNASAuthenticatorStage.LOGIN, pam.PAM_ABORT, 'Exhausted available session ids'
            )

        # Notes about utmp entry for login
        # ut_id and ut_line: ut_id should be an empty string. If it is set then pututline(3) will matched based on it
        # rather than ut_line
        #
        # Some applications (like proftpd) use the pid as component of ut_line in order to uniquely identify
        # separate logins
        utmp_entry = PyUtmpEntry(
            ut_type=PyUtmpType.USER_PROCESS,
            ut_pid=pid,
            ut_line=f'{ut_id}/{utmp_sid}',
            ut_id='',  # Yes, this should be an empty string. See comment above
            ut_user=self.truenas_state.passwd['pw_name'][:31],
            ut_host=ut_host,
            ut_exit=PyUtmpExit(0, 0),
            ut_tv=datetime.now(UTC),
            ut_session=os.getsid(pid),
            ut_addr=addr,
        )

        try:
            with self.TRUENAS_LOCK:
                login(utmp_entry)
        except Exception as exc:
            # clean up our pam handle
            self.end()
            code = pam.PAM_SYSTEM_ERR
            reason = str(exc)
            # We encountered an error inserting the utmp entry and
            # so we'll add it back to the pool
            AVAILABLE_SESSION_IDS.add(utmp_sid)
        else:
            self.truenas_state.utmp_entry = utmp_entry
            self.truenas_state.login_at = utmp_entry.ut_tv
            code = pam.PAM_SUCCESS
            reason = None
            self.truenas_state.utmp_session_id = utmp_sid
            self.truenas_state.stage = TrueNASAuthenticatorStage.LOGOUT

        return TrueNASAuthenticatorResponse(TrueNASAuthenticatorStage.LOGIN, code, reason)

    @property
    def login_at(self) -> datetime:
        return self.truenas_state.login_at

    def __del__(self):
        # Catchall to remove our utmp entry when we're garbage collected
        if self.truenas_state.stage is TrueNASAuthenticatorStage.LOGOUT:
            try:
                self.logout()
            except Exception:
                pass

        # decref our state object to trigger release of the utmp session id
        self.state = None


class ApiKeyPamAuthenticator(UserPamAuthenticator):
    def __init__(self):
        super().__init__()
        self.truenas_state = TrueNASAuthenticatorState(
            otpw_possible=False,
            twofactor_possible=False,
            service=MiddlewarePamFile.API_KEY
        )


class UnixPamAuthenticator(UserPamAuthenticator):
    def __init__(self):
        super().__init__()
        self.truenas_state = TrueNASAuthenticatorState(
            otpw_possible=False,
            twofactor_possible=False,
            service=MiddlewarePamFile.UNIX
        )

    def skip(self):
        """ return whether PAM operations and login should be skipped for this session """
        if not self.truenas_state.origin.session_is_interactive:
            # This is a middleware worker or backend job
            return True

        if self.truenas_state.origin.is_ha_connection:
            # This is an HA connection from other controller. We don't need utmp
            # entry for it (session still subject to normal middleware logging)
            return True

        return False

    def authenticate(self, username: str, origin: ConnectionOrigin) -> TrueNASAuthenticatorResponse:
        """
        Authentication for our unix socket is somewhat different. We just simply
        verify username exists and set up pam handle
        """
        self.truenas_state.origin = origin
        if self.skip():
            passwd = self._get_user_obj(username)
            return TrueNASAuthenticatorResponse(
                stage=TrueNASAuthenticatorStage.AUTH,
                code=pam.PAM_SUCCESS,
                reason=None,
                user_info=passwd
            )

        return super().authenticate(username, '', origin)

    def logout(self):
        """ If we have a non-interactive session then bypass normal logout. This is differentiated
        from an unitialized state where truenas_interactive_session is None. In latter case we want
        the logout to fail with exception that account was not logged in. """
        if self.skip():
            self.end()
            return TrueNASAuthenticatorResponse(TrueNASAuthenticatorStage.LOGOUT, pam.PAM_SUCCESS, None)

        return super().logout()

    def login(self, middleware_session_id: str) -> TrueNASAuthenticatorResponse:
        if self.skip():
            self.truenas_state.login_at = datetime.now(UTC)
            self.truenas_state.stage = TrueNASAuthenticatorStage.LOGOUT
            return TrueNASAuthenticatorResponse(TrueNASAuthenticatorStage.LOGIN, pam.PAM_SUCCESS, None)

        return super().login(middleware_session_id)
