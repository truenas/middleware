import ctypes
import enum
import os
import pam
import threading
from dataclasses import dataclass
from datetime import datetime, UTC
from ipaddress import ip_address
from middlewared.utils.nss.nss_common import NssModule
from middlewared.utils.nss.grp import getgrgid
from middlewared.utils.nss.pwd import getpwnam
from middlewared.utils.origin import ConnectionOrigin
from middlewared.plugins.account_.constants import MIDDLEWARE_PAM_SERVICE, MIDDLEWARE_PAM_API_KEY_SERVICE
from pam.__internals import PamHandle, PamConv, conv_func, my_conv
from socket import AF_UNIX
from .utmp import login, logout, PyUtmpEntry, PyUtmpExit, PyUtmpType, UTMP_LOCK

MIDDLEWARE_HOST_PREFIX = 'tn-mw'
UTMP_MAX_SESSIONS = 10000

# utmp is basically treated as a key-value store based on the tn_line field. We
# populate it with, for instance, "wss/<id>", but the total buffer size for this
# string is small (32 bytes) this means that we'll keep a set of available ids
# and pop them off on login, and add back on logout. Using cryptographic method
# here would expose us to the birthday problem and possible collisions.
AVAILABLE_SESSION_IDS = set(range(1, UTMP_MAX_SESSIONS))


class TrueNASAuthenticatorStage(enum.StrEnum):
    AUTH = 'AUTH'
    OPEN_SESSION = 'OPEN_SESSION'
    CLOSE_SESSION = 'CLOSE_SESSION'
    LOGIN = 'LOGIN'
    LOGOUT = 'LOGOUT'


class MiddlewareTTYName(enum.StrEnum):
    """ Names for the ut_id and ut_line fields """
    WEBSOCKET = 'ws'
    WEBSOCKET_SECURE = 'wss'
    WEBSOCKET_UNIX = 'wsu'


@dataclass(frozen=True)
class TrueNASAuthenticatorResponse:
    stage: TrueNASAuthenticatorStage
    code: int  # PAM response code (pam.PAM_SUCCESS, pam.PAM_AUTH_ERR, etc)
    reason: str | None  # reason for non-success
    user_info: dict | None = None  # passwd dict (only populated on authenticate calls)


