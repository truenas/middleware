class Authenticator:

    NAME = NotImplementedError

    def __init__(self, middleware):
        self.middleware = middleware

    def perform(self, *args, **kwargs):
        raise NotImplementedError

    def cleanup(self, *args, **kwargs):
        raise NotImplementedError
