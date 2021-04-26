from aiohttp import web
from collections import defaultdict

import asyncio
import base64
import binascii
import copy
import traceback
import types

from .client import ejson as json
from .job import Job
from .pipe import Pipes
from .schema import Error as SchemaError
from .service_exception import adapt_exception, CallError, ValidationError, ValidationErrors, MatchNotFound


async def authenticate(middleware, req):

    auth = req.headers.get('Authorization')
    if auth is None:
        raise web.HTTPUnauthorized()

    if auth.startswith('Basic '):
        try:
            username, password = base64.b64decode(auth[6:]).decode('utf8').split(':', 1)
        except UnicodeDecodeError:
            raise web.HTTPBadRequest()
        except binascii.Error:
            raise web.HTTPUnauthorized()

        try:
            if not await middleware.call('auth.check_user', username, password):
                raise web.HTTPUnauthorized()
        except web.HTTPUnauthorized:
            raise
        except Exception:
            raise web.HTTPUnauthorized()
    elif auth.startswith('Bearer '):
        key = auth.split(' ', 1)[1]

        if await middleware.call('api_key.authenticate', key) is None:
            raise web.HTTPUnauthorized()
    else:
        raise web.HTTPUnauthorized()


def normalize_query_parameter(value):
    try:
        return json.loads(value)
    except json.json.JSONDecodeError:
        return value


class Application:

    def __init__(self, host, remote_port):
        self.host = host
        self.remote_port = remote_port
        self.websocket = False
        self.rest = self.authenticated = True


class RESTfulAPI(object):

    def __init__(self, middleware, app):
        self.middleware = middleware
        self.app = app

        # Keep methods cached for future lookups
        self._methods = {}
        self._methods_by_service = defaultdict(dict)

        self._openapi = OpenAPIResource(self)

    def get_app(self):
        return self.app

    async def register_resources(self):
        for methodname, method in list((await self.middleware.call('core.get_methods')).items()):
            self._methods[methodname] = method
            self._methods_by_service[methodname.rsplit('.', 1)[0]][methodname] = method

        for name, service in list((await self.middleware.call('core.get_services')).items()):
            kwargs = {}
            blacklist_methods = []
            """
            Hook up methods for the resource entrypoint.
            For CRUD:
              - GET -> $name.query
              - POST - $name.create
            For Config:
              - GET -> $name.config
              - PUT -> $name.update
            """
            if service['type'] == 'crud':
                kwargs['get'] = '{}.query'.format(name)
                post = f'{name}.create'
                if post in self._methods:
                    kwargs['post'] = '{}.create'.format(name)
                blacklist_methods.extend(list(kwargs.values()))
            elif service['type'] == 'config':
                kwargs['get'] = '{}.config'.format(name)
                put = '{}.update'.format(name)
                if put in self._methods:
                    kwargs['put'] = put
                blacklist_methods.extend(list(kwargs.values()))

            service_resource = Resource(self, self.middleware, name.replace('.', '/'), service['config'], **kwargs)

            """
            For CRUD services we also need a direct subresource so we can
            operate on items in the entity, e.g. update or delete "john" of user namespace.
            """
            subresource = None
            if service['type'] == 'crud':
                kwargs = {}
                get = f'{name}.query'
                if get in self._methods:
                    kwargs['get'] = get
                delete = f'{name}.delete'
                if delete in self._methods:
                    kwargs['delete'] = delete
                put = f'{name}.update'
                if put in self._methods:
                    kwargs['put'] = put
                blacklist_methods.extend(list(kwargs.values()))
                subresource = Resource(
                    self, self.middleware, 'id/{id}', service['config'], parent=service_resource, **kwargs
                )

            for methodname, method in list(self._methods_by_service[name].items()):
                if methodname in blacklist_methods:
                    continue
                if method['require_websocket']:
                    continue
                short_methodname = methodname.rsplit('.', 1)[-1]
                if method.get('item_method') is True:
                    parent = subresource
                else:
                    parent = service_resource

                res_kwargs = {}
                """
                Methods with not empty accepts list and not filterable
                are treated as POST HTTP methods.
                """
                if method['accepts'] and not method['filterable']:
                    res_kwargs['post'] = methodname
                else:
                    res_kwargs['get'] = methodname
                for rest_method in map(str.lower, (method['extra_methods'] or [])):
                    assert rest_method in ('get',)
                    # Only allow get for now as that's the only use case we have for now NAS-110243
                    res_kwargs[rest_method] = methodname

                Resource(self, self.middleware, short_methodname, service['config'], parent=parent, **res_kwargs)
            await asyncio.sleep(0)  # Force context switch


