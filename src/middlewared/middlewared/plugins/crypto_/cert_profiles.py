from middlewared.api import api_method
from middlewared.api.current import (
    CertProfilesArgs,
    CertProfilesResult,
    CSRProfilesArgs,
    CSRProfilesResult,
)
from middlewared.service import Service


class CertificateService(Service):
    @api_method(CertProfilesArgs, CertProfilesResult, roles=["CERTIFICATE_READ"])
    async def profiles(self):
        """
        Returns a dictionary of predefined configuration
        options for creating certificates.
        """
        return CertProfilesResult.model_dump()

    @api_method(CSRProfilesArgs, CSRProfilesResult, roles=["CERTIFICATE_READ"])
    async def certificate_signing_requests_profiles(self):
        """
        Returns a dictionary of predefined configuration
        options for creating certificate signing requests.
        """
        return CSRProfilesResult.model_dump()
