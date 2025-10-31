import asyncio
import base64
import binascii
import pam
import urllib.parse

from aiohttp import web

from .api.base.server.app import App
from .auth import ApiKeySessionManagerCredentials, LoginPasswordSessionManagerCredentials, AuthenticationContext
from .service_exception import CallError
from .utils.account.authenticator import ApiKeyPamAuthenticator, UnixPamAuthenticator, UserPamAuthenticator
from .utils.auth import AA_LEVEL1, CURRENT_AAL
from .utils.origin import ConnectionOrigin


def parse_credentials(request):
    auth = request.headers.get('Authorization')
    if auth is None:
        qs = urllib.parse.parse_qs(request.query_string)
        if 'auth_token' in qs:
            return {
                'credentials': 'TOKEN',
                'credentials_data': {
                    'token': qs['auth_token'][0],
                },
            }
        else:
            return None
    elif auth.startswith('Token '):
        token = auth.split(' ', 1)[1]
        return {
            'credentials': 'TOKEN',
            'credentials_data': {
                'token': token,
            },
        }

    if auth.startswith('Basic '):
        try:
            username, password = base64.b64decode(auth[6:]).decode('utf-8').split(':', 1)
        except UnicodeDecodeError:
            raise web.HTTPBadRequest()
        except binascii.Error:
            raise web.HTTPBadRequest()

        return {
            'credentials': 'LOGIN_PASSWORD',
            'credentials_data': {
                'username': username,
                'password': password,
            },
        }
    elif auth.startswith('Bearer '):
        key = auth.split(' ', 1)[1]

        return {
            'credentials': 'API_KEY',
            'credentials_data': {
                'api_key': key,
            }
        }


async def authenticate(app, middleware, request, credentials, method, resource):

    if credentials['credentials'] == 'TOKEN':
        origin = await middleware.run_in_thread(ConnectionOrigin.create, request)
        # We are using the UnixPamAuthenticator here because we are generating a
        # fresh login based on the username in base token's credentials
        app.authentication_context.pam_hdl = UnixPamAuthenticator()
        try:
            token = await middleware.call('auth.get_token_for_action', credentials['credentials_data']['token'],
                                          origin, method, resource, app=app)
        except CallError as ce:
            raise web.HTTPForbidden(text=ce.errmsg)

        if token is None:
            raise web.HTTPForbidden(text='Invalid token')

        return token
    elif credentials['credentials'] == 'LOGIN_PASSWORD':
        twofactor_auth = await middleware.call('auth.twofactor.config')
        if twofactor_auth['enabled']:
            raise web.HTTPUnauthorized(text='HTTP Basic Auth is unavailable when OTP is enabled')

        app.authentication_context.pam_hdl = UserPamAuthenticator()
        resp = await middleware.call('auth.authenticate_plain',
                                     credentials['credentials_data']['username'],
                                     credentials['credentials_data']['password'], app=app)
        if resp['pam_response']['code'] != pam.PAM_SUCCESS:
            raise web.HTTPUnauthorized(text='Bad username or password')

        return LoginPasswordSessionManagerCredentials(
            resp['user_data'],
            assurance=CURRENT_AAL.level,
            authenticator=app.authentication_context.pam_hdl
        )
    elif credentials['credentials'] == 'API_KEY':
        if CURRENT_AAL.level is not AA_LEVEL1:
            raise web.HTTPForbidden(
                text='API key authentication is not permitted by server authentication security level'
            )

        app.authentication_context.pam_hdl = ApiKeyPamAuthenticator()
        api_key = await middleware.call('api_key.authenticate', credentials['credentials_data']['api_key'], app=app)
        if api_key is None:
            raise web.HTTPUnauthorized(text='Invalid API key')

        return ApiKeySessionManagerCredentials(
            *api_key,
            assurance=CURRENT_AAL.level,
            authenticator=app.authentication_context.pam_hdl
        )
    else:
        raise web.HTTPUnauthorized()


def create_application_impl(request, credentials=None):
    return Application(ConnectionOrigin.create(request), credentials)


async def create_application(request, credentials=None):
    return await asyncio.to_thread(create_application_impl, request, credentials)


class Application(App):
    def __init__(self, origin, authenticated_credentials):
        super().__init__(origin)
        self.session_id = None
        self.authenticated = authenticated_credentials is not None
        self.authenticated_credentials = authenticated_credentials
        self.authentication_context = AuthenticationContext()
        self.rest = True


def copy_multipart_to_pipe(loop, filepart, pipe):
    try:
        try:
            while True:
                read = asyncio.run_coroutine_threadsafe(
                    filepart.read_chunk(filepart.chunk_size),
                    loop=loop,
                ).result()
                if read == b'':
                    break
                pipe.w.write(read)
        finally:
            pipe.w.close()
    except BrokenPipeError:
        pass