class TrueNAS_PamAuthenticator(pam.PamAuthenticator):
    """
    TrueNAS authenticator object. These are allocated per middleware session and hold an
    open pam handle with state information about the particular session. This includes the
    utmp entry generated for the authenticated user. Thread-safety for the individual PAM
    handle is ensured by using a threading lock on a per-authenticator basis (global mutex
    is not required). login and logoff methods provided by utmp.py are protected by a
    separate global threading lock.
    """
    truenas_service = None  # PAM service file used to authenticate may be 'middleware' or 'middleware-api-key'
    truenas_authenticated = False
    truenas_session_opened = False
    truenas_passwd = None
    truenas_utmp_entry = None
    truenas_login_at = None
    truenas_utmp_session_id = None
    TRUENAS_LOCK = threading.Lock()

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

        self.truenas_passwd = passwd | {
            'grouplist': tuple(grouplist),
            'local': passwd['source'] == NssModule.FILES.name,
        }

        # Swap out the NSS module name with strings middleware expects
        match passwd['source']:
            case NssModule.FILES.name:
                self.truenas_passwd['source'] = 'LOCAL'
            case NssModule.WINBIND.name:
                self.truenas_passwd['source'] = 'ACTIVEDIRECTORY'
            case NssModule.SSS.name:
                self.truenas_passwd['source'] = 'LDAP'

        return self.truenas_user_obj

    @property
    def truenas_user_obj(self):
        if self.truenas_passwd is None:
            raise ValueError('passwd entry not set')

        return self.truenas_passwd.copy()

    def authenticate(
        self,
        username: str,
        password: str,
        service: str = MIDDLEWARE_PAM_SERVICE
    ) -> TrueNASAuthenticatorResponse:
        stage = TrueNASAuthenticatorStage.AUTH
        if service not in (MIDDLEWARE_PAM_SERVICE, MIDDLEWARE_PAM_API_KEY_SERVICE):
            raise ValueError(f'{service}: not a supported PAM service')

        try:
            passwd_out = self._get_user_obj(username)
        except KeyError:
            return TrueNASAuthenticatorResponse(stage, pam.PAM_AUTH_ERR, f'{username}: user does not exist')

        with self.TRUENAS_LOCK:
            success = super().authenticate(username, password, service=os.path.basename(service), call_end=False)
            if success:
                self.truenas_service = service
                self.truenas_username = username
                # This normalizes the username and gets generic information
                code = pam.PAM_SUCCESS
                reason = None
                self.truenas_authenticated = True
            else:
                match self.code:
                    case pam.PAM_AUTH_ERR:
                        # pam_unix will fail with PAM_AUTH_ERR for expired passwords due to password aging
                        # If password is expired, convert to PAM_EXPIRED
                        if any([msg.startswith('Your account has expired') for msg in self.messages]):
                            code = pam.PAM_ACCT_EXPIRED
                            reason = 'Account expired due to aging rules'
                        else:
                            code = self.code
                            reason = self.reason
                    case _:
                        code = self.code
                        reason = self.reason

                # Authentication failure and so we should close our PAM handle
                self.end()

        return TrueNASAuthenticatorResponse(stage, code, reason, passwd_out)

    def open_session(self) -> TrueNASAuthenticatorResponse:
        if self.truenas_session_opened:
            raise RuntimeError('Session already opened')

        if not self.truenas_authenticated:
            raise RuntimeError('Not authenticated')

        with self.TRUENAS_LOCK:
            # In some situations we may have pam_limits enabled. The PAM module
            # interacts with the utmp file in pam_sm_open_session() and so we need
            # to acquire a global middleware lock on the utmp file before opening
            # the session
            with UTMP_LOCK:
                resp = super().open_session()

        if resp == pam.PAM_SUCCESS:
            self.truenas_session_opened = True

        reason = self.pam_strerror(self.handle, resp)
        return TrueNASAuthenticatorResponse(TrueNASAuthenticatorStage.OPEN_SESSION, resp, reason)

    def close_session(self) -> TrueNASAuthenticatorResponse:
        if not self.truenas_session_opened:
            raise RuntimeError('Session not opened')

        with self.TRUENAS_LOCK:
            resp = super().close_session()

        if resp == pam.PAM_SUCCESS:
            self.truenas_session_opened = False

        reason = self.pam_strerror(self.handle, resp)
        return TrueNASAuthenticatorResponse(TrueNASAuthenticatorStage.CLOSE_SESSION, resp, reason)

    def end(self) -> None:
        super().end()
        self.truenas_authenticated = False
        self.truenas_passwd = None
        self.truenas_login_at = None
        self.truenas_utmp_entry = None
        self.truenas_session_opened = False
        self.truenas_service = None

    def logout(self) -> TrueNASAuthenticatorResponse:
        if not self.truenas_utmp_entry:
            raise RuntimeError('Not logged in')

        # Close the open PAM session
        self.close_session()

        try:
            with self.TRUENAS_LOCK:
                logout(self.truenas_utmp_entry)
        except Exception as exc:
            code = pam.PAM_SYSTEM_ERR
            reason = str(exc)
        else:
            if self.truenas_utmp_session_id:
                self.truenas_utmp_session_id = None
                AVAILABLE_SESSION_IDS.add(self.truenas_utmp_session_id)

            code = pam.PAM_SUCCESS
            reason = None

        self.end()
        return TrueNASAuthenticatorResponse(TrueNASAuthenticatorStage.LOGOUT, code, reason)

    def login(self, middleware_session_id: str, origin: ConnectionOrigin) -> TrueNASAuthenticatorResponse:
        """ create utmp + wtmp entry and call pam_open_session() """
        if not self.truenas_authenticated:
            raise RuntimeError('Not authenticated')

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

            addr = ip_address(origin.rem_addr)
            ut_host = f'{MIDDLEWARE_HOST_PREFIX}.{middleware_session_id}.IP{origin.rem_addr}'

        utmp_sid = AVAILABLE_SESSION_IDS.pop()

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
            ut_id='',  # Yes, this should be an empty string. See comment aboveI
            ut_user=self.truenas_passwd['pw_name'][:31],
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
            self.truenas_utmp_entry = utmp_entry
            self.truenas_login_at = utmp_entry.ut_tv
            code = pam.PAM_SUCCESS
            reason = None
            self.truenas_utmp_session_id = utmp_sid

        return TrueNASAuthenticatorResponse(TrueNASAuthenticatorStage.LOGIN, code, reason)

    @property
    def login_at(self) -> datetime:
        return self.truenas_login_at

    def __del__(self):
        # Catchall to remove our utmp entry when we're garbage collected
        if self.truenas_utmp_entry:
            try:
                self.logout()
            except Exception:
                pass

        if self.truenas_utmp_session_id:
            AVAILABLE_SESSION_IDS.add(self.truenas_utmp_session_id)
            self.truenas_utmp_session_id = None


