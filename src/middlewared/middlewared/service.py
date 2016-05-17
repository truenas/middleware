import re

CONFIG_NAMES = ('namespace', )


class Config(object):

    def __init__(self, cls, meta):
        namespace = cls.__name__
        if namespace.endswith('Service'):
            namespace = namespace[:-7]
        self.namespace = self._camel_to_dotted(namespace)
        if meta:
            for key, val in meta.__dict__.items():
                if key in CONFIG_NAMES:
                    setattr(self, key, val)

    def _camel_to_dotted(self, name):
        return re.sub(r'([a-z])([A-Z])', '\\1.\\2', name).lower()


class ServiceBase(type):

    def __new__(cls, name, bases, attrs):
        super_new = super(ServiceBase, cls).__new__
        if name == 'Service' and bases == ():
            return super_new(cls, name, bases, attrs)

        meta = attrs.pop('Meta', None)
        klass = super_new(cls, name, bases, attrs)
        klass._meta = Config(klass, meta)
        return klass


class Service(object):
    __metaclass__ = ServiceBase

    def __init__(self, middleware):
        self.middleware = middleware
