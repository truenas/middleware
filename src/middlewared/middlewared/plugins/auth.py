from __future__ import annotations
import asyncio
import random
from datetime import timedelta
import errno
import time
from typing import TYPE_CHECKING

from middlewared.api import api_method, Event
from middlewared.api.base.server.ws_handler.rpc import RpcWebSocketAppEvent
from middlewared.api.current import (
    AuthLoginArgs, AuthLoginResult,
    AuthLoginWithApiKeyArgs, AuthLoginWithApiKeyResult,
    AuthLoginWithTokenArgs, AuthLoginWithTokenResult,
    AuthLoginExArgs, AuthLoginExResult,
    AuthLoginExContinueArgs, AuthLoginExContinueResult,
    AuthMeArgs, AuthMeResult,
    AuthMechanismChoicesArgs, AuthMechanismChoicesResult,
    AuthSessionsEntry,
    AuthGenerateTokenArgs, AuthGenerateTokenResult,
    AuthLogoutArgs, AuthLogoutResult,
    AuthSetAttributeArgs, AuthSetAttributeResult,
    AuthTerminateSessionArgs, AuthTerminateSessionResult,
    AuthTerminateOtherSessionsArgs, AuthTerminateOtherSessionsResult,
    AuthGenerateOnetimePasswordArgs, AuthGenerateOnetimePasswordResult,
    AuthSessionsAddedEvent, AuthSessionsRemovedEvent,
)
from middlewared.auth import (UserSessionManagerCredentials, UnixSocketSessionManagerCredentials,
                              ApiKeySessionManagerCredentials, LoginPasswordSessionManagerCredentials,
                              LoginTwofactorSessionManagerCredentials, AuthenticationContext,
                              TruenasNodeSessionManagerCredentials, TokenSessionManagerCredentials,
                              LoginOnetimePasswordSessionManagerCredentials, dump_credentials)
from middlewared.plugins.account_.constants import MIDDLEWARE_PAM_SERVICE, MIDDLEWARE_PAM_API_KEY_SERVICE
from middlewared.service import (
    Service, filterable_api_method, filter_list,
    pass_app, private, CallError,
)
from middlewared.service_exception import MatchNotFound, ValidationError, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.account.authenticator import (
    ApiKeyPamAuthenticator, UnixPamAuthenticator, TokenPamAuthenticator, UserPamAuthenticator, AccountFlag,
    ScramPamAuthenticator,
)
from middlewared.utils.auth import (
    aal_auth_mechanism_check, AuthMech, AuthResp, AuthenticatorAssuranceLevel, AA_LEVEL1,
    AA_LEVEL2, AA_LEVEL3, CURRENT_AAL, OTPW_MANAGER,
)
from middlewared.utils.crypto import generate_token
from middlewared.utils.time_utils import utc_now
from truenas_pypam import PAMCode

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.api.base.server.ws_handler.rpc import RpcWebSocketApp
    from middlewared.auth import SessionManagerCredentials
    from middlewared.main import Middleware
    from middlewared.utils.origin import ConnectionOrigin


PAM_SERVICES = {MIDDLEWARE_PAM_SERVICE, MIDDLEWARE_PAM_API_KEY_SERVICE}


class TokenManager:
    def __init__(self):
        self.tokens: dict[str, Token] = {}

    def create(
        self,
        ttl: int,
        attributes: dict,
        match_origin: ConnectionOrigin | None,
        parent_credentials: SessionManagerCredentials,
        session_id: str,
        single_use: bool,
    ) -> Token:
        credentials = parent_credentials
        if isinstance(credentials, TokenSessionManagerCredentials):
            if root_credentials := credentials.token.root_credentials():
                credentials = root_credentials

        token = generate_token(48, url_safe=True)
        self.tokens[token] = Token(self, token, ttl, attributes, match_origin, credentials, session_id, single_use)
        return self.tokens[token]

    def get(self, token: str, origin: ConnectionOrigin) -> Token | None:
        token_ = self.tokens.get(token)
        if token_ is None:
            return None

        if not token_.is_valid():
            self.tokens.pop(token_.token)
            return None

        if token_.match_origin:
            if not isinstance(origin, type(token_.match_origin)):
                return None
            if not token_.match_origin.match(origin):
                return None

        return token_

    def destroy(self, token: Token) -> None:
        self.tokens.pop(token.token, None)

    def destroy_by_session_id(self, session_id: str) -> None:
        self.tokens = {k: v for k, v in self.tokens.items() if session_id not in v.session_ids}


class Token:
    def __init__(
        self,
        manager: TokenManager,
        token: str,
        ttl: int,
        attributes: dict,
        match_origin: ConnectionOrigin | None,
        parent_credentials: SessionManagerCredentials,
        session_id: str,
        single_use: bool,
    ):
        self.manager = manager
        self.token = token
        self.ttl = ttl
        self.attributes = attributes
        self.match_origin = match_origin
        self.parent_credentials = parent_credentials
        self.session_ids = {session_id}
        self.single_use = single_use

        self.last_used_at = time.monotonic()

    def is_valid(self):
        return time.monotonic() < self.last_used_at + self.ttl

    def notify_used(self):
        self.last_used_at = time.monotonic()

    def root_credentials(self) -> SessionManagerCredentials | None:
        credentials = self.parent_credentials
        while True:
            if isinstance(credentials, TokenSessionManagerCredentials):
                credentials = credentials.token.parent_credentials
            elif credentials is None:
                return None
            else:
                return credentials


