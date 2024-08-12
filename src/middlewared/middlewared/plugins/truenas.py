import errno
import json
import os
from datetime import timedelta

from ixhardware import TRUENAS_UNKNOWN, get_chassis_hardware

from middlewared.plugins.truecommand.enums import Status as TrueCommandStatus
from middlewared.schema import accepts, Bool, Dict, Patch, returns, Str
from middlewared.service import cli_private, job, no_auth_required, private, Service
from middlewared.utils.functools_ import cache
from middlewared.utils.time_utils import time_now
import middlewared.sqlalchemy as sa

EULA_FILE = '/usr/local/share/truenas/eula.html'
EULA_PENDING_PATH = "/data/truenas-eula-pending"
user_attrs = [
    Str('first_name'),
    Str('last_name'),
    Str('title'),
    Str('office_phone'),
    Str('mobile_phone'),
    Str('primary_email'),
    Str('secondary_email'),
    Str('address'),
    Str('city'),
    Str('state'),
    Str('zip'),
    Str('country'),
]


class TruenasCustomerInformationModel(sa.Model):
    __tablename__ = 'truenas_customerinformation'

    id = sa.Column(sa.Integer(), primary_key=True)
    data = sa.Column(sa.Text())
    updated_at = sa.Column(sa.DateTime())
    sent_at = sa.Column(sa.DateTime(), nullable=True)
    form_dismissed = sa.Column(sa.Boolean())


class TrueNASService(Service):

    class Config:
        cli_namespace = 'system.truenas'

    @no_auth_required
    @accepts()
    @returns(Bool())
    async def managed_by_truecommand(self):
        """
        Returns whether TrueNAS is being managed by TrueCommand or not.

        This endpoint has no authentication required as it is used by UI when the user has not logged in to see
        if the system is being managed by TrueCommand or not.
        """
        return TrueCommandStatus(
            (await self.middleware.call('truecommand.config'))['status']
        ) == TrueCommandStatus.CONNECTED

    @accepts()
    @returns(Str('system_chassis_hardware'))
    @cli_private
    @cache
    async def get_chassis_hardware(self):
        """
        Returns what type of hardware this is, detected from dmidecode.
        """
        dmi = await self.middleware.call('system.dmidecode_info_internal')
        return get_chassis_hardware(dmi)

    @accepts(roles=['READONLY_ADMIN'])
    @returns(Bool('is_ix_hardware'))
    async def is_ix_hardware(self):
        """
        Return a boolean value on whether this is hardware that iXsystems sells.
        """
        return await self.get_chassis_hardware() != TRUENAS_UNKNOWN

    @accepts(roles=['READONLY_ADMIN'])
    @returns(Str('eula', max_length=None, null=True))
    @cli_private
    def get_eula(self):
        """
        Returns the TrueNAS End-User License Agreement (EULA).
        """
        if not os.path.exists(EULA_FILE):
            return
        with open(EULA_FILE, 'r', encoding='utf8') as f:
            return f.read()

    @accepts(roles=['READONLY_ADMIN'])
    @returns(Bool('system_eula_accepted'))
    @cli_private
    def is_eula_accepted(self):
        """
        Returns whether the EULA is accepted or not.
        """
        return not os.path.exists(EULA_PENDING_PATH)

    @accepts()
    @returns()
    def accept_eula(self):
        """
        Accept TrueNAS EULA.
        """
        try:
            os.unlink(EULA_PENDING_PATH)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise

    @private
    def unaccept_eula(self):
        with open(EULA_PENDING_PATH, "w") as f:
            os.fchmod(f.fileno(), 0o600)

    # TODO: Document this please
    @accepts()
    async def get_customer_information(self):
        """
        Returns stored customer information.
        """
        result = await self.__fetch_customer_information()
        return result

    @accepts(Dict(
        'customer_information_update',
        Str('company'),
        Dict('administrative_user', *user_attrs),
        Dict('technical_user', *user_attrs),
        Dict(
            'reseller',
            Str('company'),
            Str('first_name'),
            Str('last_name'),
            Str('title'),
            Str('office_phone'),
            Str('mobile_phone'),
        ),
        Dict(
            'physical_location',
            Str('address'),
            Str('city'),
            Str('state'),
            Str('zip'),
            Str('country'),
            Str('contact_name'),
            Str('contact_phone_number'),
            Str('contact_email'),
        ),
        Str('primary_use_case'),
        Str('other_primary_use_case'),
    ))
    async def update_customer_information(self, data):
        """
        Updates customer information.
        """
        customer_information = await self.__fetch_customer_information()

        await self.middleware.call('datastore.update', 'truenas.customerinformation', customer_information["id"], {
            "data": json.dumps(data),
            "updated_at": time_now(),
        })

        return customer_information

    async def __fetch_customer_information(self):
        result = await self.middleware.call('datastore.config', 'truenas.customerinformation')
        result["immutable_data"] = await self.__fetch_customer_information_immutable_data()
        result["data"] = json.loads(result["data"])
        result["needs_update"] = time_now() - result["updated_at"] > timedelta(days=365)
        return result

    async def __fetch_customer_information_immutable_data(self):
        license_ = await self.middleware.call('system.license')
        if license_ is None:
            return None

        return {
            "serial_number": license_['system_serial'],
            "serial_number_ha": license_['system_serial_ha'],
            "support_level": license_['contract_type'].title(),
            "support_start_date": license_['contract_start'].isoformat(),
            "support_end_date": license_['contract_end'].isoformat(),
        }

    @accepts(roles=['READONLY_ADMIN'])
    @returns(Bool('is_production_system'))
    async def is_production(self):
        """
        Returns if system is marked as production.
        """
        return await self.middleware.call('keyvalue.get', 'truenas:production', False)

    @accepts(Bool('production'), Bool('attach_debug', default=False))
    @returns(Patch(
        'new_ticket_response', 'set_production',
        ('attr', {'null': True}),
    ))
    @job()
    async def set_production(self, job, production, attach_debug):
        """
        Sets system production state and optionally sends initial debug.
        """
        was_production = await self.is_production()
        await self.middleware.call('keyvalue.set', 'truenas:production', production)

        if not was_production and production:
            serial = (await self.middleware.call('system.dmidecode_info'))["system-serial-number"]
            return await job.wrap(await self.middleware.call('support.new_ticket', {
                "title": f"System has been just put into production ({serial})",
                "body": "This system has been just put into production",
                "attach_debug": attach_debug,
                "category": "Installation/Setup",
                "criticality": "Inquiry",
                "environment": "Production",
                "name": "Automatic Alert",
                "email": "auto-support@ixsystems.com",
                "phone": "-",
            }))
