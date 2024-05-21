# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import os

from datetime import date
from licenselib.license import ContractType, Features, License
from pathlib import Path

from middlewared.schema import accepts, Bool, returns, Str
from middlewared.service import no_auth_required, no_authz_required, private, Service, ValidationError
from middlewared.utils import sw_info
from middlewared.utils.license import LICENSE_ADDHW_MAPPING


LICENSE_FILE = '/data/license'
LICENSE_FILE_MODE = 0o600


class SystemService(Service):

    PRODUCT_TYPE = None

    @no_auth_required
    @accepts()
    @returns(Bool('system_is_truenas_core'))
    async def is_freenas(self):
        """
        FreeNAS is now TrueNAS CORE.

        DEPRECATED: Use `system.product_type`
        """
        return (await self.product_type()) == 'CORE'

    @no_auth_required
    @accepts()
    @returns(Str('product_type'))
    async def product_type(self):
        """
        Returns the type of the product.

        SCALE - TrueNAS SCALE, community version
        SCALE_ENTERPRISE - TrueNAS SCALE Enterprise, appliance version
        """
        if SystemService.PRODUCT_TYPE is None:
            if await self.is_ha_capable():
                # HA capable hardware
                SystemService.PRODUCT_TYPE = 'SCALE_ENTERPRISE'
            else:
                if license_ := await self.middleware.call('system.license'):
                    if license_['model'].lower().startswith('freenas'):
                        # legacy freenas certified
                        SystemService.PRODUCT_TYPE = 'SCALE'
                    else:
                        # the license has been issued for a "certified" line
                        # of hardware which is considered enterprise
                        SystemService.PRODUCT_TYPE = 'SCALE_ENTERPRISE'
                else:
                    # no license
                    SystemService.PRODUCT_TYPE = 'SCALE'

        return SystemService.PRODUCT_TYPE

    @private
    async def is_ha_capable(self):
        return await self.middleware.call('failover.hardware') != 'MANUAL'

    @private
    async def is_enterprise(self):
        return await self.middleware.call('system.product_type') == 'SCALE_ENTERPRISE'

    @no_auth_required
    @accepts()
    @returns(Str('product_name'))
    async def product_name(self):
        """
        Returns name of the product we are using.
        """
        return "TrueNAS"

    @no_authz_required
    @accepts()
    @returns(Str('truenas_version_shortname'))
    def version_short(self):
        """Returns the short name of the software version of the system."""
        return sw_info()['version']

    @accepts(Str('version_str', default=None, required=False))
    @returns(Str('truenas_release_notes_url', null=True))
    def release_notes_url(self, version_str):
        """Returns the release notes URL for a version of SCALE.

        `version_str` str: represents a version to check against

        If `version` is not provided, then the release notes URL will return
            a link for the currently installed version of SCALE.
        """
        to_format = self.version_short() if version_str is None else version_str
        to_format = to_format.split('-')[0].split('.')  # looks like ['23', '10', '0', '1']
        len_to_format = len(to_format)
        if len_to_format >= 2:
            maj_vers = '.'.join(to_format[0:2])
            base_url = f'https://www.truenas.com/docs/scale/{maj_vers}/gettingstarted/scalereleasenotes'
            if len_to_format == 2:
                return base_url
            else:
                return f'{base_url}/#{"".join(to_format)}'

    @no_authz_required
    @accepts()
    @returns(Str('truenas_version'))
    def version(self):
        """Returns the full name of the software version of the system."""
        return sw_info()['fullname']

    @no_authz_required
    @accepts()
    @returns(Str('is_stable'))
    def is_stable(self):
        """
        Returns whether software version of the system is stable.
        """
        return sw_info()['stable']

    @no_auth_required
    @accepts()
    @returns(Str('product_running_environment', enum=['DEFAULT', 'EC2']))
    async def environment(self):
        """
        Return environment in which product is running. Possible values:
        - DEFAULT
        - EC2
        """
        if os.path.exists('/.ec2'):
            return 'EC2'

        return 'DEFAULT'

    @private
    async def platform(self):
        return 'LINUX'

    @private
    def license(self):
        return self._get_license()

    @staticmethod
    def _get_license():
        try:
            with open(LICENSE_FILE) as f:
                licenseobj = License.load(f.read().strip('\n'))
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

        return license_

    @private
    def license_path(self):
        return LICENSE_FILE

    @accepts(Str('license'))
    @returns()
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

        prev_product_type = self.middleware.call_sync('system.product_type')
        with open(os.open(LICENSE_FILE, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, mode=LICENSE_FILE_MODE), 'w+') as f:
            f.write(license_)

        self.middleware.call_sync('etc.generate', 'rc')
        SystemService.PRODUCT_TYPE = None
        if self.middleware.call_sync('system.is_enterprise'):
            Path('/data/truenas-eula-pending').touch(exist_ok=True)

        self.middleware.call_sync('alert.alert_source_clear_run', 'LicenseStatus')
        self.middleware.call_sync('failover.configure.license', dser_license)
        self.middleware.run_coroutine(
            self.middleware.call_hook('system.post_license_update', prev_product_type=prev_product_type), wait=False,
        )

    @accepts(Str('feature', enum=['DEDUP', 'FIBRECHANNEL', 'VM']))
    @returns(Bool('feature_enabled'))
    async def feature_enabled(self, name):
        """
        Returns whether the `feature` is enabled or not
        """
        is_core = (await self.middleware.call('system.product_type')) == 'CORE'
        if name == 'FIBRECHANNEL' and is_core:
            return False
        elif is_core:
            return True
        license_ = await self.middleware.call('system.license')
        if license_ and name in license_['features']:
            return True
        return False


async def hook_license_update(middleware, prev_product_type, *args, **kwargs):
    if prev_product_type != 'ENTERPRISE' and await middleware.call('system.product_type') == 'ENTERPRISE':
        await middleware.call('system.advanced.update', {'autotune': True})


async def setup(middleware):
    middleware.register_hook('system.post_license_update', hook_license_update)
