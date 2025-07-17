import asyncio
import errno
import json
import shutil
import tempfile
import time

import aiohttp
import requests

from licenselib.utils import proactive_support_allowed
from middlewared.api import api_method
from middlewared.api.current import (
    SupportEntry, SupportAttachTicketArgs, SupportAttachTicketResult, SupportAttachTicketMaxSizeArgs,
    SupportAttachTicketMaxSizeResult, SupportFieldsArgs, SupportFieldsResult, SupportIsAvailableArgs,
    SupportIsAvailableResult, SupportIsAvailableAndEnabledArgs, SupportIsAvailableAndEnabledResult,
    SupportNewTicketArgs, SupportNewTicketResult, SupportSimilarIssuesArgs, SupportSimilarIssuesResult,
    SupportUpdateArgs, SupportUpdateResult,
)
from middlewared.pipe import Pipes, InputPipes
from middlewared.plugins.system.utils import DEBUG_MAX_SIZE
from middlewared.service import CallError, ConfigService, job, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils import sw_version
from middlewared.utils.network import INTERNET_TIMEOUT

ADDRESS = 'support-proxy.ixsystems.com'


async def post(url, data, timeout=INTERNET_TIMEOUT):
    try:
        async with asyncio.timeout(timeout):
            async with aiohttp.ClientSession(
                raise_for_status=True, trust_env=True,
            ) as session:
                req = await session.post(url, headers={"Content-Type": "application/json"}, data=data)
    except asyncio.TimeoutError:
        raise CallError('Connection timed out', errno.ETIMEDOUT)
    except aiohttp.ClientResponseError as e:
        raise CallError(f'Invalid server response: {e}', errno.EBADMSG)

    try:
        return await req.json()
    except aiohttp.client_exceptions.ContentTypeError:
        raise CallError(f'Invalid server response: {req.status}', errno.EBADMSG)


class SupportModel(sa.Model):
    __tablename__ = 'system_support'

    id = sa.Column(sa.Integer(), primary_key=True)
    enabled = sa.Column(sa.Boolean(), nullable=True, default=True)
    name = sa.Column(sa.String(200))
    title = sa.Column(sa.String(200))
    email = sa.Column(sa.String(200))
    phone = sa.Column(sa.String(200))
    secondary_name = sa.Column(sa.String(200))
    secondary_title = sa.Column(sa.String(200))
    secondary_email = sa.Column(sa.String(200))
    secondary_phone = sa.Column(sa.String(200))


