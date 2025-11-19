import enum
import os
import truenas_pyscram
from json import dumps
from uuid import UUID
from middlewared.plugins.account_.constants import ADMIN_UID
from middlewared.utils.auth import OTPW_MANAGER, OTPWResponseCode
from middlewared.utils.directoryservices.constants import DSType
from middlewared.utils.directoryservices.health import DSHealthObj
from middlewared.utils.nss.nss_common import NssModule
from middlewared.utils.nss.grp import getgrgid
from middlewared.utils.nss.pwd import getpwnam
from middlewared.utils.origin import ConnectionOrigin
from truenas_authenticator import UserPamAuthenticator as TrueNASUserPamAuthenticator
from truenas_authenticator import AuthenticatorStage as TrueNASAuthenticatorStage
from truenas_authenticator import AuthenticatorResponse as TrueNASAuthenticatorResponse
from truenas_pypam import MSGStyle, PAMCode, PAMError
from socket import AF_INET, AF_INET6, AF_UNIX
from .faillock import is_tally_locked


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


DEFAULT_LOGIN_SUCCESS = TrueNASAuthenticatorResponse(
    TrueNASAuthenticatorStage.LOGIN, PAMCode.PAM_SUCCESS, None
)

DEFAULT_LOGIN_FAIL = TrueNASAuthenticatorResponse(
    TrueNASAuthenticatorStage.LOGIN, PAMCode.PAM_SYSTEM_ERR, 'Unexpected Session Manager'
)

DEFAULT_LOGOUT_SUCCESS = TrueNASAuthenticatorResponse(
    TrueNASAuthenticatorStage.LOGOUT, PAMCode.PAM_SUCCESS, None
)

DEFAULT_LOGOUT_FAIL = TrueNASAuthenticatorResponse(
    TrueNASAuthenticatorStage.LOGOUT, PAMCode.PAM_SYSTEM_ERR, 'Unexpected Session Manager'
)


