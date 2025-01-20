from middlewared.api import api_method
from middlewared.api.current import (
    CAProfilesArgs,
    CAProfilesModel,
    CAProfilesResult,
)
from middlewared.service import Service


class CertificateAuthorityService(Service):
    class Config:
        cli_namespace = "system.certificate.authority"

    @api_method(CAProfilesArgs, CAProfilesResult, roles=["CERTIFICATE_AUTHORITY_READ"])
    async def profiles(self):
        """
        Returns a dictionary of predefined options for
        creating certificate authority requests.
        """
        return CAProfilesModel().model_dump(by_alias=True)
