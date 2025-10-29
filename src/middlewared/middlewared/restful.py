import asyncio
import base64
import binascii
from collections import defaultdict
import copy
import errno
import pam
import traceback
import types
import typing
import urllib.parse

from aiohttp import web

from truenas_api_client import json

from .api.base.server.app import App
from .auth import (
    ApiKeySessionManagerCredentials, LoginPasswordSessionManagerCredentials, AuthenticationContext,
    dump_credentials
)
from .job import Job
from .pipe import Pipes, InputPipes
from .service_exception import adapt_exception, CallError, MatchNotFound, ValidationError, ValidationErrors
from .utils.account.authenticator import ApiKeyPamAuthenticator, UnixPamAuthenticator, UserPamAuthenticator
from .utils.auth import AA_LEVEL1, CURRENT_AAL
from .utils.origin import ConnectionOrigin
if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


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


def normalize_query_parameter(value):
    try:
        return json.loads(value)
    except json.json.JSONDecodeError:
        return value


class Application(App):
    def __init__(self, origin, authenticated_credentials):
        super().__init__(origin)
        self.session_id = None
        self.authenticated = authenticated_credentials is not None
        self.authenticated_credentials = authenticated_credentials
        self.authentication_context = AuthenticationContext()
        self.rest = True


class RESTfulAPI:

    def __init__(self, middleware: 'Middleware', app):
        self.middleware = middleware
        self.app = app
        # Keep methods cached for future lookups
        self.methods = {}

    async def register_resources(self):
        resttest_service = self.middleware.get_service('resttest')
        service_resource = Resource(self, self.middleware, 'resttest', resttest_service._config)

        for methodname, method in list((await self.middleware.call('core.get_methods', 'resttest', 'REST')).items()):
            self.methods[methodname] = method

            if method['require_websocket']:
                continue

            short_methodname = methodname.rsplit('.', 1)[-1]

            if method.get('item_method') is True:
                parent = None
            else:
                parent = service_resource
            
            # Methods with not empty accepts list and not filterable are treated as POST HTTP methods.
            if (method['accepts'] and not method['filterable']) or method['uploadable']:
                res_kwargs = {'post': methodname}
            else:
                res_kwargs = {'get': methodname}

            Resource(
                self, self.middleware, short_methodname, resttest_service._config, parent=parent, **res_kwargs
            )

        await asyncio.sleep(0)  # Force context switch


