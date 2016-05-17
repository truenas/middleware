class ServiceBase(type):

    def __new__(cls, name, bases, attrs):
        super_new = super(ServiceBase, cls).__new__
        if name == 'Service' and bases == ():
            return super_new(cls, name, bases, attrs)

        klass = super_new(cls, name, bases, attrs)
        return klass


class Service(object):
    __metaclass__ = ServiceBase

    def __init__(self, middleware):
        self.middleware = middleware
