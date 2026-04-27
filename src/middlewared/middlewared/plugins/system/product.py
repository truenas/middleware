# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from datetime import date
from types import MappingProxyType

import truenas_pylicensed

from middlewared.api import api_method
from middlewared.api.current import (
    SystemFeatureEnabledArgs,
    SystemFeatureEnabledResult,
    SystemLicenseUpdateArgs,
    SystemLicenseUpdateResult,
    SystemReleaseNotesUrlArgs,
    SystemReleaseNotesUrlResult,
    SystemProductTypeArgs,
    SystemProductTypeResult,
    SystemVersionArgs,
    SystemVersionResult,
    SystemVersionShortArgs,
    SystemVersionShortResult,
)
from middlewared.service import CallError, private, Service, ValidationError
from middlewared.utils import ProductType, sw_info
from middlewared.utils.version import parse_version_string

from middlewared.plugins.truenas.license_utils import LICENSE_FILE
from middlewared.plugins.truenas.license_legacy_utils import LEGACY_LICENSE_FILE, LICENSE_ADDHW_MAPPING

PRODUCT_NAME = "TrueNAS"
LICENSE_ADDHW_REVERSE_MAPPING = MappingProxyType({v: k for k, v in LICENSE_ADDHW_MAPPING.items()})


class SystemService(Service):
    PRODUCT_TYPE = None

    @api_method(
        SystemProductTypeArgs, SystemProductTypeResult, roles=["SYSTEM_PRODUCT_READ"]
    )
    async def product_type(self):
        """Returns the type of the product"""
        if SystemService.PRODUCT_TYPE is None:
            if await self.is_ha_capable():
                # HA capable hardware
                SystemService.PRODUCT_TYPE = ProductType.ENTERPRISE
            else:
                if license_ := await self.call2(self.s.truenas.license.info_private):
                    if license_.model.lower().startswith("freenas"):
                        # legacy freenas certified
                        SystemService.PRODUCT_TYPE = ProductType.COMMUNITY_EDITION
                    else:
                        # the license has been issued for a "certified" line
                        # of hardware which is considered enterprise
                        SystemService.PRODUCT_TYPE = ProductType.ENTERPRISE
                else:
                    # no license
                    SystemService.PRODUCT_TYPE = ProductType.COMMUNITY_EDITION

        return SystemService.PRODUCT_TYPE

    @private
    async def is_ha_capable(self):
        return await self.middleware.call("failover.hardware") != "MANUAL"

    @private
    async def is_enterprise(self):
        return (
            await self.middleware.call("system.product_type") == ProductType.ENTERPRISE
        )

    @private
    def sed_enabled(self):
        return truenas_pylicensed.is_feature_licensed("SED")

    @api_method(
        SystemVersionShortArgs,
        SystemVersionShortResult,
        authorization_required=False,
    )
    def version_short(self):
        """Returns the short name of the software version of the system."""
        return sw_info().version

    @api_method(
        SystemReleaseNotesUrlArgs,
        SystemReleaseNotesUrlResult,
        roles=["SYSTEM_PRODUCT_READ"],
    )
    def release_notes_url(self, version_str):
        """Returns the release notes URL for a version of SCALE.

        `version_str` str: represents a version to check against

        If `version` is not provided, then the release notes URL will return
            a link for the currently installed version of SCALE.
        """
        parsed_version = parse_version_string(version_str or self.version_short())
        if parsed_version is None:
            raise CallError(f"Invalid version string specified: {version_str}")

        version_split = parsed_version.split(".")
        major_version = ".".join(version_split[0:2])
        base_url = f"https://www.truenas.com/docs/scale/{major_version}/gettingstarted/scalereleasenotes"
        if len(version_split) == 2:
            return base_url
        else:
            return f"{base_url}/#{''.join(version_split)}"

    @api_method(
        SystemVersionArgs,
        SystemVersionResult,
        authorization_required=False,
    )
    def version(self):
        """Returns the full name of the software version of the system."""
        return sw_info().fullname

    @private
    async def platform(self):
        return "LINUX"

    @private
    def license(self, include_raw_license: bool = False):
        info = self.call_sync2(self.s.truenas.license.info_private)
        if info is None:
            return None

        result = {
            'model': info.model,
            'system_serial': info.serials[0] if info.serials else None,
            'system_serial_ha': info.serials[1] if len(info.serials) > 1 else None,
            'contract_type': info.contract_type,
            'contract_start': None,
            'contract_end': info.expires_at,
            'legacy_contract_hardware': None,
            'legacy_contract_software': None,
            'customer_name': None,
            'expired': info.expires_at is not None and info.expires_at < date.today(),
            'features': [f.name for f in info.features],
            'addhw': [],
            'addhw_detail': [],
        }

        for name, quantity in info.enclosures.items():
            result['addhw'].append([quantity, LICENSE_ADDHW_REVERSE_MAPPING.get(name, 0)])
            result['addhw_detail'].append(f'{quantity} x {name} Expansion shelf')

        if include_raw_license:
            for f in [LICENSE_FILE, LEGACY_LICENSE_FILE]:
                try:
                    with open(f) as f:
                        result['raw_license'] = f.read().strip()
                        break
                except FileNotFoundError:
                    pass
            else:
                result['raw_license'] = None

        return result

    @api_method(
        SystemLicenseUpdateArgs,
        SystemLicenseUpdateResult,
        roles=["SYSTEM_PRODUCT_WRITE"],
    )
    def license_update(self, license_):
        """Update license file"""
        raise ValidationError(
            "system.license_update",
            "Legacy license upload is no longer supported. Use truenas.license.upload instead.",
        )

    @api_method(
        SystemFeatureEnabledArgs,
        SystemFeatureEnabledResult,
        roles=["SYSTEM_PRODUCT_READ"],
    )
    async def feature_enabled(self, name):
        """
        Returns whether the `feature` is enabled or not
        """
        info = await self.call2(self.s.truenas.license.info_private)
        if info is not None:
            return any(f.name == name for f in info.features)

        return False


async def hook_license_update(middleware, had_license, *args, **kwargs):
    if not had_license and await middleware.call("system.product_type") == "ENTERPRISE":
        await middleware.call("system.advanced.update", {"autotune": True})


async def setup(middleware):
    middleware.register_hook("system.post_license_update", hook_license_update)
