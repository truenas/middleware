import asyncio
from datetime import datetime, timedelta
import json
import os

import aiohttp

from licenselib.license import ContractType

from freenasUI.support.utils import get_license, ADDRESS, LICENSE_FILE

from middlewared.schema import accepts, Bool, Dict, Int, Str
from middlewared.service import Service, private

EULA_PENDING_PATH = "/data/truenas_license.pending"
REGISTER_URL = "https://%s/truenas/api/v1.0/register" % ADDRESS

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

    __send_customer_information_task = None

    @accepts()
    async def get_chassis_hardware(self):
        # FIXME: bring code from notifier
        return await self.middleware.call('notifier.get_chassis_hardware')

    async def is_eula_accepted(self):
        return not os.path.exists(EULA_PENDING_PATH)

    async def accept_eula(self):
        if os.path.exists(EULA_PENDING_PATH):
            os.unlink(EULA_PENDING_PATH)

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

        await self.schedule_sending_customer_information()

        return customer_information

    async def schedule_sending_customer_information(self):
        customer_information = await self.__fetch_customer_information()

        if customer_information["data"] is None:
            self.logger.debug("Customer information is not filled yet")
            return

        if customer_information["sent_at"] is not None:
            self.logger.debug("Customer information is already sent")
            return

        task = self.__send_customer_information_task
        if task is not None:
            self.logger.debug("Aborting current send_customer_information task")
            task.abort()

        self.__send_customer_information_task = asyncio.ensure_future(
            self.__send_customer_information(customer_information))

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

    async def __send_customer_information(self, customer_information):
        sleep = 60
        while True:
            try:
                with open(LICENSE_FILE, 'r') as f:
                    license_key = f.read().strip('\n')

                data = dict(customer_information["data"], **{
                    "system_serial": get_license()[0].system_serial,
                    "license_key": license_key,
                })

                await asyncio.wait_for(self.__do_send_customer_information(data), 30)
            except Exception:
                self.logger.debug("Exception while sending customer data", exc_info=True)
            else:
                self.logger.debug("Customer information sent successfully")
                break

            await asyncio.sleep(sleep)
            sleep = min(sleep * 2, 3600)

        await self.middleware.call('datastore.update', 'truenas.customerinformation', customer_information["id"], {
            "sent_at": datetime.utcnow(),
        })

    async def __do_send_customer_information(self, data):
        async with aiohttp.ClientSession(headers={"Content-type": "application/json"}) as session:
            async with session.request("post", REGISTER_URL, data=json.dumps(data)) as response:
                if response.status != 200:
                    raise Exception("HTTP Error", response.status, await response.text())

                result = await response.json()
                if result["error"]:
                    raise ValueError(result["message"])


def setup(middleware):
    asyncio.ensure_future(middleware.call('truenas.schedule_sending_customer_information'))