class UserPamAuthenticator(TrueNASUserPamAuthenticator):
    """ TrueNAS authenticator object. These are allocated per middleware session and hold an
    open pam handle with state information about the particular session. This includes the
    utmp entry generated for the authenticated user. """

    def _get_pam_session_info(self, origin: ConnectionOrigin) -> None:
        """ Set the connection origin and other middleware-session metadata into
        pam environmental variable `pam_truenas_session_data`. This will then be inserted
        into our sessions keyring that is used for tracking sessions in general. """

        if origin.family == AF_UNIX:
            session_data = {
                'origin_family': 'AF_UNIX',
                'origin': {
                    'pid': origin.pid,
                    'uid': origin.uid,
                    'gid': origin.gid,
                    'loginuid': origin.loginuid,
                    'sec': 'unconfined',
                },
                'extra': {
                    'secure_transport': origin.secure_transport
                }
            }
        elif origin.family == AF_INET or origin.family == AF_INET6:
            session_data = {
                'origin_family': 'AF_INET' if origin.family == AF_INET else 'AF_INET6',
                'origin': {
                    'loc_addr': str(origin.loc_addr),
                    'loc_port': origin.loc_port,
                    'rem_addr': str(origin.rem_addr),
                    'rem_port': origin.rem_port,
                    'ssl': origin.ssl
                },
                'extra': {
                    'secure_transport': origin.secure_transport
                }
            }

        return session_data

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

        self.passwd = passwd | {
            'grouplist': tuple(grouplist),
            'local': passwd['source'] == NssModule.FILES.name,
            'account_attributes': []
        }

        passwd = self.passwd

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

        if self.state.service == MiddlewarePamFile.API_KEY.service:
            passwd['account_attributes'].append(AccountFlag.API_KEY)

        # Compare normalized username from NSS with usernames in the /etc/users.oath file
        if self.twofactor_user:
            passwd['account_attributes'].append(AccountFlag.TWOFACTOR)

        if passwd['pw_uid'] in (0, ADMIN_UID):
            passwd['account_attributes'].append(AccountFlag.SYS_ADMIN)
            if not passwd['local']:
                raise ValueError("System administrator account is being provided by non-local source")

        # Retrieve via property getter to ensure we're returning a proper copy
        return self.truenas_user_obj

    def __init__(self, *, username: str, origin: ConnectionOrigin, service=MiddlewarePamFile.DEFAULT):
        # NOTE: we are limiting ourselves to non-blocking calls here because these objects are
        # created potentially in async co-routines. This means we input the username as sent by client.
        # We can later normalize when processing authentication requests.
        session_info = self._get_pam_session_info(origin)
        self._twofactor_user = False
        self._service = service

        super().__init__(
            username=username,
            service=service.service,
            rhost=str(origin),
            pam_env={'pam_truenas_session_data': dumps(session_info)}
        )
        self.otpw_possible = True
        self._session_uuid = None

    def login(self) -> TrueNASAuthenticatorResponse:
        resp = super().login()
        if resp.code == PAMCode.PAM_SUCCESS:
            # On successful session open, pam_truenas will set a pam environmental variable containing the
            # session_uuid it assigned the session in the user keyring.
            #
            # This will fail with FileNotFoundError if for some reason the environmental variable wasn't
            # properly set by the PAM module. This is a very unexpected error and so we are intentionally
            # not attempting to handle it here.
            try:
                uuid_str = self.ctx.get_env('pam_truenas_session_uuid')
                self._session_uuid = UUID(uuid_str)
            except Exception as exc:
                # PAM stack is misconfigured (pam_truenas possibly omitted). We don't
                # want to raise an exception here because it will make recovery impossible
                # because middleware auth will be broken.
                self.session_error = str(exc)

        return resp

    @property
    def session_uuid(self) -> UUID | None:
        return self._session_uuid

    @property
    def truenas_user_obj(self):
        """ Create a copy of the stored passwd dict for user. """
        if not getattr(self, 'passwd') or self.passwd is None:
            raise ValueError('passwd entry not set')

        out = self.passwd.copy()
        out['account_attributes'] = out['account_attributes'].copy()
        return out

    def __otpw_authenticate(self, password, passwd_entry):
        """ When autenticated uses may generate a single-use password for an account. If
        regular PAM auth fails for non-api-key case, we should check it against our single-use
        passwords. """
        if not self.otpw_possible:
            return

        otpw_resp = OTPW_MANAGER.authenticate(passwd_entry['pw_uid'], password)
        match otpw_resp.code:
            case OTPWResponseCode.SUCCESS:
                self.passwd['account_attributes'].append(AccountFlag.OTPW)
                # PASSWORD_CHANGE_REQUIRED can only be set for local accounts. We don't allow
                # password changes through middleware currently for directory services.
                if otpw_resp.data['password_set_override'] and passwd_entry['source'] == 'LOCAL':
                    self.passwd['account_attributes'].append(AccountFlag.PASSWORD_CHANGE_REQUIRED)

                code = PAMCode.PAM_SUCCESS
                reason = None
            case OTPWResponseCode.EXPIRED:
                code = PAMCode.PAM_CRED_EXPIRED
                reason = 'Onetime password is expired'
            case OTPWResponseCode.NO_KEY:
                # Indicate to caller to send original PAM response
                return
            case _:
                code = PAMCode.PAM_AUTH_ERR
                reason = f'Onetime password authentication failed: {otpw_resp.code}'

        return code, reason

    def pam_authenticate_simple(self, username: str, password: str) -> TrueNASAuthenticatorResponse:
        """ Simple version of authentication is user / password (with possibly request for 2FA token) """
        self.username = username  # ensure that PAM context is created with the provided username
        self._twofactor_user = False  # reset any old 2FA flag

        resp = self.auth_init()
        match resp.code:
            case PAMCode.PAM_SUCCESS:
                # Unix authentication will succeed immmediately
                return resp
            case PAMCode.PAM_CONV_AGAIN:
                # The service module has requested some information from the client
                # we'll handle exchange below
                pass
            case PAMCode.PAM_AUTHINFO_UNAVAIL:
                # This may be request for API key authentication for a revoked or expired key
                return resp
            case _:
                # Something very unexpected
                return resp

        while resp.code == PAMCode.PAM_CONV_AGAIN:
            if resp.reason:
                # Auto-respond to prompts based on username / password combination
                responses = []
                for msg in resp.reason:
                    if msg.msg_style == MSGStyle.PAM_PROMPT_ECHO_OFF:
                        # Check for pam_oath prompt
                        # pam_oath response here is a message with
                        # msg[0].msg_style == PAM_PROMPT_ECHO_OFF
                        # msg[0].msg = "One-time password (OATH) for `%s': "
                        if "(OATH)" in msg.msg:
                            # We return PAM_AUTH_AGAIN response to the middleware caller
                            # so that it in turn can pass a client message that second factor
                            # is required.
                            self._twofactor_in_progress = True
                            self._twofactor_user = True
                            resp.reason = msg.msg
                            return resp

                        responses.append(password)
                    elif msg.msg_style == MSGStyle.PAM_PROMPT_ECHO_ON:
                        responses.append(username)
                    else:
                        responses.append(None)

                resp = self.auth_continue(responses)
            else:
                # No messages, wait for next state
                resp = self.auth_continue([])

        return resp

    @property
    def twofactor_user(self):
        return self._twofactor_user

    def authenticate_oath(self, twofactor_token: str) -> TrueNASAuthenticatorResponse:
        stage = TrueNASAuthenticatorStage.AUTH

        if not self.twofactor_user:
            return TrueNASAuthenticatorResponse(stage, PAMCode.PAM_AUTH_ERR, 'User does not support two-factor auth')

        resp = self.auth_continue([twofactor_token])
        if resp.code == PAMCode.PAM_SUCCESS:
            # Grab fresh copy since account flags may have changed due to OTPW login
            pw = self.truenas_user_obj
            assert pw['pw_name'] == resp.user_info['pw_name']
            resp.user_info = pw

        return resp

    def authenticate(self, username: str, password: str) -> TrueNASAuthenticatorResponse:
        stage = TrueNASAuthenticatorStage.AUTH

        try:
            pw = self._get_user_obj(username)
        except KeyError:
            return TrueNASAuthenticatorResponse(stage, PAMCode.PAM_AUTH_ERR, f'{username}: user does not exist')

        code = None
        reason = None

        # Compare normalized username from NSS with usernames in the /etc/users.oath file
        if not os.path.exists(self._service):
            # Explicitly raise an exception if our service file doesn't exist. If we proceed
            # then PAM will fallback to using defaults. We want caller to catch this error and
            # regenerate pam configuraiton.
            raise FileNotFoundError(self._service)

        if self._service.service != self.state.service:
            raise RuntimeError(f'{self.state.service}: unexpected PAM service. Expected: {self._service.service}')

        # pass the normalized name to the PAM stack when authenticating
        resp = self.pam_authenticate_simple(pw['pw_name'], password)
        if resp.code != PAMCode.PAM_SUCCESS:
            if resp.code == PAMCode.PAM_AUTH_ERR and self.state.service == MiddlewarePamFile.DEFAULT.service:
                # This is possibly due to tally lock. In this case we'll change PAM code to reflect locked
                # status
                if is_tally_locked(pw['pw_name']):
                    resp.code = PAMCode.PAM_PERM_DENIED
                    resp.reason = 'Account is locked due to failed login attempts.'
                else:
                    otpw_resp = self.__otpw_authenticate(password, pw)
                    if otpw_resp:
                        code, reason = otpw_resp
                        if code == PAMCode.PAM_SUCCESS:
                            # swap out our pam service with UNIX to properly initialize
                            # underlying PAM context.
                            self.state.service = MiddlewarePamFile.UNIX.service
                            resp = self.pam_authenticate_simple(pw['pw_name'], '')
                            resp.user_info = pw
                        else:
                            resp.code = code
                            resp.reason = reason

        if resp.code == PAMCode.PAM_SUCCESS:
            # pam_acct_mgmt(3) determines whether the user's account is valid. This
            # includes things like account expiration and access restrictions. Failure
            # here is considered an overall authentication failure, exact PAM response
            # depends on the PAM modules implementing pam_sm_acct_mgmt().
            acct_resp = self.account_management()

            if acct_resp.code != PAMCode.PAM_SUCCESS:
                # pam_unix will fail with PAM_AUTH_ERR for expired passwords due to password aging
                # If password is expired, convert to PAM_EXPIRED
                resp.code = acct_resp.code
                resp.reason = acct_resp.reason
                if acct_resp.code == PAMCode.PAM_AUTH_ERR:
                    pam_messages = self.ctx.messages()
                    if pam_messages and any([m.msg.startswith('Your account has expired') for m in pam_messages[-1]]):
                        resp.code = PAMCode.PAM_ACCT_EXPIRED
                        resp.reason = 'Account expired due to aging rules'

        if resp.code == PAMCode.PAM_SUCCESS:
            # Grab fresh copy since account flags may have changed due to OTPW login
            pw = self.truenas_user_obj
            assert pw['pw_name'] == resp.user_info['pw_name']
            resp.user_info = pw

        return resp


