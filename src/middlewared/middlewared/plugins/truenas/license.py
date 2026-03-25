import typing

from middlewared.api import api_method
from middlewared.api.current import (
    TrueNASLicenseUploadArgs,
    TrueNASLicenseUploadResult,
    TrueNASLicenseInfoArgs,
    TrueNASLicenseInfoResult,
)
from middlewared.service import Service

from .license_utils import upload_license, get_license_info


class TrueNASLicenseService(Service):
    class Config:
        namespace = "truenas.license"
        cli_private = True

    @api_method(
        TrueNASLicenseUploadArgs,
        TrueNASLicenseUploadResult,
        roles=["FULL_ADMIN"],
    )
    def upload(self, license_: str) -> None:
        """Upload a PEM-wrapped license file."""
        upload_license(license_)
        self.middleware.call_sync("failover.send_small_file", "/data/truenas/license")

    @api_method(
        TrueNASLicenseInfoArgs,
        TrueNASLicenseInfoResult,
        roles=["READONLY_ADMIN"],
    )
    def info(self) -> dict[str, typing.Any] | None:
        """Returns the parsed license object, or null if no license exists."""
        return get_license_info()