class OpenAPIResource(object):

    def __init__(self, rest):
        self.rest = rest
        self.rest.app.router.add_route('GET', '/api/v2.0', self.get)
        self.rest.app.router.add_route('GET', '/api/v2.0/', self.get)
        self.rest.app.router.add_route('GET', '/api/v2.0/openapi.json', self.get)
        self._paths = defaultdict(dict)
        self._schemas = dict()
        self._components = defaultdict(dict)
        self._components['schemas'] = self._schemas
        self._components['responses'] = {
            'NotFound': {
                'description': 'Endpoint not found',
            },
            'Unauthorized': {
                'description': 'No authorization for this endpoint',
            },
            'Success': {
                'description': 'Operation succeeded',
            },
        }
        self._components['securitySchemes'] = {
            'basic': {
                'type': 'http',
                'scheme': 'basic'
            },
        }

    def add_path(self, path, operation, methodname, service_config):
        assert operation in ('get', 'post', 'put', 'delete')
        opobject = {
            'tags': [methodname.rsplit('.', 1)[0]],
            'responses': {
                '200': {'$ref': '#/components/responses/Success'},
                '401': {'$ref': '#/components/responses/Unauthorized'},
            },
            'parameters': [],
        }
        method = self.rest._methods.get(methodname)
        if method and method.get('require_pipes'):
            return
        elif method:
            desc = method.get('description') or ''
            if method.get('downloadable') or method.get('uploadable'):
                job_desc = f'\n\nA file can be {"downloaded from" if method.get("downloadable") else "uploaded to"} ' \
                           'this end point. This end point is special, please refer to Jobs section in ' \
                           'Websocket API documentation for details.'
                desc = (desc or '') + job_desc

            if desc:
                opobject['description'] = desc

            accepts = method.get('accepts')
            if method['filterable']:
                opobject['parameters'] += [
                    {
                        'name': 'limit',
                        'in': 'query',
                        'required': False,
                        'schema': {'type': 'integer'},
                    },
                    {
                        'name': 'offset',
                        'in': 'query',
                        'required': False,
                        'schema': {'type': 'integer'},
                    },
                    {
                        'name': 'count',
                        'in': 'query',
                        'required': False,
                        'schema': {'type': 'boolean'},
                    },
                    {
                        'name': 'sort',
                        'in': 'query',
                        'required': False,
                        'schema': {'type': 'string'},
                    },
                ] if '{id}' not in path else []
                desc = f'{desc}\n\n' if desc else ''
                opobject['description'] = desc + '`query-options.extra` can be specified as query parameters with ' \
                                                 'prefixing them with `extra.` prefix. For example, ' \
                                                 '`extra.retrieve_properties=false` will pass `retrieve_properties` ' \
                                                 'as an extra argument to pool/dataset endpoint.'
            elif accepts and not (operation == 'delete' and method['item_method'] and len(accepts) == 1) and (
                '{id}' not in path and not method['filterable']
            ):
                opobject['requestBody'] = self._accepts_to_request(methodname, method, accepts)

            # For now we only accept `id` as an url parameters
            if '{id}' in path:
                opobject['parameters'].append({
                    'name': 'id',
                    'in': 'path',
                    'required': True,
                    'schema': {'type': service_config['datastore_primary_key_type']},
                })

        self._paths[f'/{path}'][operation] = opobject

    def _convert_schema(self, schema):
        """
        Convert JSON Schema to OpenAPI Schema
        """
        schema = copy.deepcopy(schema)
        _type = schema.get('type')
        schema.pop('_required_', None)
        if isinstance(_type, list):
            if 'null' in _type:
                _type.remove('null')
                schema['nullable'] = True
            schema['type'] = _type = _type[0]
        if _type == 'object':
            for key, val in schema['properties'].items():
                schema['properties'][key] = self._convert_schema(val)
        elif _type == 'array':
            items = schema.get('items')
            for i, item in enumerate(list(items)):
                if item.get('type') == 'null':
                    items.remove(item)
            if isinstance(items, list):
                if len(items) > 1:
                    schema['items'] = {'oneOf': items}
                elif len(items) > 0:
                    schema['items'] = items[0]
                else:
                    schema['items'] = {}
        return schema

    def _accepts_to_request(self, methodname, method, schemas):

        # Create an unique ID for every argument and register the schema
        ids = []
        for i, schema in enumerate(schemas):
            if i == 0 and method['item_method']:
                continue
            unique_id = f'{methodname.replace(".", "_")}_{i}'
            self._schemas[unique_id] = self._convert_schema(schema)
            ids.append(unique_id)

        if len(ids) == 1:
            schema = f'#/components/schemas/{ids[0]}'
        else:
            # If the method accepts multiple arguments lets emulate/create
            # a new schema, which is a object containing every argument as an
            # attribute.
            props = {}
            for i in ids:
                schema = self._schemas[i]
                props[schema['title']] = {'$ref': f'#/components/schemas/{i}'}
            new_schema = {
                'type': 'object',
                'properties': props
            }
            new_id = f'{methodname.replace(".", "_")}'
            self._schemas[new_id] = new_schema
            schema = f'#/components/schemas/{new_id}'

        json_request = {'schema': {'$ref': schema}}
        for i, example in enumerate(method['examples']['rest']):
            try:
                title, example = example.split('{', 1)
                example = json.loads('{' + example.strip())
            except ValueError:
                pass
            else:
                json_request.setdefault('examples', {})
                json_request['examples'][f'example_{i + 1}'] = {'summary': title.strip(), 'value': example}

        return {
            'content': {
                'application/json': json_request,
            }
        }

    def get(self, req, **kwargs):

        servers = []
        host = req.headers.get('Host')
        if host:
            servers.append({
                'url': f'{req.scheme}://{host}/api/v2.0',
            })

        result = {
            'openapi': '3.0.0',
            'info': {
                'title': 'TrueNAS RESTful API',
                'version': 'v2.0',
            },
            'paths': self._paths,
            'servers': servers,
            'components': self._components,
            'security': [{'basic': []}],
        }

        resp = web.Response()
        resp.text = json.dumps(result, indent=True)
        return resp


