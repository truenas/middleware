# Copyright (c) 2019 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from datetime import datetime, timedelta
import errno
import json
import os

from middlewared.schema import accepts, Bool, Dict, Str
from middlewared.service import job, private, Service
import middlewared.sqlalchemy as sa
from middlewared.utils import run

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

    @accepts()
    async def get_chassis_hardware(self):
        """
        Returns what type of hardware this is, detected from dmidecode.

        TRUENAS-X10-HA-D
        TRUENAS-X10-S
        TRUENAS-X20-HA-D
        TRUENAS-X20-S
        TRUENAS-M40-HA
        TRUENAS-M40-S
        TRUENAS-M50-HA
        TRUENAS-M50-S
        TRUENAS-M60-HA
        TRUENAS-M60-S
        TRUENAS-Z20-S
        TRUENAS-Z20-HA-D
        TRUENAS-Z30-HA-D
        TRUENAS-Z30-S
        TRUENAS-Z35-HA-D
        TRUENAS-Z35-S
        TRUENAS-Z50-HA-D
        TRUENAS-Z50-S

        Nothing in dmidecode but a M, X or Z class machine:
        (Note this means production didn't burn the hardware model
        into SMBIOS. We can detect this case by looking at the
        motherboard)
        TRUENAS-M
        TRUENAS-X
        TRUENAS-Z

        Detected by the motherboard model:
        TRUENAS-SBB

        Pretty much anything else with a SM X8 board:
        (X8DTH was popular but there are a few other boards out there)
        TRUENAS-SM

        Really NFI about hardware at this point.  TrueNAS on a Dell?
        TRUENAS-UNKNOWN
        """

        chassis = await run('dmidecode', '-s', 'system-product-name', check=False)
        chassis = chassis.stdout.decode(errors='ignore').split('\n', 1)[0].strip()
        if chassis == 'TRUENAS-MINI':
            return 'TRUENAS-UNKNOWN'
        if chassis.startswith(('TRUENAS-M', 'TRUENAS-X', 'TRUENAS-Z')):
            return chassis
        # We don't match a burned in name for a M, X or Z series.  Let's catch
        # the case where we are a M, X or Z. (shame on you production!)
        motherboard = await run('dmidecode', '-s', 'baseboard-manufacturer', check=False)
        motherboard = motherboard.stdout.decode(errors='ignore').split('\n', 1)[0].strip()
        motherboard_model = await run('dmidecode', '-s', 'baseboard-product-name', check=False)
        motherboard_model = motherboard_model.stdout.decode(errors='ignore').split('\n', 1)[0].strip()
        if motherboard_model == 'X11DPi-NT' or motherboard_model == 'X11SPi-TF':
            return 'TRUENAS-M'
        if motherboard_model == 'iXsystems TrueNAS X10':
            return 'TRUENAS-X'
        if motherboard == 'GIGABYTE':
            return 'TRUENAS-Z'

        # Are we an SBB?  We can tell this because all SBBs used
        # the same motherboard: X8DTS
        if motherboard_model == 'X8DTS':
            return 'TRUENAS-SBB'

        # Most likely we are an X8DTH at this point, but there are some
        # unicorns that used various X8 boards, so we're going to make
        # allowances
        if motherboard_model.startswith('X8'):
            return 'TRUENAS-SM'

        # Give up
        return 'TRUENAS-UNKNOWN'

    @accepts()
    def get_eula(self):
        """
        Returns the TrueNAS End-User License Agreement (EULA).
        """
        if not os.path.exists(EULA_FILE):
            return
        with open(EULA_FILE, 'r', encoding='utf8') as f:
            return f.read()

    @accepts()
    async def is_eula_accepted(self):
        """
        Returns whether the EULA is accepted or not.
        """
        return not os.path.exists(EULA_PENDING_PATH)

    @accepts()
    async def accept_eula(self):
        """
        Accept TrueNAS EULA.
        """
        try:
            os.unlink(EULA_PENDING_PATH)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise

    @private
    async def unaccept_eula(self):
        with open(EULA_PENDING_PATH, "w"):
            pass

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
            "updated_at": datetime.utcnow(),
        })

        return customer_information

    async def __fetch_customer_information(self):
        result = await self.middleware.call('datastore.config', 'truenas.customerinformation')
        result["immutable_data"] = await self.__fetch_customer_information_immutable_data()
        result["data"] = json.loads(result["data"])
        result["needs_update"] = datetime.utcnow() - result["updated_at"] > timedelta(days=365)
        return result

    async def __fetch_customer_information_immutable_data(self):
        license = (await self.middleware.call('system.info'))['license']
        if license is None:
            return None

        return {
            "serial_number": license['system_serial'],
            "serial_number_ha": license['system_serial_ha'],
            "support_level": license['contract_type'].title(),
            "support_start_date": license['contract_start'].isoformat(),
            "support_end_date": license['contract_end'].isoformat(),
        }

    @accepts()
    async def is_production(self):
        """
        Returns if system is marked as production.
        """
        return await self.middleware.call('keyvalue.get', 'truenas:production', False)

    @accepts(Bool('production'), Bool('attach_debug', default=False))
    @job()
    async def set_production(self, job, production, attach_debug):
        """
        Sets system production state and optionally sends initial debug.
        """
        was_production = await self.is_production()
        await self.middleware.call('keyvalue.set', 'truenas:production', production)

        if not was_production and production:
            serial = (await self.middleware.call('system.info'))["system_serial"]
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