class TrueNAS_UnixPamAuthenticator(TrueNAS_PamAuthenticator):
    truenas_interactive_session = None

    def __authenticate_impl(self, username: str) -> TrueNASAuthenticatorResponse:
        @conv_func
        def __conv(n_messages, messages, p_response, app_data):
            pyob = ctypes.cast(app_data, ctypes.py_object).value

            msg_list = pyob.get('msgs')
            password = pyob.get('password')
            encoding = pyob.get('encoding')

            return my_conv(n_messages, messages, p_response, self.libc, msg_list, password, encoding)

        try:
            passwd = self._get_user_obj(username)
        except Exception:
            return TrueNASAuthenticatorResponse(
                TrueNASAuthenticatorStage.AUTH,
                pam.PAM_USER_UNKNOWN,
                f'{username}: User does not exist'
            )

        self.handle = PamHandle()
        app_data = {'msgs': self.messages, 'password': '', 'encoding': 'utf-8'}
        conv = PamConv(__conv, ctypes.c_void_p.from_buffer(ctypes.py_object(app_data)))
        retval = self.pam_start(
            MIDDLEWARE_PAM_SERVICE.encode(),
            username.encode(),
            ctypes.byref(conv),
            ctypes.byref(self.handle)
        )
        if retval != pam.PAM_SUCCESS:
            reason = self.pam_strerror(self.handle, retval)
            return TrueNASAuthenticatorResponse(TrueNASAuthenticatorStage.AUTH, retval, reason)

        # Verify that account not disabled / expired
        retval = self.pam_acct_mgmt(self.handle, 0)
        reason = None
        if retval != pam.PAM_SUCCESS:
            reason = self.pam_strerror(self.handle, retval)
        else:
            self.truenas_passwd = passwd

        return TrueNASAuthenticatorResponse(TrueNASAuthenticatorStage.AUTH, retval, reason, passwd)

    def authenticate(self, username: str) -> TrueNASAuthenticatorResponse:
        """
        Authentication for our unix socket is somewhat different. We just simply
        verify username exists and set up pam handle
        """
        with self.TRUENAS_LOCK:
            resp = self.__authenticate_impl(username)
            if resp.code == pam.PAM_SUCCESS:
                self.truenas_service = MIDDLEWARE_PAM_SERVICE
                self.truenas_username = self.truenas_passwd['pw_name']
                self.truenas_authenticated = True

        return resp

    def logout(self):
        """ If we have a non-interactive session then bypass normal logout. This is differentiated
        from an unitialized state where truenas_interactive_session is None. In latter case we want
        the logout to fail with exception that account was not logged in. """
        if self.truenas_interactive_session is False:
            return TrueNASAuthenticatorResponse(TrueNASAuthenticatorStage.LOGOUT, pam.PAM_SUCCESS, None)

        return super().logout()

    def login(self, middleware_session_id: str, origin: ConnectionOrigin) -> TrueNASAuthenticatorResponse:
        """ We need special handling for internal non-interactive middleware sessions """
        self.truenas_interactive_session = origin.session_is_interactive

        if not origin.session_is_interactive:
            # short-circuit login if this is a middleware worker or other backend job
            self.truenas_login_at = datetime.now(UTC)
            return TrueNASAuthenticatorResponse(TrueNASAuthenticatorStage.LOGIN, pam.PAM_SUCCESS, None)

        return super().login(middleware_session_id, origin)
