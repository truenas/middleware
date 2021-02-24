from .base import Authenticator
from .factory import auth_factory


class Route53Authenticator(Authenticator):

    NAME = 'route53'

    def perform(self, *args, **kwargs):
        raise NotImplementedError

    def cleanup(self, *args, **kwargs):
        raise NotImplementedError


auth_factory.register(Route53Authenticator)
