class Authenticator:

    NAME = NotImplementedError

    def perform(self, *args, **kwargs):
        raise NotImplementedError

    def cleanup(self, *args, **kwargs):
        raise NotImplementedError
