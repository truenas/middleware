from middlewared.service import CallError, ValidationErrors


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

    def perform(self, domain, validation_name, validation_content):
        try:
            self._perform(domain, validation_name, validation_content)
        except Exception as e:
            raise CallError(f'Failed to perform {self.NAME} challenge for {domain!r} domain: {e}')

    def _perform(self, domain, validation_name, validation_content):
        raise NotImplementedError

    def cleanup(self, domain, validation_name, validation_content):
        try:
            self.cleanup(domain, validation_name, validation_content)
        except Exception as e:
            raise CallError(f'Failed to cleanup {self.NAME} challenge for {domain!r} domain: {e}')

    def _cleanup(self, domain, validation_name, validation_content):
        raise NotImplementedError