class Resource(object):

    name = None
    parent = None

    delete = None
    get = None
    post = None
    put = None

    def __init__(
        self, rest, middleware, name, service_config, parent=None,
        delete=None, get=None, post=None, put=None,
    ):
        self.rest = rest
        self.middleware = middleware
        self.name = name
        self.parent = parent
        self.service_config = service_config
        self.__method_params = {}

        path = self.get_path()
        if delete:
            self.delete = delete
        if get:
            self.get = get
        if post:
            self.post = post
        if put:
            self.put = put

        for i in ('delete', 'get', 'post', 'put'):
            operation = getattr(self, i)
            if operation is None:
                continue
            self.rest.app.router.add_route(i.upper(), f'/api/v2.0/{path}', getattr(self, f'on_{i}'))
            self.rest.app.router.add_route(i.upper(), f'/api/v2.0/{path}/', getattr(self, f'on_{i}'))
            self.rest._openapi.add_path(path, i, operation, self.service_config)
            self.__map_method_params(operation)

        self.middleware.logger.trace(f"add route {self.get_path()}")

    def __map_method_params(self, method_name):
        """
        Middleware methods which accepts more than one argument are mapped to a single
        schema of object type.
        For that reason we need to keep track of each parameter and its order
        """
        method = self.rest._methods.get(method_name)
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
                if not self.rest._methods[getattr(self, method)]['no_auth_required']:
                    await authenticate(self.middleware, req)
                kwargs.update(dict(req.match_info))
                return await do(method, req, resp, *args, **kwargs)

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

    async def do(self, http_method, req, resp, **kwargs):
        assert http_method in ('delete', 'get', 'post', 'put')

        methodname = getattr(self, http_method)
        method = self.rest._methods[methodname]
        """
        Arguments for a method can be grabbed from an override method in
        the form of "get_{get,post,put,delete}_args", e.g.:

          def get_post_args(self, req, resp, **kwargs):
              return [await req.json(), True, False]
        """
        get_method_args = getattr(self, 'get_{}_args'.format(http_method), None)
        if get_method_args is not None:
            method_args = get_method_args(req, resp, **kwargs)
        else:
            method_args = []
            if http_method == 'get' and method['filterable']:
                if self.parent and 'id' in kwargs:
                    filterid = kwargs['id']
                    if filterid.isdigit():
                        filterid = int(filterid)
                    extra = {}
                    for key, val in list(req.query.items()):
                        if key.startswith('extra.'):
                            extra[key[len('extra.'):]] = normalize_query_parameter(val)

                    method_args = [
                        [(self.service_config['datastore_primary_key'], '=', filterid)],
                        {'get': True, 'force_sql_filters': True, 'extra': extra}
                    ]
                else:
                    method_args = self._filterable_args(req)

            if not method_args:
                # RFC 7231 specifies that a GET request can accept a payload body
                # This means that all the http methods now ( delete, get, post, put ) accept a payload body
                try:
                    text = await req.text()
                    if not text:
                        method_args = []
                    else:
                        data = await req.json()
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
                                resp.body = json.dumps({
                                    'message': 'Endpoint accepts multiple params, object/dict expected.',
                                })
                                return resp
                            method_args = []
                            for p, options in sorted(params.items(), key=lambda x: x[1]['order']):
                                if p not in data and options['required']:
                                    resp.set_status(400)
                                    resp.body = json.dumps({
                                        'message': f'{p} attribute expected.',
                                    })
                                    return resp
                                elif p in data:
                                    method_args.append(data.pop(p))
                            if data:
                                resp.set_status(400)
                                resp.body = json.dumps({
                                    'message': f'The following attributes are not expected: {", ".join(data.keys())}',
                                })
                                return resp
                except Exception as e:
                    resp.set_status(400)
                    resp.body = json.dumps({
                        'message': str(e),
                    })
                    return resp

        """
        If the method is marked `item_method` then the first argument
        must be the item id (from url param)
        """
        if method.get('item_method') is True:
            method_args.insert(0, kwargs['id'])

        if method.get('pass_application'):
            method_kwargs = {
                'app': Application(req.headers.get('X-Real-Remote-Addr'), req.headers.get('X-Real-Remote-Port'))
            }
        else:
            method_kwargs = {}
        download_pipe = None
        if method['downloadable']:
            download_pipe = self.middleware.pipe()
            method_kwargs['pipes'] = Pipes(output=download_pipe)

        try:
            result = await self.middleware.call(methodname, *method_args, **method_kwargs)
        except CallError as e:
            resp = web.Response(status=422)
            result = {
                'message': e.errmsg,
                'errno': e.errno,
            }
        except (SchemaError, ValidationError, ValidationErrors) as e:
            if isinstance(e, (SchemaError, ValidationError)):
                e = [(e.attribute, e.errmsg, e.errno)]
            result = defaultdict(list)
            for attr, errmsg, errno in e:
                result[attr].append({
                    'message': errmsg,
                    'errno': errno,
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
        resp.text = json.dumps(result, indent=True)
        return resp