class ApiKeyPamAuthenticator(UserPamAuthenticator):
    """ Authenticator for exchanges involving plain API key. SCRAM authentication with API
    is handled With ScramPamAuthenticator. """
    def __init__(self, *, username: str, origin: ConnectionOrigin):
        if not origin.is_tcp_ip_family:
            raise TypeError(f'{origin}: unexpected origin for ApiKeyPamAuthenticator')

        super().__init__(username=username, origin=origin, service=MiddlewarePamFile.API_KEY)
        self.otpw_possible = False

    def authenticate(self, username: str, password: str) -> TrueNASAuthenticatorResponse:
        """ Split up API key into DBID and actual key material then pass to backend """
        try:
            dbid, key = password.split('-', 1)
        except ValueError:
            # Not a valid API key, but let the backend do the erroring out
            return super().authenticate(username, password)

        self.dbid = dbid
        return super().authenticate(username, key)


class ScramPamAuthenticator(UserPamAuthenticator):
    def __init__(self, *, client_first_message: str, origin: ConnectionOrigin):
        try:
            self.client_first = truenas_pyscram.ClientFirstMessage(rfc_string=client_first_message)
        except Exception as exc:
            self.scram_error = exc
            return
        else:
            self.scram_error = None

        if not origin.is_tcp_ip_family:
            raise TypeError(f'{origin}: unexpected origin for ApiKeyPamAuthenticator')

        super().__init__(
            username=self.client_first.username, origin=origin, service=MiddlewarePamFile.API_KEY
        )
        self.sent_server_first = False
        self.sent_server_final = False
        self.otpw_possible = False
        self.dbid = self.client_first.api_key_id

    def authenticate(self, username: str, password: str):
        raise NotImplementedError("Plain authentication is not supported for SCRAM authentication")

    def handle_first_message(self) -> TrueNASAuthenticatorResponse:
        """ handle the ClientFirstMessage from the initialization and generate ServerFirstMessage. """
        stage = TrueNASAuthenticatorStage.AUTH

        if self.scram_error:
            # We had some sort of parsing error on the client-provided RFC string. We'll convert it
            # to a PAM response here
            return TrueNASAuthenticatorResponse(stage, PAMCode.PAM_AUTH_ERR, str(self.scram_error))

        if self.sent_server_first:
            raise RuntimeError('Already sent server first response')

        try:
            self._get_user_obj(self.username)
        except KeyError:
            return TrueNASAuthenticatorResponse(
                stage, PAMCode.PAM_AUTH_ERR, f'{self.username}: user does not exist'
            )

        resp = self.auth_init()
        if resp.code != PAMCode.PAM_CONV_AGAIN:
            return TrueNASAuthenticatorResponse(
                stage, PAMCode.PAM_AUTH_ERR,
                f'{resp.code}: unexpected response code. Expected [PAM_CONV_AGAIN]'
            )

        client_resp = []
        for msg in resp.reason:
            if msg.msg_style == MSGStyle.PAM_PROMPT_ECHO_OFF:
                if 'Send SCRAM ClientFirst message' not in msg.msg:
                    raise RuntimeError(f'{msg.msg}: unexpected PAM response')

                client_resp.append(str(self.client_first))
            elif msg.msg_style == MSGStyle.PAM_PROMPT_ECHO_ON:
                client_resp.append(self.username)
            else:
                raise RuntimeError(f'{msg}: unexpected PAM respones')

        # now time to get the ServerFirstResponse
        resp = self.auth_continue(client_resp)
        if resp.code != PAMCode.PAM_CONV_AGAIN:
            return TrueNASAuthenticatorResponse(
                stage, PAMCode.PAM_AUTH_ERR,
                f'{resp.code}: unexpected response code. Expected [PAM_CONV_AGAIN]'
            )

        if len(resp.reason) != 1:
            raise RuntimeError(f'{resp.reason}: unexpected PAM response')

        self.sent_server_first = True
        return TrueNASAuthenticatorResponse(stage, PAMCode.PAM_CONV_AGAIN, resp.reason[0].msg)

    def handle_final_message(self, rfc_string: str) -> TrueNASAuthenticatorResponse:
        stage = TrueNASAuthenticatorStage.AUTH
        if self.sent_server_final:
            raise RuntimeError('Already sent ServerFinalMessage')

        if not self.sent_server_first:
            raise RuntimeError('Did not send ServerFirstMessage')

        resp = self.auth_continue([rfc_string])
        if resp.code != PAMCode.PAM_CONV_AGAIN:
            return TrueNASAuthenticatorResponse(
                stage, PAMCode.PAM_AUTH_ERR,
                f'{resp.code}: unexpected response code. Expected [PAM_CONV_AGAIN]'
            )

        msg = resp.reason[0]
        if msg.msg_style != MSGStyle.PAM_TEXT_INFO:
            raise RuntimeError('{msg}: unexpected PAM message')

        passwd = self.truenas_user_obj
        if self.dbid:
            passwd['account_attributes'].append(AccountFlag.API_KEY)

        # send final message to close out the authentcation
        self.auth_continue([''])

        return TrueNASAuthenticatorResponse(
            stage=stage,
            code=PAMCode.PAM_SUCCESS,
            reason=msg.msg,
            user_info=passwd
        )


