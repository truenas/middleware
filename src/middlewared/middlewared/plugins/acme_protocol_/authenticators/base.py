class Authenticator:

    NAME = NotImplementedError

    def __init__(self, attributes):
        self.attributes = attributes

    def perform(self, *args, **kwargs):
        raise NotImplementedError

    def cleanup(self, *args, **kwargs):
        raise NotImplementedError
