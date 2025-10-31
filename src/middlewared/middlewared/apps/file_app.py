import asyncio
import base64
import binascii
import pam
from typing import Literal, TypeAlias, TypedDict, Union, TYPE_CHECKING
import urllib.parse

from aiohttp import web

from middlewared.api.base.server.app import App
from middlewared.auth import (
    ApiKeySessionManagerCredentials,
    LoginPasswordSessionManagerCredentials,
    TokenSessionManagerCredentials,
    AuthenticationContext
)
from middlewared.pipe import Pipes, InputPipes
from middlewared.service_exception import CallError
from middlewared.utils.account.authenticator import ApiKeyPamAuthenticator, UnixPamAuthenticator, UserPamAuthenticator
from middlewared.utils.auth import AA_LEVEL1, CURRENT_AAL
from middlewared.utils.origin import ConnectionOrigin
from truenas_api_client import json

if TYPE_CHECKING:
    from aiohttp import BodyPartReader
    from middlewared.api.base.types import HttpVerb
    from middlewared.main import Middleware
    from middlewared.pipe import Pipe

__all__ = ("FileApplication",)


class TokenDict(TypedDict):
    token: str


class LoginDict(TypedDict):
    username: str
    password: str


class APIKeyDict(TypedDict):
    api_key: str


class TokenCredentialsDict(TypedDict):
    credentials: Literal['TOKEN']
    credentials_data: TokenDict


class LoginCredentialsDict(TypedDict):
    credentials: Literal['LOGIN_PASSWORD']
    credentials_data: LoginDict


class KeyCredentialsDict(TypedDict):
    credentials: Literal['API_KEY']
    credentials_data: APIKeyDict


CredentialsDict: TypeAlias = TokenCredentialsDict | LoginCredentialsDict | KeyCredentialsDict
SessionManagerCredentials: TypeAlias = Union[
    TokenSessionManagerCredentials,
    LoginPasswordSessionManagerCredentials,
    ApiKeySessionManagerCredentials
]


MAX_UPLOADED_FILES = 5


def parse_credentials(request: web.Request) -> CredentialsDict | None:
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

    if auth.startswith('Token '):
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

    if auth.startswith('Bearer '):
        key = auth.split(' ', 1)[1]

        return {
            'credentials': 'API_KEY',
            'credentials_data': {
                'api_key': key,
            }
        }


async def authenticate(
    app: App,
    middleware: 'Middleware',
    request: web.Request,
    credentials: CredentialsDict,
    method: 'HttpVerb',
    resource: str
) -> SessionManagerCredentials:
    match credentials['credentials']:
        case 'TOKEN':
            origin = await middleware.run_in_thread(ConnectionOrigin.create, request)
            # We are using the UnixPamAuthenticator here because we are generating a
            # fresh login based on the username in base token's credentials
            app.authentication_context.pam_hdl = UnixPamAuthenticator()
            try:
                token = await middleware.call(
                    'auth.get_token_for_action',
                    credentials['credentials_data']['token'],
                    origin,
                    method,
                    resource,
                    app=app
                )
            except CallError as ce:
                raise web.HTTPForbidden(text=ce.errmsg)

            if token is None:
                raise web.HTTPForbidden(text='Invalid token')

            return token

        case 'LOGIN_PASSWORD':
            twofactor_auth = await middleware.call('auth.twofactor.config')
            if twofactor_auth['enabled']:
                raise web.HTTPUnauthorized(text='HTTP Basic Auth is unavailable when OTP is enabled')

            app.authentication_context.pam_hdl = UserPamAuthenticator()
            resp = await middleware.call(
                'auth.authenticate_plain',
                credentials['credentials_data']['username'],
                credentials['credentials_data']['password'],
                app=app
            )
            if resp['pam_response']['code'] != pam.PAM_SUCCESS:
                raise web.HTTPUnauthorized(text='Bad username or password')

            return LoginPasswordSessionManagerCredentials(
                resp['user_data'],
                assurance=CURRENT_AAL.level,
                authenticator=app.authentication_context.pam_hdl
            )

        case 'API_KEY':
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

        case _:
            raise web.HTTPUnauthorized()


class Application(App):
    def __init__(self, origin: ConnectionOrigin, authenticated_credentials: SessionManagerCredentials | None):
        super().__init__(origin)
        self.session_id = None
        self.authenticated = authenticated_credentials is not None
        self.authenticated_credentials = authenticated_credentials
        self.authentication_context = AuthenticationContext()
        self.rest = True


def create_application_impl(
    request: web.Request, credentials: SessionManagerCredentials | None = None
) -> Application:
    return Application(ConnectionOrigin.create(request), credentials)


async def create_application(
    request: web.Request, credentials: SessionManagerCredentials | None = None
) -> Application:
    return await asyncio.to_thread(create_application_impl, request, credentials)


def copy_multipart_to_pipe(loop: asyncio.AbstractEventLoop, filepart: 'BodyPartReader', pipe: 'Pipe') -> None:
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


