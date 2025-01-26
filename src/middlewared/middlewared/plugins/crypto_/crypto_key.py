from middlewared.api import api_method
from middlewared.api.current import (
    CryptoKeyGenerateCertificateArgs, CryptoKeyGenerateCertificateResult, CryptoKeyGenerateSelfSignedCAArgs,
    CryptoKeyGenerateSelfSignedCAResult, CryptoKeyGenerateCAArgs, CryptoKeyGenerateCAResult, CryptoKeySignCSRWithCAArgs,
    CryptoKeySignCSRWithCAResult,
)
from middlewared.service import Service

from .generate_ca import generate_certificate_authority
from .generate_certs import generate_certificate
from .generate_self_signed import generate_self_signed_certificate
from .generate_utils import normalize_san, sign_csr_with_ca


class CryptoKeyService(Service):

    class Config:
        private = True

    def normalize_san(self, san_list):
        return normalize_san(san_list)

    def generate_self_signed_certificate(self):
        return generate_self_signed_certificate()

    @api_method(CryptoKeyGenerateCertificateArgs, CryptoKeyGenerateCertificateResult, private=True)
    def generate_certificate(self, data):
        return generate_certificate(data)

    @api_method(CryptoKeyGenerateSelfSignedCAArgs, CryptoKeyGenerateSelfSignedCAResult, private=True)
    def generate_self_signed_ca(self, data):
        return self.generate_certificate_authority(data)

    @api_method(CryptoKeyGenerateCAArgs, CryptoKeyGenerateCAResult, private=True)
    def generate_certificate_authority(self, data):
        return generate_certificate_authority(data)

    @api_method(CryptoKeySignCSRWithCAArgs, CryptoKeySignCSRWithCAResult, private=True)
    def sign_csr_with_ca(self, data):
        return sign_csr_with_ca(data)
