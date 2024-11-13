from middlewared.service import Service

from .client_utils import get_acme_client_and_key


class ACMEService(Service):

    class Config:
        namespace = 'acme'
        private = True

    def get_acme_client_and_key_payload(self, acme_directory_uri, tos=False):
        data = self.middleware.call_sync('acme.registration.query', [['directory', '=', acme_directory_uri]])
        if not data:
            data = self.middleware.call_sync(
                'acme.registration.create',
                {'tos': tos, 'acme_directory_uri': acme_directory_uri}
            )
        else:
            data = data[0]

        return data

    def get_acme_client_and_key(self, acme_directory_uri, tos=False):
        return get_acme_client_and_key(self.get_acme_client_and_key_payload(acme_directory_uri, tos))
