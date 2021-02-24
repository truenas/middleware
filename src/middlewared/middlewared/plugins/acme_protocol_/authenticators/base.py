from middlewared.service import ValidationErrors


class Authenticator:

    NAME = NotImplementedError

    def __init__(self, attributes):
        self.attributes = attributes
        self.initialize_credentials()
        self.validate_credentials()

    def initialize_credentials(self):
        pass

    def validate_credentials(self):
        verrors = ValidationErrors()
        self._validate_credentials(verrors)
        verrors.check()

    def _validate_credentials(self, verrors):
        pass

    def perform(self, domain, challenge, key):
        raise NotImplementedError

    def cleanup(self, *args, **kwargs):
        raise NotImplementedError
