from middlewared.service import Service

from truenas_crypto_utils.generate_self_signed import generate_self_signed_certificate
from truenas_crypto_utils.generate_utils import normalize_san


class CryptoKeyService(Service):

    class Config:
        private = True

    def normalize_san(self, san_list):
        return normalize_san(san_list)

    def generate_self_signed_certificate(self):
        return generate_self_signed_certificate()
