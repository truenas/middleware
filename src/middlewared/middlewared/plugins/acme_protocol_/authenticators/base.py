from middlewared.service import CallError


class Authenticator:

    NAME = NotImplementedError
    SCHEMA = NotImplementedError

    def __init__(self, attributes):
        self.attributes = attributes
        self.initialize_credentials()

    def initialize_credentials(self):
        pass

    @staticmethod
    def validate_credentials(self, data):
        raise NotImplementedError

    def perform(self, domain, validation_name, validation_content):
        try:
            self._perform(domain, validation_name, validation_content)
        except Exception as e:
            raise CallError(f'Failed to perform {self.NAME} challenge for {domain!r} domain: {e}')

    def _perform(self, domain, validation_name, validation_content):
        raise NotImplementedError

    def cleanup(self, domain, validation_name, validation_content):
        try:
            self._cleanup(domain, validation_name, validation_content)
        except Exception as e:
            raise CallError(f'Failed to cleanup {self.NAME} challenge for {domain!r} domain: {e}')

    def _cleanup(self, domain, validation_name, validation_content):
        raise NotImplementedError