class SessionManager:
    def __init__(self):
        self.sessions: dict[str, Session] = {}
        self.middleware: Middleware

    async def login(self, app: RpcWebSocketApp, credentials: SessionManagerCredentials) -> None:
        if app.authenticated:
            await self.middleware.run_in_thread(credentials.login)
            self.sessions[app.session_id].credentials = credentials
            app.authenticated_credentials = credentials
            await self.middleware.log_audit_message(app, "AUTHENTICATION", {
                "credentials": dump_credentials(credentials),
                "error": None,
            }, True)
            return

        resp = await self.middleware.run_in_thread(credentials.login)
        if resp.code != PAMCode.PAM_SUCCESS:
            raise CallError(f'Login with credentials failed: {resp.reason}')

        session = Session(self, credentials, app)
        self.sessions[app.session_id] = session

        app.authenticated_credentials = credentials
        app.register_callback(RpcWebSocketAppEvent.MESSAGE, self._app_on_message)
        app.register_callback(RpcWebSocketAppEvent.CLOSE, self._app_on_close)

        if not is_internal_session(session):
            self.middleware.send_event("auth.sessions", "ADDED", fields=dict(id=app.session_id, **session.dump()))
            await self.middleware.log_audit_message(app, "AUTHENTICATION", {
                "credentials": dump_credentials(credentials),
                "error": None,
            }, True)

    async def logout(self, app: App) -> None:
        if session := self.sessions.get(app.session_id):
            if not (internal_session := is_internal_session(session)):
                await self.middleware.log_audit_message(app, "LOGOUT", {
                    "credentials": dump_credentials(app.authenticated_credentials),
                }, True)

            del self.sessions[app.session_id]
            app.authentication_context = None
            app.authenticated_credentials = None  # Must happen before awaiting

            await self.middleware.run_in_thread(session.credentials.logout)

            if not internal_session:
                self.middleware.send_event("auth.sessions", "REMOVED", fields=dict(id=app.session_id))
        else:
            app.authenticated_credentials = None

    async def _app_on_message(self, app: App, message) -> None:
        session = self.sessions.get(app.session_id)
        if session is None:
            app.authenticated_credentials = None
            return

        if not session.credentials.is_valid():
            await self.logout(app)
            return

        session.credentials.notify_used()

    async def _app_on_close(self, app: App) -> None:
        await self.logout(app)


class Session:
    def __init__(self, manager: SessionManager, credentials: SessionManagerCredentials, app: RpcWebSocketApp):
        self.manager = manager
        self.credentials = credentials
        self.app = app

        self.created_at = time.monotonic()

    def dump(self):
        return {
            "origin": str(self.app.origin),
            **dump_credentials(self.credentials),
            "created_at": utc_now() - timedelta(seconds=time.monotonic() - self.created_at),
            "secure_transport": self.app.origin.secure_transport,
        }


def is_internal_session(session: Session) -> bool:
    try:
        is_root_sock = session.app.origin.is_unix_family and session.app.origin.uid == 0
        if is_root_sock:
            return True
    except AttributeError:
        # session.app.origin can be NoneType
        pass

    if isinstance(session.app.authenticated_credentials, TruenasNodeSessionManagerCredentials):
        return True

    return False


class UserWebUIAttributeModel(sa.Model):
    __tablename__ = 'account_bsdusers_webui_attribute'

    id = sa.Column(sa.Integer(), primary_key=True)
    uid = sa.Column(sa.Integer(), unique=True)
    attributes = sa.Column(sa.JSON())