class Resource(object):

    name = None
    parent = None
    get = None
    post = None

    def __init__(self, rest, middleware, name, service_config, parent=None, get=None, post=None):
        self.rest = rest
        self.middleware = middleware
        self.name = name
        self.parent = parent
        self.service_config = service_config
        self.__method_params = {}

        path = self.get_path()
        if get:
            self.get = get
        if post:
            self.post = post

        for i in ('get', 'post'):
            operation = getattr(self, i)
            if operation is None:
                continue
            self.rest.app.router.add_route(i.upper(), f'/api/v2.0/{path}', getattr(self, f'on_{i}'))
            self.rest.app.router.add_route(i.upper(), f'/api/v2.0/{path}/', getattr(self, f'on_{i}'))
            self.__map_method_params(operation)

        self.middleware.logger.trace(f"add route {self.get_path()}")

    def __map_method_params(self, method_name):
        """
        Middleware methods which accepts more than one argument are mapped to a single
        schema of object type.
        For that reason we need to keep track of each parameter and its order
        """
        method = self.rest.methods.get(method_name)
        if not method:
            return
        accepts = method.get('accepts')
        self.__method_params[method_name] = {}
        if accepts is None:
            return
        for i, accept in enumerate(accepts):
            # First param of an `item_method` is the item `id` and must be skipped
            # since thats gotten from the URL.
            if i == 0 and method['item_method']:
                continue
            self.__method_params[method_name][accept['title']] = {
                'order': i,
                'required': accept['_required_'],
            }

    def __getattr__(self, attr):
        if attr in ('on_get', 'on_post', 'on_delete', 'on_put'):
            do = object.__getattribute__(self, 'do')
            method = attr.split('_')[-1]

            if object.__getattribute__(self, method) is None:
                return None

            async def on_method(req, *args, **kwargs):
                resp = web.Response()
                info = req.match_info.route.resource.get_info()
                if "path" in info:
                    resource = info["path"][len("/api/v2.0"):]
                elif "formatter" in info:
                    resource = info["formatter"][len("/api/v2.0"):]
                else:
                    resource = None

                app = await create_application(req)
                auth_required = not self.rest.methods[getattr(self, method)]['no_auth_required']
                credentials = parse_credentials(req)
                if credentials is None:
                    if auth_required:
                        raise web.HTTPUnauthorized()

                    authenticated_credentials = None
                else:
                    try:
                        authenticated_credentials = await authenticate(app, self.middleware, req, credentials,
                                                                       method.upper(), resource)
                    except web.HTTPException as e:
                        credentials['credentials_data'].pop('password', None)
                        credentials['credentials_data'].pop('api_key', None)
                        await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                            'credentials': credentials,
                            'error': e.text,
                        }, False)
                        raise
                    app = await create_application(req, authenticated_credentials)
                    await self.middleware.log_audit_message(app, 'AUTHENTICATION', {
                        'credentials': dump_credentials(authenticated_credentials),
                        'error': None,
                    }, True)
                if auth_required:
                    if authenticated_credentials is None:
                        raise web.HTTPUnauthorized()
                kwargs.update(dict(req.match_info))
                return await do(method, req, resp, app,
                                not auth_required or authenticated_credentials.authorize(method.upper(), resource),
                                *args, **kwargs)

            return on_method
        return object.__getattribute__(self, attr)

    def get_path(self):
        path = []
        parent = self.parent
        while parent is not None:
            path.append(parent.name)
            parent = parent.parent
        path.reverse()
        path.append(self.name)
        return '/'.join(path)

    def _filterable_args(self, req):
        filters = []
        extra_args = {}
        options = {}
        for key, val in list(req.query.items()):
            if '__' in key:
                field, op = key.split('__', 1)
            else:
                field, op = key, '='

            def convert(val):
                if val.isdigit():
                    val = int(val)
                elif val.lower() in ('true', 'false', '0', '1'):
                    if val.lower() in ('true', '1'):
                        val = True
                    elif val.lower() in ('false', '0'):
                        val = False
                return val

            if key in ('limit', 'offset', 'count'):
                options[key] = convert(val)
                continue
            elif key == 'sort':
                options[key] = [convert(v) for v in val.split(',')]
                continue
            elif key.startswith('extra.'):
                key = key[len('extra.'):]
                extra_args[key] = normalize_query_parameter(val)
                continue

            op_map = {
                'eq': '=',
                'neq': '!=',
                'gt': '>',
                'lt': '<',
                'gte': '>=',
                'lte': '<=',
                'regex': '~',
            }

            op = op_map.get(op, op)

            if val.isdigit():
                val = int(val)
            elif val.lower() == 'true':
                val = True
            elif val.lower() == 'false':
                val = False
            elif val.lower() == 'null':
                val = None
            filters.append((field, op, val))

        if extra_args:
            options['extra'] = extra_args

        return [filters, options] if filters or options else []

    async def parse_rest_json_request(self, req, resp):
        body, error = None, False
        try:
            body = await req.json()
        except json.decoder.JSONDecodeError as e:
            resp.set_status(400)
            resp.headers['Content-type'] = 'application/json'
            resp.text = json.dumps({
                'message': f'json parse error: {e}',
                'errno': errno.EINVAL,
            }, indent=True)
            error = True

        return body, error

    async def do(self, http_method, req, resp, app, authorized, **kwargs):
        assert http_method in ('delete', 'get', 'post', 'put')

        methodname = getattr(self, http_method)
        method = self.rest.methods[methodname]

        method_kwargs = {}
        method_kwargs['app'] = app

        has_request_body = False
        request_body = None
        upload_pipe = None
        filepart = None
        if method['uploadable']:
            if req.headers.get('Content-Type', '').startswith('multipart/'):
                reader = await req.multipart()

                part = await reader.next()
                if not part or part.name != "data":
                    resp.set_status(400)
                    resp.headers['Content-type'] = 'application/json'
                    resp.text = json.dumps({
                        'message': 'The method accepts multipart requests with two parts (`data` and `file`).',
                        'errno': errno.EINVAL,
                    }, indent=True)
                    return resp

                has_request_body = True
                try:
                    request_body = json.loads(await part.read())
                except ValueError as e:
                    resp.set_status(400)
                    resp.headers['Content-type'] = 'application/json'
                    resp.text = json.dumps({
                        'message': f'`data` json parse error: {e}',
                        'errno': errno.EINVAL,
                    }, indent=True)
                    return resp

                filepart = await reader.next()
                if not filepart or filepart.name != "file":
                    resp.set_status(400)
                    resp.headers['Content-type'] = 'application/json'
                    resp.text = json.dumps({
                        'message': ('The method accepts multipart requests with two parts (`data` and `file`). '
                                    '`file` not found.'),
                        'errno': errno.EINVAL,
                    }, indent=True)
                    return resp

                upload_pipe = self.middleware.pipe()
            else:
                if method['check_pipes']:
                    resp.set_status(400)
                    resp.headers['Content-type'] = 'application/json'
                    resp.text = json.dumps({
                        'message': 'This method accepts only multipart requests.',
                        'errno': errno.EINVAL,
                    }, indent=True)
                    return resp
                else:
                    if await req.text():
                        has_request_body = True
                        request_body, error = await self.parse_rest_json_request(req, resp)
                        if error:
                            return resp
        else:
            if await req.text():
                has_request_body = True
                request_body, error = await self.parse_rest_json_request(req, resp)
                if error:
                    return resp

        download_pipe = None
        if method['downloadable']:
            if req.query.get('download', '1') == '1':
                download_pipe = self.middleware.pipe()
            else:
                if method['check_pipes']:
                    resp.set_status(400)
                    resp.headers['Content-type'] = 'application/json'
                    resp.text = json.dumps({
                        'message': 'JSON response is not supported for this method.',
                        'errno': errno.EINVAL,
                    }, indent=True)
                    return resp

        if upload_pipe and download_pipe:
            method_kwargs['pipes'] = Pipes(inputs=InputPipes(upload_pipe), output=download_pipe)
        elif upload_pipe:
            method_kwargs['pipes'] = Pipes(inputs=InputPipes(upload_pipe))
        elif download_pipe:
            method_kwargs['pipes'] = Pipes(output=download_pipe)

        method_args = []
        if http_method == 'get' and method['filterable']:
            if self.parent and 'id_' in kwargs:
                primary_key = kwargs['id_']
                if primary_key.isdigit():
                    primary_key = int(primary_key)
                extra = {}
                for key, val in list(req.query.items()):
                    if key.startswith('extra.'):
                        extra[key[len('extra.'):]] = normalize_query_parameter(val)

                method_args = [
                    [(self.service_config['datastore_primary_key'], '=', primary_key)],
                    {'get': True, 'force_sql_filters': True, 'extra': extra}
                ]
            else:
                method_args = self._filterable_args(req)

        if not method_args:
            # RFC 7231 specifies that a GET request can accept a payload body
            # This means that all the http methods now ( delete, get, post, put ) accept a payload body
            try:
                if not has_request_body:
                    method_args = []
                else:
                    data = request_body
                    params = self.__method_params.get(methodname)
                    if not params and http_method in ('get', 'delete') and not data:
                        # This will happen when the request body contains empty dict "{}"
                        # Keeping compatibility with how we used to accept the above case, this
                        # makes sure that existing client implementations are not affected
                        method_args = []
                    elif not params or len(params) == 1:
                        method_args = [data]
                    else:
                        if not isinstance(data, dict):
                            resp.set_status(400)
                            resp.headers['Content-type'] = 'application/json'
                            resp.body = json.dumps({
                                'message': 'Endpoint accepts multiple params, object/dict expected.',
                            })
                            return resp
                        # These parameters were renamed as pydantic does not support `-` in parameter names
                        if 'query-filters' in data and 'query-filters' not in params and 'filters' in params:
                            data['filters'] = data.pop('query-filters')
                        if 'query-options' in data and 'query-options' not in params and 'options' in params:
                            data['options'] = data.pop('query-options')
                        method_args = []
                        for p, options in sorted(params.items(), key=lambda x: x[1]['order']):
                            if p not in data and options['required']:
                                resp.set_status(400)
                                resp.headers['Content-type'] = 'application/json'
                                resp.body = json.dumps({
                                    'message': f'{p} attribute expected.',
                                })
                                return resp
                            elif p in data:
                                method_args.append(data.pop(p))
                        if data:
                            resp.set_status(400)
                            resp.headers['Content-type'] = 'application/json'
                            resp.body = json.dumps({
                                'message': f'The following attributes are not expected: {", ".join(data.keys())}',
                            })
                            return resp
            except Exception as e:
                resp.set_status(400)
                resp.headers['Content-type'] = 'application/json'
                resp.body = json.dumps({
                    'message': str(e),
                })
                return resp

        """
        If the method is marked `item_method` then the first argument
        must be the item id (from url param)
        """
        if method.get('item_method') is True:
            id_ = kwargs['id_']
            try:
                id_ = int(id_)
            except ValueError:
                pass
            method_args.insert(0, id_)

        try:
            serviceobj, methodobj = self.middleware.get_method(methodname)
            if authorized:
                result = await self.middleware.call_with_audit(methodname, serviceobj, methodobj, method_args,
                                                               **method_kwargs)
                result = self.middleware.dump_result(serviceobj, methodobj, app, result)
            else:
                await self.middleware.log_audit_message_for_method(methodname, methodobj, method_args, app,
                                                                   True, False, False)
                resp.set_status(403)
                return resp
            if upload_pipe:
                await self.middleware.run_in_thread(copy_multipart_to_pipe, self.middleware.loop, filepart, upload_pipe)
            if method['downloadable'] and download_pipe is None:
                result = await result.wait()
        except CallError as e:
            resp = web.Response(status=422)
            result = {
                'message': e.errmsg,
                'errno': e.errno,
            }
        except (ValidationError, ValidationErrors) as e:
            if isinstance(e, ValidationError):
                e = [(e.attribute, e.errmsg, e.errno)]
            result = defaultdict(list)
            for attr, errmsg, errno_ in e:
                result[attr].append({
                    'message': errmsg,
                    'errno': errno_,
                })
            resp = web.Response(status=422)

        except Exception as e:
            adapted = adapt_exception(e)
            if adapted:
                resp = web.Response(status=422)
                result = {
                    'message': adapted.errmsg,
                    'errno': adapted.errno,
                }
            else:
                if isinstance(e, (MatchNotFound,)):
                    resp = web.Response(status=404)
                    result = {
                        'message': str(e),
                    }
                else:
                    resp = web.Response(status=500)
                    result = {
                        'message': str(e),
                        'traceback': ''.join(traceback.format_exc()),
                    }

        if download_pipe is not None:
            resp = web.StreamResponse(status=200, reason='OK', headers={
                'Content-Type': 'application/octet-stream',
                'Transfer-Encoding': 'chunked',
            })
            await resp.prepare(req)

            loop = asyncio.get_event_loop()

            def do_copy():
                while True:
                    read = download_pipe.r.read(1048576)
                    if read == b'':
                        break
                    asyncio.run_coroutine_threadsafe(resp.write(read), loop=loop).result()

            await self.middleware.run_in_thread(do_copy)

            await resp.drain()
            return resp

        if isinstance(result, types.GeneratorType):
            result = list(result)
        elif isinstance(result, types.AsyncGeneratorType):
            result = [i async for i in result]
        elif isinstance(result, Job):
            result = result.id
        resp.headers['Content-type'] = 'application/json'
        resp.text = json.dumps(result, indent=True)
        return resp


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