class SupportService(ConfigService):

    class Config:
        datastore = 'system.support'
        cli_namespace = 'system.support'
        role_prefix = 'SUPPORT'
        entry = SupportEntry

    @api_method(SupportUpdateArgs, SupportUpdateResult)
    async def do_update(self, data):
        """
        Update Proactive Support settings.
        """

        config_data = await self.config()
        config_data.update(data)

        verrors = ValidationErrors()
        if config_data['enabled']:
            for key in ['name', 'title', 'email', 'phone']:
                for prefix in ['', 'secondary_']:
                    field = prefix + key
                    if not config_data[field]:
                        verrors.add(f'support_update.{field}', 'This field is required')
        verrors.check()

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            config_data['id'],
            config_data,
        )

        return await self.config()

    @api_method(SupportIsAvailableArgs, SupportIsAvailableResult, roles=['SUPPORT_READ'])
    async def is_available(self):
        """
        Returns whether Proactive Support is available for this product type and current license.
        """

        if await self.middleware.call('system.vendor.name'):
            return False

        if not await self.middleware.call('system.is_enterprise'):
            return False

        license_ = await self.middleware.call('system.license')
        if license_ is None:
            return False

        return proactive_support_allowed(license_['contract_type'])

    @api_method(SupportIsAvailableAndEnabledArgs, SupportIsAvailableAndEnabledResult, roles=['SUPPORT_READ'])
    async def is_available_and_enabled(self):
        """
        Returns whether Proactive Support is available and enabled.
        """

        return await self.is_available() and bool((await self.config())['enabled'])

    @api_method(SupportFieldsArgs, SupportFieldsResult, roles=['SUPPORT_READ'])
    async def fields(self):
        """
        Returns list of pairs of field names and field titles for Proactive Support.
        """
        return [
            ['name', 'Contact Name'],
            ['title', 'Contact Title'],
            ['email', 'Contact E-mail'],
            ['phone', 'Contact Phone'],
            ['secondary_name', 'Secondary Contact Name'],
            ['secondary_title', 'Secondary Contact Title'],
            ['secondary_email', 'Secondary Contact E-mail'],
            ['secondary_phone', 'Secondary Contact Phone'],
        ]

    @api_method(SupportSimilarIssuesArgs, SupportSimilarIssuesResult, roles=['SUPPORT_READ'])
    async def similar_issues(self, query):
        await self.middleware.call('network.general.will_perform_activity', 'support')

        data = await post(
            f'https://{ADDRESS}/freenas/api/v1.0/similar_issues',
            data=json.dumps({
                'query': query,
            }),
        )

        if 'error' in data:
            raise CallError(data['message'], errno.EINVAL)

        return data

    @api_method(SupportNewTicketArgs, SupportNewTicketResult, roles=['SUPPORT_WRITE', 'READONLY_ADMIN'])
    @job()
    async def new_ticket(self, job, data):
        """
        Creates a new ticket for support.
        This is done using the support proxy API.
        For TrueNAS Community Edition it will be created on JIRA and for TrueNAS Enterprise on Salesforce.

        For Community Edition, `criticality`, `environment`, `phone`, `name`, and `email` attributes are not required.
        For Enterprise, `token` and `type` attributes are not required.
        """
        vendor = await self.middleware.call('system.vendor.name')
        if vendor:
            raise CallError(f'Support is not available for this product ({vendor})', errno.EINVAL)

        if await self.middleware.call('system.experimental'):
            raise CallError('This TrueNAS build is experimental', errno.EINVAL)

        await self.middleware.call('network.general.will_perform_activity', 'support')

        job.set_progress(1, 'Gathering data')

        sw_name = 'freenas' if not await self.middleware.call('system.is_enterprise') else 'truenas'

        if sw_name == 'freenas':
            required_attrs = ('type', 'token')
        else:
            required_attrs = ('category', 'phone', 'name', 'email', 'criticality', 'environment')
            data['serial'] = (await self.middleware.call('system.dmidecode_info'))['system-serial-number']
            license_ = await self.middleware.call('system.license')
            if license_:
                data['company'] = license_['customer_name']
            else:
                data['company'] = 'Unknown'

        for i in required_attrs:
            if i not in data:
                raise CallError(f'{i} is required', errno.EINVAL)

        data['version'] = sw_version()
        debug = data.pop('attach_debug')

        type_ = data.get('type')
        if type_:
            data['type'] = type_.lower()

        job.set_progress(20, 'Submitting ticket')

        result = await post(
            f'https://{ADDRESS}/{sw_name}/api/v1.0/ticket',
            data=json.dumps(data),
        )
        if result['error']:
            raise CallError(result['message'], errno.EINVAL)

        ticket = result.get('ticketnum')
        url = result.get('message')
        if not ticket:
            raise CallError('New ticket number was not informed', errno.EINVAL)
        job.set_progress(50, f'Ticket created: {ticket}', extra={'ticket': ticket})

        has_debug = False
        if debug:
            job.set_progress(60, 'Generating debug file')

            debug_job = await self.middleware.call(
                'system.debug', pipes=Pipes(output=self.middleware.pipe()),
            )

            if await self.middleware.call('failover.licensed'):
                debug_name = 'debug-{}.tar'.format(time.strftime('%Y%m%d%H%M%S'))
            else:
                debug_name = 'debug-{}-{}.txz'.format(
                    (await self.middleware.call('system.hostname')).split('.')[0],
                    time.strftime('%Y%m%d%H%M%S'),
                )

            with tempfile.NamedTemporaryFile("w+b") as f:
                def copy1():
                    nonlocal has_debug
                    try:
                        rbytes = 0
                        while True:
                            r = debug_job.pipes.output.r.read(1048576)
                            if r == b'':
                                break

                            rbytes += len(r)
                            if rbytes > DEBUG_MAX_SIZE * 1048576:
                                return

                            f.write(r)

                        f.seek(0)
                        has_debug = True
                    finally:
                        debug_job.pipes.output.r.read()

                await self.middleware.run_in_thread(copy1)
                await debug_job.wait()

                if has_debug:
                    job.set_progress(80, 'Attaching debug file')

                    t = {
                        'ticket': ticket,
                        'filename': debug_name,
                    }
                    if 'token' in data:
                        t['token'] = data['token']
                    tjob = await self.middleware.call(
                        'support.attach_ticket', t, pipes=Pipes(inputs=InputPipes(self.middleware.pipe())),
                    )

                    def copy2():
                        try:
                            shutil.copyfileobj(f, tjob.pipes.input.w)
                        finally:
                            tjob.pipes.input.w.close()

                    await self.middleware.run_in_thread(copy2)
                    await tjob.wait()
        else:
            job.set_progress(100)

        return {
            'ticket': ticket,
            'url': url,
            'has_debug': has_debug,
        }

    @api_method(SupportAttachTicketArgs, SupportAttachTicketResult, roles=['SUPPORT_WRITE', 'READONLY_ADMIN'])
    @job(pipes=["input"])
    def attach_ticket(self, job, data):
        """
        Method to attach a file to an existing ticket.
        """

        self.middleware.call_sync('network.general.will_perform_activity', 'support')

        sw_name = 'freenas' if not self.middleware.call_sync('system.is_enterprise') else 'truenas'

        data['ticketnum'] = data.pop('ticket')
        filename = data.pop('filename')

        try:
            r = requests.post(
                f'https://{ADDRESS}/{sw_name}/api/v1.0/ticket/attachment',
                data=data,
                timeout=300,
                files={'file': (filename, job.pipes.input.r)},
            )
        except requests.ConnectionError as e:
            raise CallError(f'Connection error {e}', errno.EBADF)
        except requests.Timeout:
            raise CallError('Connection time out', errno.ETIMEDOUT)

        if r.status_code == 413:
            raise CallError(f'Uploaded file is too large', errno.EFBIG)

        try:
            data = r.json()
        except ValueError:
            self.logger.debug(f'Failed to decode ticket attachment response: {r.text}')
            raise CallError(f'Invalid server response: {r.status_code}', errno.EBADMSG)

        if data['error']:
            raise CallError(data['message'], errno.EINVAL)

    @api_method(SupportAttachTicketMaxSizeArgs, SupportAttachTicketMaxSizeResult, roles=['SUPPORT_READ'])
    async def attach_ticket_max_size(self):
        """
        Returns maximum uploaded file size for `support.attach_ticket`
        """
        return DEBUG_MAX_SIZE


async def setup(middleware):
    await middleware.call('network.general.register_activity', 'support', 'Support')