class InternalPamAuthenticator(UserPamAuthenticator):
    """ Authenticator for handling AF_UNIX connections, API token authentication, and HA connections. """
    def __init__(self, *, username: str, origin: ConnectionOrigin):
        super().__init__(username=username, origin=origin, service=MiddlewarePamFile.UNIX)
        self.otpw_possible = False

    def authenticate(self, username: str) -> TrueNASAuthenticatorResponse:
        """ Authentication for our unix socket is somewhat different. We just simply
        verify username exists and set up pam handle

        In TrueNAS 25.10 and earlier this would be optionally skipped in case of
        internal sessions. Performance with the new cpython extensions and PAM module design
        should be good enough to generate proper sessions for everything going through middleware. """
        return super().authenticate(username, '')


class UnixPamAuthenticator(InternalPamAuthenticator):
    def __init__(self, *, username: str, origin: ConnectionOrigin):
        if not origin.is_unix_family:
            raise TypeError(f'{origin}: unexpected origin for UnixPamAuthenticator')

        super().__init__(username=username, origin=origin)


class TokenPamAuthenticator(InternalPamAuthenticator):
    def __init__(self, *, username: str, origin: ConnectionOrigin):
        # Tokens have an unusual authenticator flow that's inside the TokenSessionManagerCredentials
        # object. So we'll initially set them up for a totally unprivileged user and then
        # rely on the subsequent authenticate call to handle the rest.
        super().__init__(username=username, origin=origin)
