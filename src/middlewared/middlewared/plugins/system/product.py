# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from types import MappingProxyType

from truenas_pylicensed.features import LicenseFeature

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
from middlewared.utils.hardware import get_hardware_class, get_hardware_info
from middlewared.utils.version import parse_version_string

from middlewared.utils.license import LEGACY_LICENSE_FILE, LICENSE_ADDHW_MAPPING, LICENSE_FILE

PRODUCT_NAME = "TrueNAS"
LICENSE_ADDHW_REVERSE_MAPPING = MappingProxyType({v: k for k, v in LICENSE_ADDHW_MAPPING.items()})


class SystemService(Service):

    @api_method(
        SystemProductTypeArgs, SystemProductTypeResult, roles=["SYSTEM_PRODUCT_READ"]
    )
    def product_type(self):
        """Returns the type of the product"""
        if get_hardware_class().is_appliance:
            return ProductType.ENTERPRISE

        return ProductType.COMMUNITY_EDITION

    @private
    def is_ha_capable(self):
        return get_hardware_info().is_ha_capable

    @private
    def sed_enabled(self):
        return self.call_sync2(self.s.truenas.entitlements.check, LicenseFeature.SED).entitled

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

        major = parsed_version.split(".")[0]
        return f"https://www.truenas.com/docs/scale/{major}/gettingstarted/versionnotes"

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
        """The license as the dashboard consumes it.

        A license does not expire, so nothing here reports that it has. The `contract_*`
        keys carry the SUPPORT feature's dates, which is the only expiry a license holds.
        """
        info = self.call_sync2(self.s.truenas.license.info_private)
        if info is None:
            return None

        support = info.feature("SUPPORT")
        result = {
            'model': info.model,
            'system_serial': info.serials[0] if info.serials else None,
            'system_serial_ha': info.serials[1] if len(info.serials) > 1 else None,
            'contract_type': info.contract_type,
            'contract_start': support.start_date if support is not None else None,
            # The 25.10 dashboard reads remote_info.license.contract_end without a null
            # guard, and an upgraded standby's payload is merged into an un-upgraded
            # active's for as long as the operator leaves the active running, so this key
            # stays until no supported upgrade starts on 25.10.
            'contract_end': info.support_expires_at,
            'legacy_contract_hardware': None,
            'legacy_contract_software': None,
            'customer_name': None,
            'features': list(info.features),
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
        removed_in="v26",
    )
    async def feature_enabled(self, name):
        """
        Returns whether the `feature` is enabled or not
        """
        return (await self.call2(self.s.truenas.entitlements.check, name)).entitled
