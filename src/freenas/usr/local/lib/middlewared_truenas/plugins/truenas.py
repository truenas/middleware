from datetime import datetime, timedelta
import json

from licenselib.license import ContractType

from freenasUI.support.utils import get_license

from middlewared.schema import accepts, Bool, Dict, Int, Str
from middlewared.service import Service

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


class TrueNASService(Service):

    class Config:
        private = True

    @accepts()
    async def get_chassis_hardware(self):
        # FIXME: bring code from notifier
        return await self.middleware.call('notifier.get_chassis_hardware')

    async def get_customer_information(self):
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
        customer_information = await self.__fetch_customer_information()

        await self.middleware.call('datastore.update', 'truenas.customerinformation', customer_information["id"], {
            "data": json.dumps(data),
            "updated_at": datetime.utcnow(),
        })

        return customer_information

    async def dismiss_customer_information_form(self):
        customer_information = await self.__fetch_customer_information()

        await self.middleware.call('datastore.update', 'truenas.customerinformation', customer_information["id"], {
            "form_dismissed": True,
        })

    async def __fetch_customer_information(self):
        result = await self.middleware.call('datastore.config', 'truenas.customerinformation')
        result["immutable_data"] = self.__fetch_customer_information_immutable_data()
        result["data"] = json.loads(result["data"])
        result["needs_update"] = datetime.utcnow() - result["updated_at"] > timedelta(days=365)
        return result

    def __fetch_customer_information_immutable_data(self):
        license = get_license()[0]
        if license is None:
            return None

        return {
            "serial_number": license.system_serial,
            "serial_number_ha": license.system_serial_ha,
            "support_level": ContractType(license.contract_type).name.title(),
            "support_start_date": license.contract_start.isoformat(),
            "support_end_date": license.contract_end.isoformat(),
        }
