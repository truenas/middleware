import os
import re


from middlewared.schema import accepts, Bool, Dict, Int, List, Str
from middlewared.service import private, SystemServiceService, ValidationErrors
from middlewared.validators import IpAddress, Port, UUID, validate_attributes


class NetDataService(SystemServiceService):

    class Config:
        service = 'netdata'
        service_model = 'netdataglobalsettings'
        service_verb = 'restart'
        datastore_prefix = ''
        datastore_extend = 'netdata.netdata_global_config_extend'

    @private
    async def netdata_global_config_extend(self, data):
        data['memory_mode'] = data['memory_mode'].upper()
        data['stream_mode'] = data['stream_mode'].upper()
        return data

    @private
    async def list_alarms(self):
        path = '/usr/local/etc/netdata/health.d/'
        alarms = {}
        pattern = re.compile('.*alarm: +(.*)\n')

        for file in [f for f in os.listdir(path) if 'sample' not in f]:
            with open(path + file, 'r') as f:
                for alarm in re.findall(pattern, f.read()):
                    alarms[alarm.strip()] = path + file

        return alarms

    @private
    async def validate_attrs(self, data):
        verrors = ValidationErrors()

        additional_params = data.get('additional_params')
        if additional_params:
            # Let's be very generic here and introduce very basic validation
            # Expected format is as following
            # [ipv6.icmpneighbor]
            #   history = 86400
            #   enabled = yes
            #
            # While we are here, we will also introduce basic formatting to the file to ensure
            # that we can make it as compliable as possible

            param_str = ''
            for i in additional_params.split('\n'):
                i = i.strip()
                if not i:
                    continue
                if i.startswith('#'):
                    # Let's not validate this
                    if i.replace('#', '').startswith('['):
                        param_str += f'\n\n{i}'
                    else:
                        param_str += f'\n\t{i}'

                    continue

                if i.startswith('[') and not i.endswith(']'):
                    verrors.add(
                        'netdata_update.additional_params',
                        f'Please correct format for {i}. i.e [system.intr]'
                    )
                elif not i.startswith('[') and '=' not in i:
                    verrors.add(
                        'netdata_update.additional_params',
                        f'Please correct format for {i}. i.e enabled = yes'
                    )

                if i.startswith('['):
                    param_str += f'\n\n{i}'
                else:
                    param_str += f'\n\t{i}'

            data['additional_params'] = param_str + '\n'
        else:
            # Let's load up the default value for additional params
            # This is sort of a rollback to default configuration if a blank string is provided for
            # additional params - we will default to the defaults of netdata.conf giving users a chance
            # to come back to default configuration if they messed something up pretty bad
            with open('/usr/local/etc/netdata/netdata.conf.sample', 'r') as file:
                try:
                    data['additional_params'] = file.read().split('per plugin configuration')[1]
                except IndexError:
                    self.logger.debug('Failed to set default value for additional params')

        bind_to_ips = data.get('bind_to')
        if bind_to_ips:
            valid_ips = [ip['address'] for ip in await self.middleware.call('interfaces.ip_in_use')]
            valid_ips.extend(['127.0.0.1', '::1', '*'])

            for bind_ip in bind_to_ips:
                if bind_ip not in valid_ips:
                    verrors.add(
                        'netdata_update.bind_to',
                        f'Invalid {bind_ip} bind to IP'
                    )
        else:
            verrors.add(
                'netdata_update.bind_to',
                'This field is required'
            )

        update_alarms = data.pop('update_alarms', {})
        valid_alarms = await self.list_alarms()
        if update_alarms:
            for alarm in update_alarms:
                if alarm not in valid_alarms:
                    verrors.add(
                        'netdata_update.alarms',
                        f'{alarm} not a valid alarm'
                    )

            verrors.extend(
                validate_attributes([Bool(key) for key in update_alarms], {'attributes': update_alarms})
            )

        # Validating streaming metrics now
        stream_mode = data.get('stream_mode')
        if stream_mode == 'SLAVE':
            for key in ('api_key', 'destination'):
                if not data.get(key):
                    verrors.add(
                        f'netdata_update.{key}',
                        f'{key} is required with stream mode as SLAVE'
                    )
        elif stream_mode == 'MASTER':
            for key in ('allow_from', 'api_key'):
                if not data.get(key):
                    verrors.add(
                        f'netdata_update.{key}',
                        f'{key} is required with stream mode as MASTER'
                    )

        verrors.check()

        for alarm in valid_alarms:
            # Let's add alarms to our db if they aren't already there
            if alarm not in data['alarms']:
                data['alarms'][alarm] = True

        for alarm in update_alarms:
            # These are valid alarms
            data['alarms'][alarm] = update_alarms[alarm]

        data['memory_mode'] = data['memory_mode'].lower()
        data['stream_mode'] = data['stream_mode'].lower()

        return data

    @accepts(
        Dict(
            'netdata_update',
            Str('additional_params'),
            Dict(
                'alarms',
                additional_attrs=True
            ),
            List('allow_from', items=[Str('pattern')]),
            Str('api_key', validators=[UUID()]),
            List('bind_to', items=[Str('bind_to_ip')]),
            Int('bind_to_port', validators=[Port()]),
            List('destination', items=[Str('destination', validators=[IpAddress(port=True)])]),
            Int('history'),
            Int('http_port_listen_backlog'),
            Str('memory_mode', enum=['SAVE', 'MAP', 'RAM', 'NONE']),
            Str('stream_mode', enum=['NONE', 'MASTER', 'SLAVE']),
            Int('update_every')
        )
    )
    async def do_update(self, data):
        """
        Update Netdata Service Configuration

        `alarms` is a dictionary where user specifies a key,value pair with key being alarm name and value is a boolean
        value which represents should the alarm be enabled or not. Middlewared supports interacting (changing) alarms
        in /usr/local/etc/netdata/health.d/ directory.

        `allow_from` is used when netdata service is expected to be used as a master. It defaults to "['*']". This field
        expects a list of Netdata patterns which Netdata will use to set restrictions on incoming connections from slave
        accordingly.

        `api_key` is a valid UUID which can be generated in command line by typing uuidgen.

        `destination` is used when netdata service is expected to be used as a slave. Destination is a list of potential
        destinations to which netdata should stream metrics. We expect the format to be IP:PORT ( port is optional ).
        The first working destination is used by Netdata service.

        `history` is the number of entries the netdata daemon will by default keep in memory for each chart dimension.
        It defaults to 86400.

        .. examples(websocket)::

          Update Netdata Service Configuration

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "netdata.update",
                "params": [{
                    "history": 80000,
                    "alarms": {
                        "used_swap": "true",
                        "ram_in_swap": "true"
                    }
                }]
            }
        """
        old = await self.config()
        new = old.copy()
        # We separate alarms we have in db and the ones user supplies. If alarms are valid, we add them to db, else
        # we keep the old ones
        new['update_alarms'] = data.pop('alarms', {})
        new.update(data)

        new = await self.validate_attrs(new)

        # If bind_to ip or port value is updated, we don't restart nginx, that has to be done manually
        await self._update_service(old, new)

        return await self.config()