class FileApplication:
    def __init__(self, middleware: "Middleware", loop: asyncio.AbstractEventLoop):
        self.middleware = middleware
        self.loop = loop
        self.jobs: dict[int, asyncio.TimerHandle] = {}

    def register_job(self, job_id: int, buffered: bool) -> None:
        # FIXME: Allow the job to run for infinite time + give 300 seconds to begin
        # download instead of waiting 3600 seconds for the whole operation
        self.jobs[job_id] = self.middleware.loop.call_later(
            3600 if buffered else 60,
            lambda: self.middleware.create_task(self._cleanup_job(job_id)),
        )

    async def _cleanup_cancel(self, job_id: int) -> None:
        job_cleanup = self.jobs.pop(job_id, None)
        if job_cleanup:
            job_cleanup.cancel()

    async def _cleanup_job(self, job_id: int) -> None:
        if job_id not in self.jobs:
            return
        self.jobs[job_id].cancel()
        del self.jobs[job_id]

        job = self.middleware.jobs[job_id]
        await job.pipes.close()

    async def download(self, request: web.Request) -> web.Response | web.StreamResponse:
        path = request.path.split("/")
        if not request.path[-1].isdigit():
            resp = web.Response()
            resp.set_status(404)
            return resp

        job_id = int(path[-1])

        qs = urllib.parse.parse_qs(request.query_string)
        denied = False
        filename = None
        if "auth_token" not in qs:
            denied = True
        else:
            origin = await self.middleware.run_in_thread(ConnectionOrigin.create, request)
            auth_token = qs["auth_token"][0]
            token = await self.middleware.call("auth.get_token", auth_token, origin)
            if not token:
                denied = True
            else:
                if token["attributes"].get("job") != job_id:
                    denied = True
                else:
                    filename = token["attributes"].get("filename")
        if denied:
            resp = web.Response()
            resp.set_status(401)
            return resp

        job = self.middleware.jobs.get(job_id)
        if not job:
            resp = web.Response()
            resp.set_status(404)
            return resp

        if job_id not in self.jobs:
            resp = web.Response()
            resp.set_status(410)
            return resp

        resp = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Transfer-Encoding": "chunked",
            },
        )
        await resp.prepare(request)

        def do_copy():
            while True:
                read = job.pipes.output.r.read(1048576)
                if read == b"":
                    break
                asyncio.run_coroutine_threadsafe(resp.write(read), loop=self.loop).result()

        try:
            await self._cleanup_cancel(job_id)
            await self.middleware.run_in_thread(do_copy)
        finally:
            await job.pipes.close()

        await resp.drain()
        return resp

    async def upload(self, request: web.Request) -> web.Response:
        reader = await request.multipart()

        part = await reader.next()
        if not part:
            resp = web.Response(status=405, body="No part found on payload")
            resp.set_status(405)
            return resp

        if part.name != "data":
            resp = web.Response(
                status=405, body='"data" part must be the first on payload'
            )
            resp.set_status(405)
            return resp

        try:
            data = json.loads(await part.read())
        except Exception as e:
            return web.Response(status=400, body=str(e))

        if "method" not in data:
            return web.Response(status=422)

        try:
            credentials = parse_credentials(request)
            if credentials is None:
                raise web.HTTPUnauthorized()
        except web.HTTPException as e:
            return web.Response(status=e.status_code, body=e.text)
        app = await create_application(request)
        try:
            authenticated_credentials = await authenticate(
                app, self.middleware, request, credentials, "CALL", data["method"]
            )
            if authenticated_credentials is None:
                raise web.HTTPUnauthorized()
        except web.HTTPException as e:
            credentials["credentials_data"].pop("password", None)
            await self.middleware.log_audit_message(
                app,
                "AUTHENTICATION",
                {
                    "credentials": credentials,
                    "error": e.text,
                },
                False,
            )
            return web.Response(status=e.status_code, body=e.text)
        app = await create_application(request, authenticated_credentials)
        credentials["credentials_data"].pop("password", None)
        await self.middleware.log_audit_message(
            app,
            "AUTHENTICATION",
            {
                "credentials": credentials,
                "error": None,
            },
            True,
        )

        filepart = await reader.next()
        if not filepart or filepart.name != "file":
            resp = web.Response(
                status=405, body='"file" not found as second part on payload'
            )
            resp.set_status(405)
            return resp

        try:
            params = data.get("params") or []
            serviceobj, methodobj = self.middleware.get_method(data["method"], mocks=True, params=params)
            if not authenticated_credentials.authorize("CALL", data["method"]):
                await self.middleware.log_audit_message_for_method(
                    data["method"],
                    methodobj,
                    data.get("params") or [],
                    app,
                    True,
                    False,
                    False,
                )
                raise web.HTTPForbidden()

            first_pipe = self.middleware.pipe()
            with InputPipes(first_pipe) as input_pipes:
                job = await self.middleware.call_with_audit(
                    data["method"],
                    serviceobj,
                    methodobj,
                    params,
                    app,
                    pipes=Pipes(inputs=input_pipes),
                )

                await self.middleware.run_in_thread(copy_multipart_to_pipe, self.loop, filepart, first_pipe)

                for i in range(MAX_UPLOADED_FILES - 1):
                    filepart = await reader.next()
                    if not filepart:
                        break

                    if filepart.name != "file":
                        resp = web.Response(status=405, body=f'Unknown payload part {filepart.name!r}')
                        return resp

                    next_pipe = self.middleware.pipe()
                    input_pipes.add_pipe(next_pipe)
                    await self.middleware.run_in_thread(copy_multipart_to_pipe, self.loop, filepart, next_pipe)

                if await reader.next():
                    resp = web.Response(status=405, body='Too many uploaded files')
                    return resp
        except CallError as e:
            if e.errno == CallError.ENOMETHOD:
                status_code = 422
            else:
                status_code = 412
            return web.Response(status=status_code, body=str(e))
        except web.HTTPException as e:
            return web.Response(status=e.status_code, body=e.text)
        except Exception as e:
            return web.Response(status=500, body=str(e))

        resp = web.Response(
            status=200,
            headers={
                "Content-Type": "application/json",
            },
            body=json.dumps({"job_id": job.id}).encode(),
        )
        return resp
