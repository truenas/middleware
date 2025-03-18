from truenas_crypto_utils.read import load_certificate, load_certificate_request

from middlewared.schema import accepts, Str
from middlewared.service import Service


class CryptoKeyService(Service):

    class Config:
        private = True

    @accepts(Str('certificate', required=True, max_length=None))
    def load_certificate(self, certificate):
        return load_certificate(certificate)

    @accepts(Str('csr', required=True, max_length=None))
    def load_certificate_request(self, csr):
        return load_certificate_request(csr)
