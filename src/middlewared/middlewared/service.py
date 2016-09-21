from collections import defaultdict

import inspect
import logging
import re

from middlewared.schema import accepts, Int, Str


def item_method(fn):
    """Flag method as an item method.
    That means it operates over a single item in the collection,
    by an unique identifier."""
    fn._item_method = True
    return fn


def job(fn):
    """Flag method as a long running job."""
    fn._job = True
    return fn


def no_auth_required(fn):
    """Authentication is not required to use the given method."""
    fn._no_auth_required = True
    return fn


def pass_app(fn):
    """Pass the application instance as parameter to the method."""
    fn._pass_app = True
    return fn


def private(fn):
    """Do not expose method in public API"""
    fn._private = True
    return fn


class ServiceBase(type):

    def __new__(cls, name, bases, attrs):
        super_new = super(ServiceBase, cls).__new__
        if name == 'Service' and bases == ():
            return super_new(cls, name, bases, attrs)

        config = attrs.pop('Config', None)
        klass = super_new(cls, name, bases, attrs)

        namespace = klass.__name__
        if namespace.endswith('Service'):
            namespace = namespace[:-7]
        namespace = namespace.lower()

        config_attrs = {
            'namespace': namespace,
            'private': False,
        }
        if config:
            config_attrs.update({
                k: v
                for k, v in config.__dict__.items() if not k.startswith('_')
            })

        klass._config = type('Config', (), config_attrs)
        return klass


class Service(object):
    __metaclass__ = ServiceBase

    def __init__(self, middleware):
        self.logger = logging.getLogger(type(self).__class__.__name__)
        self.middleware = middleware


class ConfigService(Service):

    def config(self):
        raise NotImplementedError

    def update(self, data):
        return self.do_update(data)


class CRUDService(Service):

    def query(self, filters, options):
        raise NotImplementedError

    def create(self, data):
        return self.do_create(data)

    def update(self, data):
        return self.do_update(data)

    def delete(self, data):
        return self.do_delete(data)


class CoreService(Service):

    @accepts(Int('id', required=False))
    def get_jobs(self, id=None):
        """Get the long running jobs."""
        jobs = self.middleware.get_jobs().all()
        if id:
            job = jobs.get(id)
            return job.__encode__() if job else None
        return [job.__encode__() for job in jobs.itervalues()]

    @accepts()
    def get_services(self):
        """Returns a list of all registered services."""
        services = {}
        for k, v in self.middleware.get_services().items():
            if v._config.private is True:
                continue
            if isinstance(v, CRUDService):
                _typ = 'crud'
            elif isinstance(v, ConfigService):
                _typ = 'config'
            else:
                _typ = 'service'
            services[k] = {
                'config': {k: v for k, v in v._config.__dict__.items() if not k.startswith('_')},
                'type': _typ,
            }
        return services

    @accepts(Str('service'))
    def get_methods(self, service=None):
        """Return methods metadata of every available service.

        `service` parameter is optional and filters the result for a single service."""
        data = {}
        for name, svc in list(self.middleware.get_services().items()):
            if service is not None and name != service:
                continue

            for attr in dir(svc):
                if attr.startswith('_'):
                    continue
                method = getattr(svc, attr)
                if not callable(method):
                    continue

                # Skip private methods
                if hasattr(method, '_private'):
                    continue

                examples = defaultdict(list)
                doc = inspect.getdoc(method)
                if doc:
                    """
                    Allow method docstring to have sections in the format of:

                      .. section_name::

                    Currently the following sections are available:

                      .. examples:: - goes into `__all__` list in examples
                      .. examples(rest):: - goes into `rest` list in examples
                      .. examples(websocket):: - goes into `websocket` list in examples
                    """
                    sections = re.split(r'^.. (.+?)::$', doc, flags=re.M)
                    doc = sections[0]
                    for i in range((len(sections) - 1) / 2):
                        idx = (i + 1) * 2 - 1
                        reg = re.search(r'examples(?:\((.+)\))?', sections[idx])
                        if reg is None:
                            continue
                        exname = reg.groups()[0]
                        if exname is None:
                            exname = '__all__'
                        examples[exname].append(sections[idx + 1])

                accepts = getattr(method, 'accepts', None)
                if accepts:
                    accepts = [i.to_json_schema() for i in accepts]

                data['{0}.{1}'.format(name, attr)] = {
                    'description': doc,
                    'examples': examples,
                    'accepts': accepts,
                    'item_method': hasattr(method, '_item_method'),
                }
        return data