class AuthService(Service):

    class Config:
        cli_namespace = "auth"
        events = [
            Event(
                name='auth.sessions',
                description='Notification of new and removed sessions.',
                roles=['FULL_ADMIN'],
                models={
                    'ADDED': AuthSessionsAddedEvent,
                    'REMOVED': AuthSessionsRemovedEvent,
                }
            )
        ]

    session_manager = SessionManager()

    token_manager = TokenManager()

    def __init__(self, middleware: Middleware):
        super(AuthService, self).__init__(middleware)
        self.session_manager.middleware = middleware

    @filterable_api_method(item=AuthSessionsEntry, roles=['AUTH_SESSIONS_READ'], pass_app=True, pass_app_require=True)
    def sessions(self, app, filters, options):
        """
        Returns list of active auth sessions.

        Example of return value:

        [
            {
                "id": "NyhB1J5vjPjIV82yZ6caU12HLA1boDJcZNWuVQM4hQWuiyUWMGZTz2ElDp7Yk87d",
                "origin": "192.168.0.3:40392",
                "credentials": "LOGIN_PASSWORD",
                "credentials_data": {"username": "root"},
                "current": True,
                "internal": False,
                "created_at": {"$date": 1545842426070}
            }
        ]

        `credentials` can be `UNIX_SOCKET`, `ROOT_TCP_SOCKET`, `LOGIN_PASSWORD`, `API_KEY` or `TOKEN`,
        depending on what authentication method was used.
        For `UNIX_SOCKET` and `LOGIN_PASSWORD` logged-in `username` field will be provided in `credentials_data`.
        For `API_KEY` corresponding `api_key` will be provided in `credentials_data`.
        For `TOKEN` its `parent` credential will be provided in `credentials_data`.

        If you want to exclude all internal connections from the list, call this method with following arguments:

        [
            [
                ["internal", "=", True]
            ]
        ]
        """
        return filter_list(
            [
                dict(
                    id=session_id,
                    current=app.session_id == session_id,
                    internal=is_internal_session(session),
                    **session.dump()
                )
                for session_id, session in sorted(self.session_manager.sessions.items(),
                                                  key=lambda t: t[1].created_at)
            ],
            filters,
            options,
        )

    @api_method(AuthTerminateSessionArgs, AuthTerminateSessionResult, roles=['AUTH_SESSIONS_WRITE'])
    async def terminate_session(self, id_):
        """
        Terminates session `id`.
        """
        session = self.session_manager.sessions.get(id_)
        if session is None:
            return False

        self.token_manager.destroy_by_session_id(id_)

        await session.app.ws.close()
        return True

    @api_method(AuthTerminateOtherSessionsArgs, AuthTerminateOtherSessionsResult, roles=['AUTH_SESSIONS_WRITE'],
                pass_app=True)
    async def terminate_other_sessions(self, app):
        """
        Terminates all other sessions (except the current one).
        """
        errors = []
        for session_id, session in list(self.session_manager.sessions.items()):
            if session_id == app.session_id:
                continue

            if is_internal_session(session):
                continue

            try:
                await self.terminate_session(session_id)
            except Exception as e:
                errors.append(str(e))

        if errors:
            raise CallError("\n".join(["Unable to terminate all sessions:"] + errors))

        return True

    @api_method(
        AuthGenerateOnetimePasswordArgs, AuthGenerateOnetimePasswordResult,
        roles=['ACCOUNT_WRITE'],
        audit='Generate onetime password for user',
        pass_app=True,
        pass_app_require=True,
    )
    def generate_onetime_password(self, app, data):
        """
        Generate a password for the specified username that may be used only a single time to authenticate
        to TrueNAS. This may be used by server administrators to allow users authenticate and then set
        a proper password and two-factor authentication token.
        """
        if app.authenticated_credentials.is_user_session:
            account_admin = app.authenticated_credentials.has_role('ACCOUNT_WRITE')
        else:
            # credentials that aren't associated with user sessions are root-equivalent
            account_admin = True

        username = data['username']
        user_data = self.middleware.call_sync('user.query', [['username', '=', username]])
        if not user_data:
            raise ValidationError('auth.generate_onetime_password.username', f'{username}: user does not exist.')

        verrors = ValidationErrors()

        if user_data[0]['password_disabled']:
            verrors.add(
                'auth.generate_onetime_password.username',
                f'{username}: password authentication is disabled for account.'
            )

        if user_data[0]['locked']:
            verrors.add(
                'auth.generate_onetime_password.username',
                f'{username}: account is locked.'
            )

        verrors.check()

        return OTPW_MANAGER.generate_for_uid(user_data[0]['uid'], account_admin)

    @api_method(
        AuthGenerateTokenArgs, AuthGenerateTokenResult,
        audit='Generate authentication token for session',
        authorization_required=False,
        pass_app=True,
    )
    def generate_token(self, app, ttl, attrs, match_origin, single_use):
        """
        Generate a token to be used for authentication.

        `ttl` stands for Time To Live, in seconds. The token will be invalidated if the connection
        has been inactive for a time greater than this.

        `attrs` is a general purpose object/dictionary to hold information about the token.

        `match_origin` will only allow using this token from the same IP address or with the same user UID.

        NOTE: this endpoint is not supported when server security requires replay-resistant
        authentication as part of GPOS STIG requirements.
        """
        if not single_use and CURRENT_AAL.level != AA_LEVEL1:
            raise CallError(
                'Multi-use authentication tokens are not supported at current authenticator level.',
                errno.EOPNOTSUPP
            )

        if app and not app.authenticated_credentials.may_create_auth_token:
            raise CallError(
                f'{app.authenticated_credentials.class_name()}: the current session type does '
                'not support creation of authentication tokens.',
                errno.EOPNOTSUPP
            )

        if ttl is None:
            ttl = 600

        # FIXME: we need to properly define attrs in the schema
        if (job_id := attrs.get('job')) is not None:
            job = self.middleware.jobs.get(job_id)
            if not job:
                raise CallError(f'{job_id}: job does not exist.')

            if error := job.credential_access_error(app.authenticated_credentials, None):
                raise CallError(f'{job_id}: {error}')

            if job.pipes.output is None:
                raise CallError(f'{job_id}: job is not suitable for download token')

        token = self.token_manager.create(
            ttl,
            attrs,
            app.origin if match_origin else None,
            app.authenticated_credentials,
            app.session_id,
            single_use
        )

        return token.token

    @private
    def get_token(self, token_id, origin):
        if (token := self.token_manager.get(token_id, origin)) is None:
            return None

        if token.single_use:
            self.token_manager.destroy(token)
        else:
            if CURRENT_AAL.level != AA_LEVEL1:
                raise CallError('Multi-use API tokens are not supported '
                                'at the current security level',
                                errno.EOPNOTSUPP)

        return {
            'attributes': token.attributes,
        }

    @private
    @pass_app(require=True)
    def get_token_for_action(self, app, token_id, origin, method, resource) -> TokenSessionManagerCredentials | None:
        if (token := self.token_manager.get(token_id, origin)) is None:
            return None

        if token.attributes:
            return None

        if not token.parent_credentials.authorize(method, resource):
            return None

        auth_ctx = app.authentication_context

        if not auth_ctx:
            raise CallError('Authentication context was not initialized')

        if auth_ctx.pam_hdl:
            raise CallError(f'{auth_ctx.pam_hdl}: Unexpected existing authenticator')

        cred = token.root_credentials()
        if cred.is_user_session:
            username = cred.dump()['username']
        else:
            username = 'root'

        auth_ctx.pam_hdl = TokenPamAuthenticator(username=username, origin=origin)
        if token.single_use:
            self.token_manager.destroy(token)
        else:
            if CURRENT_AAL.level != AA_LEVEL1:
                raise CallError('Multi-use API tokens are not supported '
                                'at the current security level',
                                errno.EOPNOTSUPP)

        # We re-do the PAM authentication here to ensure that account is stil valid
        cred = TokenSessionManagerCredentials(self.token_manager, token, auth_ctx.pam_hdl)
        pam_resp = cred.pam_authenticate()
        if pam_resp.code != PAMCode.PAM_SUCCESS:
            raise CallError(f'Failed to get token for action: {pam_resp.reason}')

        return cred

    @private
    def get_token_for_shell_application(self, token_id, origin):
        if (token := self.token_manager.get(token_id, origin)) is None:
            return None

        if token.attributes:
            return None

        root_credentials = token.root_credentials()
        if not isinstance(root_credentials, UserSessionManagerCredentials):
            return None

        if not root_credentials.user['privilege']['web_shell']:
            return None

        if token.single_use:
            self.token_manager.destroy(token)

        return {
            'username': root_credentials.user['username'],
        }

    @api_method(AuthLoginArgs, AuthLoginResult, cli_private=True, authentication_required=False, pass_app=True)
    async def login(self, app, username, password, otp_token):
        """
        Authenticate session using username and password.
        `otp_token` must be specified if two factor authentication is enabled.
        """

        resp = await self.login_ex(app, {
            'mechanism': AuthMech.PASSWORD_PLAIN,
            'username': username,
            'password': password,
            'login_options': {'user_info': False},
        })

        match resp['response_type']:
            case AuthResp.SUCCESS:
                return True
            case AuthResp.OTP_REQUIRED:
                if otp_token is None:
                    return False

                otp_resp = await self.login_ex(app, {
                    'mechanism': AuthMech.OTP_TOKEN.name,
                    'otp_token': otp_token
                })
                return otp_resp['response_type'] == AuthResp.SUCCESS
            case _:
                return False

    @private
    async def set_authenticator_assurance_level(self, level: str):
        """
        See NIST SP 800-63B Section 4:
        https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-63b.pdf
        """
        self.logger.warning('Setting AAL to %s', level)
        match level:
            case 'LEVEL_1':
                level = AA_LEVEL1
            case 'LEVEL_2':
                level = AA_LEVEL2
            case 'LEVEL_3':
                level = AA_LEVEL3
            case _:
                raise CallError(f'{level}: unknown authenticator assurance level')

        CURRENT_AAL.level = level

    @private
    async def get_authenticator_assurance_level(self):
        """
        See NIST SP 800-63B Section 4:
        https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-63b.pdf

        And descriptions in middlewared/utils/auth.py
        """
        if CURRENT_AAL.level is AA_LEVEL1:
            return 'LEVEL_1'
        elif CURRENT_AAL.level is AA_LEVEL2:
            return 'LEVEL_2'
        elif CURRENT_AAL.level is AA_LEVEL3:
            return 'LEVEL_3'

        raise CallError(f'{CURRENT_AAL.level}: unknown authenticator assurance level')

    @private
    async def check_auth_mechanism(
        self,
        app,
        mechanism: AuthMech,
        auth_ctx: AuthenticationContext,
        level: AuthenticatorAssuranceLevel
    ) -> None:

        # The current session may be in the middle of a challenge-response conversation
        # and so we need to validate that what we received from client was expected
        # next message.
        if auth_ctx.next_mech and mechanism is not auth_ctx.next_mech:
            expected = auth_ctx.auth_data['user']['username']
            self.logger.debug('%s: received auth mechanism for user %s while expecting next auth mechanism: %s',
                              mechanism, expected, auth_ctx.next_mech)

            expected = auth_ctx.auth_data['user']['username']
            if auth_ctx.next_mech is AuthMech.OTP_TOKEN:
                errmsg = (
                    'Abandoning login attempt after being presented wtih '
                    'requirement for second factor for authentication.'
                )

                await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                    'credentials': {
                        'credentials': 'LOGIN_TWOFACTOR',
                        'credentials_data': {
                            'username': expected,
                        },
                    },
                    'error': errmsg
                }, False)

            # Discard in-progress auth attempt
            auth_ctx.next_mech = None
            auth_ctx.auth_data = None

        # OTP tokens are only permitted when prompted
        if auth_ctx.next_mech is None and mechanism == AuthMech.OTP_TOKEN.name:
            raise CallError(f'{mechanism}: no authentication in progress', errno.EINVAL)

        # Verify that auth mechanism is permitted under authenticator assurance level
        if not aal_auth_mechanism_check(mechanism, level):
            # Per NIST SP 800-63B only permitted authenticator types may be used
            raise CallError(
                f'{mechanism}: mechanism is not supported at current authenticator level.',
                errno.EOPNOTSUPP
            )

    @api_method(AuthMechanismChoicesArgs, AuthMechanismChoicesResult, authentication_required=False, pass_app=True)
    async def mechanism_choices(self, app) -> list:
        """ Get list of available authentication mechanisms available for auth.login_ex """
        aal = CURRENT_AAL.level
        cred_allows_token = True

        # The currently authenticated credential may actually restrict whether it can
        # generate authentication tokens. This is used by UI as a hint that it shouldn't
        # try to generate tokens for this user.
        if app and not app.authenticated_credentials.may_create_auth_token:
            cred_allows_token = False

        choices = [mech.name for mech in aal.mechanisms]
        if not cred_allows_token and AuthMech.TOKEN_PLAIN in choices:
            choices.remove(AuthMech.TOKEN_PLAIN.value)

        return choices

    @api_method(AuthLoginExContinueArgs, AuthLoginExContinueResult, cli_private=True, authentication_required=False,
                pass_app=True)
    async def login_ex_continue(self, app, data):
        """
        Continue in-progress authentication attempt. This endpoint should be
        called to continue an auth.login_ex attempt that returned OTP_REQUIRED.

        This is a convenience wrapper around auth.login_ex for API consumers.

        params:
            mechanism: the mechanism by which to continue authentication.
            Currently the only supported mechanism here is OTP_TOKEN.

            OTP_TOKEN
            otp_token: one-time password token. This is only permitted if
            a previous auth.login_ex call responded with "OTP_REQUIRED".

        returns:
            JSON object containing the following keys:

            `response_type` - will be one of the following:
            SUCCESS - continued auth was required

            OTP_REQUIRED - otp token was rejected. API consumer may call this
            endpoint again with correct OTP token.

            AUTH_ERR - invalid OTP token submitted too many times.
        """
        return await self.login_ex(app, data)

    @api_method(AuthLoginExArgs, AuthLoginExResult, cli_private=True, authentication_required=False, pass_app=True)
    async def login_ex(self, app, data):
        """
        Authenticate using one of a variety of mechanisms

        NOTE: mechanisms with a _PLAIN suffix indicate that they involve
        passing plain-text passwords or password-equivalent strings and
        should not be used on untrusted / insecure transport. Available
        mechanisms will be expanded in future releases.

        params:
            This takes a single argument consistning of a JSON object with the
            following keys:

            mechanism: the mechanism by which to authenticate to the backend
            the exact parameters to use vary by mechanism and are described
            below

            PASSWORD_PLAIN
            username: username with which to authenticate
            password: password with which to authenticate
            login_options: dictionary with additional authentication options

            API_KEY_PLAIN
            username: username with which to authenticate
            api_key: API key string
            login_options: dictionary with additional authentication options

            AUTH_TOKEN_PLAIN
            token: authentication token string
            login_options: dictionary with additional authentication options

            OTP_TOKEN
            otp_token: one-time password token. This is only permitted if
            a previous auth.login_ex call responded with "OTP_REQUIRED".

            login_options
            user_info: boolean - include auth.me output in successful responses.

        raises:
            CallError: a middleware CallError may be raised in the following
                circumstances.

            * An multistep challenge-response authentication mechanism is being
              used and the specified `mechanism` does not match the expected
              next step for authentication. In this case the errno will be set
              to EBUSY.

            * OTP_TOKEN mechanism was passed without an explicit request from
              a previous authentication step. In this case the errno will be set
              to EINVAL.

            * Current authenticator assurance level prohibits the use of the
              specified authentication mechanism. In this case the errno will be
              set to EOPNOTSUPP.

        returns:
            JSON object containing the following keys:

            response_type: string indicating the results of the current authentication
                mechanism. This is used to inform client of nature of authentication
                error or whether further action will be required in order to complete
                authentication.

            <additional keys per response_type>

        Notes about response types:

        SUCCESS:
        additional key:
            user_info: includes auth.me output for the resulting authenticated
            credentials.

        OTP_REQUIRED
        additional key:
            username: normalized username of user who must provide an OTP token.

        AUTH_ERR
        Generic authentication error corresponds to PAM_AUTH_ERR and PAM_USER_UNKOWN
        from libpam. This may be returned if the account does not exist or if the
        credential is incorrect.

        EXPIRED
        The specified credential is expired and not suitable for authentication.

        REDIRECT
        Authentication must be performed on different server.
        """
        if await self.middleware.call('failover.licensed'):
            if await self.middleware.call('failover.status') == 'BACKUP':
                try:
                    rem_status = await self.middleware.call(
                        'failover.call_remote', 'failover.status', [], {'connect_timeout': 2}
                    )
                    if rem_status == 'MASTER':
                        return {
                            'response_type': AuthResp.REDIRECT,
                            'urls': await self.middleware.call(
                                'failover.call_remote', 'failover.get_ips'),
                        }
                except Exception:
                    self.logger.exception('Unhandled exception checking remote system')

            # NOTE: It's okay to fall through here on HA systems. If the creds are
            # correct then the caller can check the various failover endpoints to check
            # the overall HA status. Without falling through here, a user won't be able
            # to login via our API on an HA system. This puts the responsibiility of
            # the end-user (in this example, it's the local UI) on whether to show the
            # web page contents.

        mechanism = AuthMech[data['mechanism']]
        if app.authentication_context is None:
            app.authentication_context = AuthenticationContext()

        auth_ctx = app.authentication_context
        login_fn = self.session_manager.login
        cred = None
        response = {'response_type': AuthResp.AUTH_ERR}

        await self.check_auth_mechanism(app, mechanism, auth_ctx, CURRENT_AAL.level)

        match mechanism:
            case AuthMech.PASSWORD_PLAIN:
                # Both of these mechanisms are de-factor username + password
                # combinations and pass through libpam.
                cred_type = 'LOGIN_PASSWORD'
                auth_ctx.pam_hdl = UserPamAuthenticator(username=data['username'], origin=app.origin)
                resp = await self.get_login_user(
                    app,
                    data['username'],
                    data['password'],
                )

                if resp['otp_required']:
                    # A one-time password is required for this user account and so
                    # we should request it from API client.
                    auth_ctx.next_mech = AuthMech.OTP_TOKEN
                    return {
                        'response_type': AuthResp.OTP_REQUIRED,
                        'username': data['username']
                    }
                elif resp['otpw_used']:
                    cred_type = 'ONETIME_PASSWORD'
                elif CURRENT_AAL.level.otp_mandatory:
                    # If we're here it means either:
                    #
                    # 1) correct username and password, but 2FA isn't enabled for user
                    # or
                    # 2) bad username or password
                    #
                    # We must not include information in response to indicate which case
                    # the situation is because it would divulge privileged information about
                    # the account to an unauthenticated user.
                    if resp['pam_response'] == 'SUCCESS':
                        # Insert a failure delay so that we don't leak information about
                        # the PAM response
                        await asyncio.sleep(CURRENT_AAL.get_delay_interval())
                        await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                            'credentials': {
                                'credentials': cred_type,
                                'credentials_data': {'username': data['username']},
                            },
                            'error': 'User does not have two factor authentication enabled.'
                        }, False)

                    else:
                        await asyncio.sleep(CURRENT_AAL.get_delay_interval())
                        await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                            'credentials': {
                                'credentials': cred_type,
                                'credentials_data': {'username': data['username']},
                            },
                            'error': 'Bad username or password'
                        }, False)

                    return response

                match resp['pam_response']['code']:
                    case PAMCode.PAM_SUCCESS:
                        if cred_type == 'ONETIME_PASSWORD':
                            cred = LoginOnetimePasswordSessionManagerCredentials(
                                resp['user_data'],
                                CURRENT_AAL.level,
                                auth_ctx.pam_hdl
                            )
                        else:
                            cred = LoginPasswordSessionManagerCredentials(
                                resp['user_data'],
                                CURRENT_AAL.level,
                                auth_ctx.pam_hdl
                            )

                        await login_fn(app, cred)
                    case PAMCode.PAM_AUTH_ERR:
                        await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                            'credentials': {
                                'credentials': cred_type,
                                'credentials_data': {'username': data['username']},
                            },
                            'error': 'Bad username or password'
                        }, False)
                    case _:
                        await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                            'credentials': {
                                'credentials': cred_type,
                                'credentials_data': {'username': data['username']},
                            },
                            'error': resp['pam_response']['reason'] or resp['pam_response']['otpw_response']
                        }, False)

            case AuthMech.API_KEY_PLAIN:
                # API key that we receive over wire is concatenation of the
                # datastore `id` of the particular key with the key itself,
                # delimited by a dash. <id>-<key>.
                auth_ctx.pam_hdl = ApiKeyPamAuthenticator(username=data['username'], origin=app.origin)
                resp = await self.get_login_user(
                    app,
                    data['username'],
                    data['api_key'],
                )

                # Retrieve the API key here so that we can upgrade the underlying
                # hash type and iterations if needed (since we have plain-text).
                # We also need the key info so that we can generate a useful
                # audit entry in case of failure.
                try:
                    key_id = int(data['api_key'].split('-')[0])
                    key = await self.middleware.call(
                        'api_key.query', [['id', '=', key_id]],
                        {'get': True, 'select': ['id', 'name', 'expires_at', 'revoked']}
                    )
                except Exception:
                    key = None

                if key and resp['pam_response']['code'] == PAMCode.PAM_AUTHINFO_UNAVAIL:
                    # Key may be expired or revoked. In both of these cases we won't
                    # have a key in the user's keyring. There's no way to differentiate
                    # at PAM level because both fail with ENOKEY.
                    if key['expires_at']:
                        resp['pam_response']['reason'] = 'Api key is expired.'
                        resp['pam_response']['code'] = PAMCode.PAM_CRED_EXPIRED
                    elif key['revoked']:
                        resp['pam_response']['reason'] = 'Api key is revoked.'
                    else:
                        self.logger.warning('%s: unexpected PAM_AUTHINFO_UNAVAIL response '
                                            'for API key. Forcibly regenerating API keys.',
                                            key['name'])
                        await self.middleware.call('etc.generate', 'pam_middleware')

                if resp['pam_response']['code'] == PAMCode.PAM_SUCCESS:
                    if not app.origin.secure_transport:
                        # Per NEP if plain API key auth occurs over insecure transport
                        # the key should be automatically revoked.
                        await self.middleware.call(
                            'api_key.revoke',
                            key_id,
                            'Attempt to use over an insecure transport',
                        )
                        await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                            'credentials': {
                                'credentials': 'API_KEY',
                                'credentials_data': {'username': data['username']},
                            },
                            'error': 'API key revoked due to insecure transport.'
                        }, False)

                        response['response_type'] = AuthResp.EXPIRED.name
                        # Revoke the pam handle and clean it up
                        auth_ctx.pam_hdl.end()
                        return response

                    cred = ApiKeySessionManagerCredentials(resp['user_data'], key, CURRENT_AAL.level, auth_ctx.pam_hdl)
                    await login_fn(app, cred)
                else:
                    await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                        'credentials': {
                            'credentials': 'API_KEY',
                            'credentials_data': {
                                'username': data['username'],
                                'api_key': key,
                            }
                        },
                        'error': resp['pam_response']['reason'],
                    }, False)

            case AuthMech.OTP_TOKEN:
                # We've received a one-time password token based in response to our
                # response to an earlier authentication attempt. This means our auth
                # context has user information. We don't re-request username from the
                # client as this would open possibility of user trivially bypassing
                # 2FA.
                resp = await self.middleware.run_in_thread(
                    auth_ctx.pam_hdl.authenticate_oath,
                    data['otp_token']
                )
                # get reference to auth data
                auth_data = auth_ctx.auth_data

                if resp.code == PAMCode.PAM_SUCCESS:
                    # Per feedback to NEP-053 it was decided to only request second
                    # factor for password-based logins (not user-linked API keys).
                    # Hence we don't have to worry about whether this is based on
                    # an API key.
                    cred = LoginTwofactorSessionManagerCredentials(
                        auth_data['user'], CURRENT_AAL.level, auth_ctx.pam_hdl
                    )
                    await login_fn(app, cred)
                else:
                    # Add a sleep like pam_delay() would add for pam_oath
                    await asyncio.sleep(CURRENT_AAL.get_delay_interval())
                    await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                        'credentials': {
                            'credentials': 'LOGIN_TWOFACTOR',
                            'credentials_data': {
                                'username': auth_data['user']['username'],
                            },
                        },
                        'error': 'One-time token validation failed.'
                    }, False)

                    # Give the user a few attempts to recover a fat-fingered OTP cred
                    if resp.code == PAMCode.PAM_CONV_AGAIN:
                        # Module says that we still have a few attempts remaining
                        auth_ctx.auth_data = auth_data
                        auth_ctx.next_mech = AuthMech.OTP_TOKEN

                        return {
                            'response_type': AuthResp.OTP_REQUIRED,
                            'username': auth_data['user']['username']
                        }

            case AuthMech.TOKEN_PLAIN:
                # We've received a authentication token that _should_ have been
                # generated by `auth.generate_token`. For consistency with other
                # authentication methods a failure delay has been added, but this
                # may be removed more safely than for other authentication methods
                # since the tokens are short-lived.
                token_str = data['token']
                token = self.token_manager.get(token_str, app.origin)
                if token is None:
                    await asyncio.sleep(CURRENT_AAL.get_delay_interval())
                    await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                        'credentials': {
                            'credentials': 'TOKEN',
                            'credentials_data': {
                                'token': token_str,
                            }
                        },
                        'error': 'Invalid token',
                    }, False)
                    return response

                if token.attributes:
                    await asyncio.sleep(CURRENT_AAL.get_delay_interval())
                    await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                        'credentials': {
                            'credentials': 'TOKEN',
                            'credentials_data': {
                                'token': token.token,
                            }
                        },
                        'error': 'Bad token',
                    }, False)
                    return response

                # Use the AF_UNIX style authenticator with username from base auth
                cred = token.root_credentials()
                if cred.is_user_session:
                    username = cred.dump()['username']
                else:
                    username = 'root'

                auth_ctx.pam_hdl = TokenPamAuthenticator(username=username, origin=app.origin)

                cred = TokenSessionManagerCredentials(self.token_manager, token, auth_ctx.pam_hdl)
                pam_resp = await self.middleware.run_in_thread(cred.pam_authenticate)
                if pam_resp.code != PAMCode.PAM_SUCCESS:
                    # Account may have gotten locked between when token originally generated and when it was used.
                    # Alternatively we may have hit session limits.
                    await asyncio.sleep(CURRENT_AAL.get_delay_interval())

                    # Unlike other failure types we can't print the token in the audit log
                    # since it is actually still valid
                    await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                        'credentials': {
                            'credentials': 'TOKEN',
                            'credentials_data': cred.dump()
                        },
                        'error': pam_resp.reason,
                    }, False)
                    return response

                await login_fn(app, cred)
                if token.single_use:
                    self.token_manager.destroy(token)

                resp = {
                    'pam_response': {
                        'code': PAMCode.PAM_SUCCESS,
                        'reason': None
                    }
                }

            case AuthMech.SCRAM:
                match data['scram_type']:
                    case 'CLIENT_FIRST_MESSAGE':
                        auth_ctx.pam_hdl = ScramPamAuthenticator(
                            client_first_message=data['rfc_str'],
                            origin=app.origin
                        )
                        auth_ctx.next_mech = AuthMech.SCRAM

                        resp = await self.middleware.run_in_thread(
                            auth_ctx.pam_hdl.handle_first_message,
                        )
                        if resp.code != PAMCode.PAM_CONV_AGAIN:
                            await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                                'credentials': {
                                    'credentials': 'SCRAM',
                                    'credentials_data': {}
                                },
                                'error': resp.reason,
                            }, False)
                            return response

                        return {
                            'response_type': AuthResp.SCRAM_RESPONSE,
                            'scram_type': 'SERVER_FIRST_RESPONSE',
                            'rfc_str': resp.reason,
                            'user_info': None
                        }
                    case 'CLIENT_FINAL_MESSAGE':
                        auth_ctx.next_mech = None

                        pam_resp = await self.middleware.run_in_thread(
                            auth_ctx.pam_hdl.handle_final_message,
                            data['rfc_str']
                        )

                        if pam_resp.code != PAMCode.PAM_SUCCESS:
                            await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                                'credentials': {
                                    'credentials': 'SCRAM',
                                    'credentials_data': {}
                                },
                                'error': pam_resp.reason,
                            }, False)
                            return response

                        user_info = await self.middleware.call('auth.authenticate_user', pam_resp.user_info)
                        if user_info is None:
                            # User is unprivileged:
                            return response

                        resp = {
                            'response_type': AuthResp.SCRAM_RESPONSE,
                            'scram_type': 'SERVER_FINAL_RESPONSE',
                            'rfc_str': pam_resp.reason,
                        }

                        # SCRAM authentication can in theory be either an API key or
                        if auth_ctx.pam_hdl.dbid:
                            key = await self.middleware.call(
                                'api_key.query', [['id', '=', auth_ctx.pam_hdl.dbid]],
                                {'get': True, 'select': ['id', 'name']}
                            )
                            cred = ApiKeySessionManagerCredentials(
                                user_info, key, CURRENT_AAL.level, auth_ctx.pam_hdl
                            )
                        else:
                            cred = UserSessionManagerCredentials(
                                user_info, key, CURRENT_AAL.level, auth_ctx.pam_hdl
                            )

                        await login_fn(app, cred)
                        resp['user_info'] = await self.me(app)
                        return resp

                    case _:
                        self.logger.error('%s: invalid scram message type', data['scram_type'])
                        raise CallError(f'{data["scram_type"]}: invalid SCRAM type')

            case _:
                # This shouldn't happen so we'll log it and raise a call error
                self.logger.error('%s: unexpected authentication mechanism', mechanism)
                raise CallError(f'{mechanism}: unexpected authentication mechanism')

        match resp['pam_response']['code']:
            case PAMCode.PAM_SUCCESS:
                response['response_type'] = AuthResp.SUCCESS
                if data['login_options']['user_info']:
                    response['user_info'] = await self.me(app)
                else:
                    response['user_info'] = None

                response['authenticator'] = await self.get_authenticator_assurance_level()

                if cred and cred.login_id.startswith('<ERROR'):
                    # If we get here, it means that pam_truenas.so isn't present in
                    # the middleware-session PAM configuration. Log an error and regenerate.
                    self.logger.error(
                        'PAM stack failed to allocate session UUID. This may indicate a '
                        'configuration error: %s. Attempting to recover. Error: %s', cred.dump(),
                        auth_ctx.pam_hdl.session_error
                    )
                    await self.middleware.call('etc.generate', 'pam_middleware')

                # Remove reference to pam handle. This ensures that logout occurs when
                # the SessionManagerCredential is deallocated or logout() explicitly called
                auth_ctx.pam_hdl = None

            case PAMCode.PAM_AUTH_ERR | PAMCode.PAM_USER_UNKNOWN:
                # We have to squash AUTH_ERR and USER_UNKNOWN into a generic response
                # to prevent unauthenticated remote clients from guessing valid usernames.
                response['response_type'] = AuthResp.AUTH_ERR
            case PAMCode.PAM_ACCT_EXPIRED | PAMCode.PAM_NEW_AUTHTOK_REQD | PAMCode.PAM_CRED_EXPIRED:
                response['response_type'] = AuthResp.EXPIRED.name
            case _:
                # This is unexpected and so we should generate a debug message
                # so that we can better handle in the future.
                self.logger.debug(
                    '%s: unexpected response code [%d] to authentication request',
                    mechanism, resp['pam_response']['code']
                )
                response['response_type'] = AuthResp.AUTH_ERR

        return response

    @private
    @pass_app()
    async def get_login_user(self, app, username, password):
        """
        This is a private endpoint that performs the actual validation of username/password
        combination and returns user information and whether additional OTP is required.
        """
        otp_required = False
        otpw_used = False

        resp = await self.middleware.call(
            'auth.authenticate_plain',
            username, password,
            app=app
        )
        if resp['pam_response']['code'] == PAMCode.PAM_SUCCESS:
            if AccountFlag.OTPW in resp['user_data']['account_attributes']:
                otpw_used = True

        elif resp['pam_response']['code'] == PAMCode.PAM_CONV_AGAIN:
            otp_required = True

        return resp | {'otp_required': otp_required, 'otpw_used': otpw_used}

    @api_method(AuthLoginWithApiKeyArgs, AuthLoginWithApiKeyResult, cli_private=True, authentication_required=False,
                pass_app=True)
    async def login_with_api_key(self, app, api_key):
        """
        Authenticate session using API Key.
        """
        try:
            key_id = int(api_key.split('-')[0])
            key_entry = await self.middleware.call('api_key.query', [['id', '=', key_id]])
        except Exception:
            key_entry = None

        if not key_entry:
            await asyncio.sleep(random.uniform(1, 2))
            await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                'credentials': {
                    'credentials': 'API_KEY',
                    'credentials_data': {
                        'username': None,
                        'api_key': api_key,
                    }
                },
                'error': 'Invalid API key'
            }, False)
            return False

        resp = await self.login_ex(app, {
            'mechanism': AuthMech.API_KEY_PLAIN,
            'username': key_entry[0]['username'],
            'api_key': api_key,
            'login_options': {'user_info': False},
        })

        return resp['response_type'] == AuthResp.SUCCESS

    @api_method(AuthLoginWithTokenArgs, AuthLoginWithTokenResult, cli_private=True, authentication_required=False,
                pass_app=True)
    async def login_with_token(self, app, token_str):
        """
        Authenticate session using token generated with `auth.generate_token`.
        """
        resp = await self.login_ex(app, {
            'mechanism': AuthMech.TOKEN_PLAIN,
            'token': token_str,
            'login_options': {'user_info': False},
        })
        return resp['response_type'] == AuthResp.SUCCESS

    @api_method(AuthLogoutArgs, AuthLogoutResult, cli_private=True, authorization_required=False, pass_app=True)
    async def logout(self, app):
        """
        Deauthenticates an app and if a token exists, removes that from the
        session.
        """
        await self.middleware.event_source_manager.unsubscribe_app(app)
        await self.session_manager.logout(app)
        return True

    @api_method(AuthMeArgs, AuthMeResult, authorization_required=False, pass_app=True, pass_app_require=True)
    async def me(self, app):
        """
        Returns currently logged-in user.
        """
        user = await self._me(app)

        if attr := await self._attributes(user):
            attributes = attr['attributes']
        else:
            attributes = {}

        try:
            twofactor_config = await self.middleware.call('user.twofactor_config', user['pw_name'])
        except Exception:
            self.logger.error('%s: failed to look up 2fa details', exc_info=True)
            twofactor_config = None

        return {**user, 'attributes': attributes, 'two_factor_config': twofactor_config}

    @api_method(AuthSetAttributeArgs, AuthSetAttributeResult, authorization_required=False, pass_app=True)
    async def set_attribute(self, app, key, value):
        """
        Set current user's `attributes` dictionary `key` to `value`.

        e.g. Setting key="foo" value="var" will result in {"attributes": {"foo": "bar"}}
        """
        user = await self._me(app)

        async with self._attributes_lock:
            if attrs := await self._attributes(user):
                await self.middleware.call('datastore.update', 'account.bsdusers_webui_attribute', attrs['id'],
                                           {'attributes': {**attrs['attributes'], key: value}})
            else:
                await self.middleware.call('datastore.insert', 'account.bsdusers_webui_attribute', {
                    'uid': user['pw_uid'],
                    'attributes': {key: value},
                })

    _attributes_lock = asyncio.Lock()

    async def _me(self, app):
        credentials = app.authenticated_credentials
        if isinstance(credentials, TokenSessionManagerCredentials):
            if root_credentials := credentials.token.root_credentials():
                credentials = root_credentials

        if not isinstance(credentials, UserSessionManagerCredentials):
            raise CallError(f'You are logged in using {credentials.class_name()}')

        username = credentials.user['username']

        account_attributes = credentials.user['account_attributes'].copy()
        # Local accounts may have hit soft limit for requiring password change
        # If they hit a hard limit then they wouldn't be here (auth would have failed)
        if 'LOCAL' in account_attributes:
            user_entry = await self.middleware.call('user.query', [
                ['username', '=', username],
                ['local', '=', True]
            ], {'get': True})
            if user_entry['password_change_required']:
                account_attributes.append('PASSWORD_CHANGE_REQUIRED')

        return {
            **(await self.middleware.call('user.get_user_obj', {'username': username})),
            'privilege': credentials.user['privilege'],
            'account_attributes': account_attributes
        }

    async def _attributes(self, user):
        try:
            return await self.middleware.call('datastore.query', 'account.bsdusers_webui_attribute',
                                              [['uid', '=', user['pw_uid']]], {'get': True})
        except MatchNotFound:
            return None


