# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import os
from datetime import date

from licenselib.license import ContractType, Features, License
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
from middlewared.plugins.truenas import EULA_PENDING_PATH
from middlewared.service import CallError, private, Service, ValidationError
from middlewared.utils import ProductType, sw_info
from middlewared.utils.license import LICENSE_ADDHW_MAPPING
from middlewared.utils.version import parse_version_string


LICENSE_FILE = '/data/license'
LICENSE_FILE_MODE = 0o600
PRODUCT_NAME = 'TrueNAS'


class SystemService(Service):

    PRODUCT_TYPE = None

    @api_method(
        SystemProductTypeArgs,
        SystemProductTypeResult,
        roles=['SYSTEM_PRODUCT_READ']
    )
    async def product_type(self):
        """Returns the type of the product"""
        if SystemService.PRODUCT_TYPE is None:
            if await self.is_ha_capable():
                # HA capable hardware
                SystemService.PRODUCT_TYPE = ProductType.ENTERPRISE
            else:
                if license_ := await self.middleware.call('system.license'):
                    if license_['model'].lower().startswith('freenas'):
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
        return await self.middleware.call('failover.hardware') != 'MANUAL'

    @private
    async def is_enterprise(self):
        return await self.middleware.call('system.product_type') == ProductType.ENTERPRISE

    @private
    async def sed_enabled(self):
        return await self.is_enterprise() and await self.feature_enabled('SED')

    @api_method(
        SystemVersionShortArgs,
        SystemVersionShortResult,
        authorization_required=False,
    )
    def version_short(self):
        """Returns the short name of the software version of the system."""
        return sw_info()['version']

    @api_method(
        SystemReleaseNotesUrlArgs,
        SystemReleaseNotesUrlResult,
        roles=['SYSTEM_PRODUCT_READ']
    )
    def release_notes_url(self, version_str):
        """Returns the release notes URL for a version of SCALE.

        `version_str` str: represents a version to check against

        If `version` is not provided, then the release notes URL will return
            a link for the currently installed version of SCALE.
        """
        parsed_version = parse_version_string(version_str or self.version_short())
        if parsed_version is None:
            raise CallError(f'Invalid version string specified: {version_str}')

        version_split = parsed_version.split('.')
        major_version = '.'.join(version_split[0:2])
        base_url = f'https://www.truenas.com/docs/scale/{major_version}/gettingstarted/scalereleasenotes'
        if len(version_split) == 2:
            return base_url
        else:
            return f'{base_url}/#{"".join(version_split)}'

    @api_method(
        SystemVersionArgs,
        SystemVersionResult,
        authorization_required=False,
    )
    def version(self):
        """Returns the full name of the software version of the system."""
        return sw_info()['fullname']

    @private
    async def platform(self):
        return 'LINUX'

    @private
    def license(self, include_raw_license: bool = False):
        return self._get_license(include_raw_license=include_raw_license)

    @staticmethod
    def _get_license(include_raw_license: bool = False):
        try:
            with open(LICENSE_FILE) as f:
                raw_license = f.read().strip('\n')
                licenseobj = License.load(raw_license)
        except Exception:
            return

        license_ = {
            'model': licenseobj.model,
            'system_serial': licenseobj.system_serial,
            'system_serial_ha': licenseobj.system_serial_ha,
            'contract_type': ContractType(licenseobj.contract_type).name.upper(),
            'contract_start': licenseobj.contract_start,
            'contract_end': licenseobj.contract_end,
            'legacy_contract_hardware': (
                licenseobj.contract_hardware.name.upper()
                if licenseobj.contract_type == ContractType.legacy
                else None
            ),
            'legacy_contract_software': (
                licenseobj.contract_software.name.upper()
                if licenseobj.contract_type == ContractType.legacy
                else None
            ),
            'customer_name': licenseobj.customer_name,
            'expired': licenseobj.expired,
            'features': [i.name.upper() for i in licenseobj.features],
            'addhw': licenseobj.addhw,
            'addhw_detail': [],
        }

        for quantity, code in licenseobj.addhw:
            try:
                license_['addhw_detail'].append(f'{quantity} x {LICENSE_ADDHW_MAPPING[code]} Expansion shelf')
            except KeyError:
                license_['addhw_detail'].append(f'<Unknown hardware {code}>')

        if Features.fibrechannel not in licenseobj.features and licenseobj.contract_start < date(2017, 4, 14):
            # Licenses issued before 2017-04-14 had a bug in the feature bit for fibrechannel, which
            # means they were issued having dedup+jails instead.
            if Features.dedup in licenseobj.features and Features.jails in licenseobj.features:
                license_['features'].append(Features.fibrechannel.name.upper())

        if include_raw_license:
            license_['raw_license'] = raw_license

        return license_

    @private
    def license_path(self):
        return LICENSE_FILE

    @api_method(
        SystemLicenseUpdateArgs,
        SystemLicenseUpdateResult,
        roles=['SYSTEM_PRODUCT_WRITE']
    )
    def license_update(self, license_):
        """Update license file"""
        try:
            dser_license = License.load(license_)
        except Exception:
            raise ValidationError('system.license', 'This is not a valid license.')
        else:
            if dser_license.system_serial_ha:
                if not self.middleware.call_sync('system.is_ha_capable'):
                    raise ValidationError('system.license', 'This is not an HA capable system.')

        prev_license = self.middleware.call_sync('system.license')
        with open(LICENSE_FILE, 'w+') as f:
            f.write(license_)
            os.fchmod(f.fileno(), LICENSE_FILE_MODE)

        self.middleware.call_sync('etc.generate', 'rc')
        SystemService.PRODUCT_TYPE = None
        if self.middleware.call_sync('system.is_enterprise'):
            with open(EULA_PENDING_PATH, 'a+') as f:
                os.fchmod(f.fileno(), 0o600)

        self.middleware.call_sync('alert.alert_source_clear_run', 'LicenseStatus')
        self.middleware.call_sync('failover.configure.license', dser_license)
        self.middleware.run_coroutine(
            self.middleware.call_hook('system.post_license_update', prev_license=prev_license), wait=False,
        )

    @api_method(
        SystemFeatureEnabledArgs,
        SystemFeatureEnabledResult,
        roles=['SYSTEM_PRODUCT_READ'],
    )
    async def feature_enabled(self, name):
        """
        Returns whether the `feature` is enabled or not
        """
        license_ = await self.middleware.call('system.license')
        if license_ and name in license_['features']:
            return True
        return False


async def hook_license_update(middleware, prev_license, *args, **kwargs):
    if prev_license is None and await middleware.call('system.product_type') == 'ENTERPRISE':
        await middleware.call('system.advanced.update', {'autotune': True})


async def setup(middleware):
    middleware.register_hook('system.post_license_update', hook_license_update)
