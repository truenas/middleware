from datetime import datetime

import falcon
import json


class JsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return str(obj)
        return json.JSONEncoder.default(self, obj)


class JSONTranslator(object):

    def process_request(self, req, resp):
        if req.content_length in (None, 0):
            return

        body = req.stream.read()
        if not body:
            return

        if 'application/json' not in req.content_type:
            return

        try:
            req.context['doc'] = json.loads(body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            raise falcon.HTTPError(
                falcon.HTTP_753,
                'Malformed JSON',
                'Could not decode the request body. The JSON was incorrect or '
                'not encoded as UTF-8.'
            )

    def process_response(self, req, resp, resource):
        if 'result' in req.context:
            resp.body = JsonEncoder(indent=True).encode(req.context['result'])


class RESTfulAPI(object):

    def __init__(self, middleware):
        self.middleware = middleware
        self.app = falcon.API(middleware=[
            JSONTranslator(),
        ])
        self.register_resources()

    def get_app(self):
        return self.app

    def register_resources(self):
        for name, service in self.middleware.call('core.get_services').items():

            kwargs = {}
            blacklist_methods = []
            if service['type'] == 'crud':
                kwargs['get'] = '{}.query'.format(name)
                kwargs['post'] = '{}.create'.format(name)
                blacklist_methods.extend([kwargs['get'], kwargs['post']])
            elif service['type'] == 'config':
                kwargs['get'] = '{}.config'.format(name)
                kwargs['put'] = '{}.update'.format(name)
                blacklist_methods.extend([kwargs['get'], kwargs['put']])

            service_resource = Resource(self, self.middleware, name, **kwargs)
            for methodname, method in self.middleware.call('core.get_methods', name).items():
                if methodname in blacklist_methods:
                    continue
                short_methodname = methodname.rsplit('.', 1)[-1]
                Resource(self, self.middleware, short_methodname, parent=service_resource, get=methodname)


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
        if get:
            self.get = get
        if post:
            self.post = post
        if put:
            self.put = put

        self.rest.app.add_route('/api/v2.0/' + self.get_path(), self)
        print "add route", self.get_path()

    def __getattr__(self, attr):
        if attr in ('on_get', 'on_post', 'on_delete', 'on_put'):
            do = object.__getattribute__(self, 'do')
            method = attr.split('_')[-1]

            if object.__getattribute__(self, method) is None:
                return None

            def on_method(req, resp, **kwargs):
                return do(method, req, resp, **kwargs)

            return on_method
        return object.__getattribute__(self, attr)

    def get_path(self):
        path = ''
        parent = self.parent
        while parent is not None:
            path += parent.name + '/'
            parent = parent.parent
        path += self.name
        return path

    def do(self, http_method, req, resp, **kwargs):
        assert http_method in ('delete', 'get', 'post', 'put')

        method = getattr(self, http_method)
        if http_method in ('delete', 'get'):
            req.context['result'] = self.middleware.call(method)
        else:
            req.context['result'] = self.middleware.call(method, *req.context['doc'])
