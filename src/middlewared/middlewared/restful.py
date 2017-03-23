from aiohttp import web
from collections import defaultdict

import base64
import binascii

from .client import ejson as json


def authenticate(middleware, req):

    auth = req.headers.get('Authorization')
    if auth is None or not auth.startswith('Basic '):
        raise web.HTTPUnauthorized()
    try:
        username, password = base64.b64decode(auth[6:]).decode('utf8').split(':', 1)
    except binascii.Error:
        raise web.HTTPUnauthorized()

    try:
        if not middleware.call('auth.check_user', username, password):
            raise web.HTTPUnauthorized()
    except web.HTTPUnauthorized:
        raise
    except Exception as e:
        raise web.HTTPUnauthorized()


class RESTfulAPI(object):

    def __init__(self, middleware, app):
        self.middleware = middleware
        self.app = app

        # Keep methods cached for future lookups
        self._methods = {}
        self._methods_by_service = defaultdict(dict)
        for methodname, method in list(self.middleware.call('core.get_methods').items()):
            self._methods[methodname] = method
            self._methods_by_service[methodname.rsplit('.', 1)[0]][methodname] = method

        self.register_resources()

    def get_app(self):
        return self.app

    def register_resources(self):
        for name, service in list(self.middleware.call('core.get_services').items()):

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
                kwargs['post'] = '{}.create'.format(name)
                blacklist_methods.extend(list(kwargs.values()))
            elif service['type'] == 'config':
                kwargs['get'] = '{}.config'.format(name)
                kwargs['put'] = '{}.update'.format(name)
                blacklist_methods.extend(list(kwargs.values()))

            service_resource = Resource(self, self.middleware, name.replace('.', '/'), **kwargs)

            """
            For CRUD services we also need a direct subresource so we can
            operate on items in the entity, e.g. update or delete "john" of user namespace.
            """
            subresource = None
            if service['type'] == 'crud':
                kwargs = {
                    'delete': '{}.delete'.format(name),
                    'put': '{}.update'.format(name),
                }
                blacklist_methods.extend(list(kwargs.values()))
                subresource = Resource(self, self.middleware, 'id/{id}', parent=service_resource, **kwargs)

            for methodname, method in list(self._methods_by_service[name].items()):
                if methodname in blacklist_methods:
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
                Resource(self, self.middleware, short_methodname, parent=parent, **res_kwargs)


class Resource(object):

    name = None
    parent = None

    delete = None
    get = None
    post = None
    put = None

    def __init__(
        self, rest, middleware, name, parent=None,
        delete=None, get=None, post=None, put=None,
    ):
        self.rest = rest
        self.middleware = middleware
        self.name = name
        self.parent = parent

        if delete:
            self.delete = delete
            self.rest.app.router.add_route('DELETE', '/api/v2.0/' + self.get_path(), self.on_delete)
        if get:
            self.get = get
            self.rest.app.router.add_route('GET', '/api/v2.0/' + self.get_path(), self.on_get)
        if post:
            self.post = post
            self.rest.app.router.add_route('POST', '/api/v2.0/' + self.get_path(), self.on_post)
        if put:
            self.put = put
            self.rest.app.router.add_route('PUT', '/api/v2.0/' + self.get_path(), self.on_put)

        self.middleware.logger.debug("add route {}".format(self.get_path()))

    def __getattr__(self, attr):
        if attr in ('on_get', 'on_post', 'on_delete', 'on_put'):
            do = object.__getattribute__(self, 'do')
            method = attr.split('_')[-1]

            if object.__getattribute__(self, method) is None:
                return None

            async def on_method(req, *args, **kwargs):
                resp = web.Response()
                authenticate(self.middleware, req)
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

        return [filters, options]

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
            if http_method in ('post', 'put'):
                try:
                    method_args = await req.json()
                except Exception:
                    method_args = []
            elif http_method == 'get' and method['filterable']:
                method_args = self._filterable_args(req)
            else:
                method_args = []

        """
        If the method is marked `item_method` then the first argument
        must be the item id (from url param)
        """
        if method.get('item_method') is True:
            method_args.insert(0, kwargs['id'])

        resp.text = json.dumps(self.middleware.call(methodname, *method_args), indent=True)
        return resp
