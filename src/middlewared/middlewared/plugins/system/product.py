import os

from datetime import date
from licenselib.license import ContractType, Features, License
from pathlib import Path

from middlewared.schema import accepts, Bool, returns, Str
from middlewared.service import CallError, no_auth_required, private, Service
from middlewared.utils import sw_version, sw_version_is_stable
from middlewared.utils.license import LICENSE_ADDHW_MAPPING


LICENSE_FILE = '/data/license'


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
            if await self.middleware.call('failover.hardware') != 'MANUAL':
                # HA capable hardware
                SystemService.PRODUCT_TYPE = 'SCALE_ENTERPRISE'
            else:
                if license := await self.middleware.call('system.license'):
                    if license['model'].lower().startswith('freenas'):
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

    @accepts()
    @returns(Str('truenas_version'))
    def version(self):
        """
        Returns software version of the system.
        """
        return sw_version()

    @accepts()
    @returns(Str('is_stable'))
    def is_stable(self):
        """
        Returns whether software version of the system is stable.
        """
        return sw_version_is_stable()

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
    async def license(self):
        return await self.middleware.run_in_thread(self._get_license)

    @staticmethod
    def _get_license():
        if not os.path.exists(LICENSE_FILE):
            return

        with open(LICENSE_FILE, 'r') as f:
            license_file = f.read().strip('\n')

        try:
            licenseobj = License.load(license_file)
        except Exception:
            return

        license = {
            "model": licenseobj.model,
            "system_serial": licenseobj.system_serial,
            "system_serial_ha": licenseobj.system_serial_ha,
            "contract_type": ContractType(licenseobj.contract_type).name.upper(),
            "contract_start": licenseobj.contract_start,
            "contract_end": licenseobj.contract_end,
            "legacy_contract_hardware": (
                licenseobj.contract_hardware.name.upper()
                if licenseobj.contract_type == ContractType.legacy
                else None
            ),
            "legacy_contract_software": (
                licenseobj.contract_software.name.upper()
                if licenseobj.contract_type == ContractType.legacy
                else None
            ),
            "customer_name": licenseobj.customer_name,
            "expired": licenseobj.expired,
            "features": [],
            "addhw": licenseobj.addhw,
            "addhw_detail": [
                f"{quantity} × " + (f"{LICENSE_ADDHW_MAPPING[code]} Expansion shelf" if code in LICENSE_ADDHW_MAPPING
                                    else f"<Unknown hardware {code}>")
                for quantity, code in licenseobj.addhw
            ],
        }
        for feature in licenseobj.features:
            license["features"].append(feature.name.upper())
        # Licenses issued before 2017-04-14 had a bug in the feature bit
        # for fibre channel, which means they were issued having
        # dedup+jails instead.
        if (
            Features.fibrechannel not in licenseobj.features and licenseobj.contract_start < date(2017, 4, 14) and
            Features.dedup in licenseobj.features and Features.jails in licenseobj.features
        ):
            license["features"].append(Features.fibrechannel.name.upper())
        return license

    @private
    def license_path(self):
        return LICENSE_FILE

    @accepts(Str('license'))
    @returns()
    def license_update(self, license):
        """
        Update license file.
        """
        try:
            License.load(license)
        except Exception:
            raise CallError('This is not a valid license.')

        prev_product_type = self.middleware.call_sync('system.product_type')

        with open(LICENSE_FILE, 'w+') as f:
            f.write(license)

        self.middleware.call_sync('etc.generate', 'rc')

        SystemService.PRODUCT_TYPE = None
        if self.middleware.call_sync('system.is_enterprise'):
            Path('/data/truenas-eula-pending').touch(exist_ok=True)
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
        license = await self.middleware.call('system.license')
        if license and name in license['features']:
            return True
        return False

    @private
    async def is_ix_hardware(self):
        product = (await self.middleware.call('system.dmidecode_info'))['system-product-name']
        return product is not None and product.startswith(('FREENAS-', 'TRUENAS-'))

    @private
    async def is_enterprise_ix_hardware(self):
        return await self.middleware.call('truenas.get_chassis_hardware') != 'TRUENAS-UNKNOWN'


async def hook_license_update(middleware, prev_product_type, *args, **kwargs):
    if prev_product_type != 'ENTERPRISE' and await middleware.call('system.product_type') == 'ENTERPRISE':
        await middleware.call('system.advanced.update', {'autotune': True})


async def setup(middleware):
    middleware.register_hook('system.post_license_update', hook_license_update)