async def check_permission(middleware: Middleware, app: RpcWebSocketApp) -> None:
    """Authenticates connections coming from loopback and from root user."""
    origin = app.origin
    if origin is None or not origin.is_unix_family:
        return

    if origin.uid == 0 and not origin.session_is_interactive:
        # We can bypass more complex privilege composition for internal root sessions
        authenticator = UnixPamAuthenticator(username='root', origin=origin)
        user = await middleware.call('auth.authenticate_root')
        resp = await middleware.run_in_thread(authenticator.authenticate, 'root')
        if resp.code != PAMCode.PAM_SUCCESS:
            middleware.logger.error('root: AF_UNIX authentication for user failed: %s', resp.reason)
    else:
        # We first have to convert the UID to a username to send to PAM. The PAM
        # authenticator will handle retrieving group membership and setting account flags
        try:
            user_info = await middleware.call('user.get_user_obj', {'uid': origin.uid})
        except KeyError:
            # User does not exist
            return

        authenticator = UnixPamAuthenticator(username=user_info['pw_name'], origin=origin)
        resp = await middleware.run_in_thread(authenticator.authenticate, user_info['pw_name'])
        if resp.code != PAMCode.PAM_SUCCESS:
            middleware.logger.error('%s: AF_UNIX authentication for user failed: %s',
                                    user_info['pw_name'], resp.reason)
            return

        # Use the user_info from the authenticator (contains more information than user.get_user_obj)
        # to generate the credentials dict that will be inserted as the SessionManagerCredentials.
        user = await middleware.call('auth.authenticate_user', resp.user_info)
        if user is None:
            # User may not have privileges to TrueNAS
            return

    await AuthService.session_manager.login(app, UnixSocketSessionManagerCredentials(user, authenticator))
    if not authenticator.session_uuid:
        middleware.logger.error(
            'PAM stack failed to allocate session UUID. This may indicate a configuration error. Attempting to '
            'recover. Error: %s', authenticator.session_error
        )
        await middleware.call('etc.generate', 'pam_middleware')


def setup(middleware: Middleware):
    middleware.register_hook('core.on_connect', check_permission)
