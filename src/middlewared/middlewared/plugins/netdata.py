import copy
import os
import re


from middlewared.schema import accepts, Bool, Dict, Int, List, Str
from middlewared.service import private, SystemServiceService, ValidationErrors
from middlewared.validators import IpAddress, Port, Unique, UUID, validate_attributes


class NetDataService(SystemServiceService):

    READ_HEALTH_DIRECTORY = '/usr/local/lib/netdata/conf.d/health.d/'
    WRITE_HEALTH_DIRECTORY = '/usr/local/etc/netdata/health.d'

    class Config:
        service = 'netdata'
        service_model = 'netdataglobalsettings'
        service_verb = 'restart'
        datastore_extend = 'netdata.netdata_extend'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._alarms = {}
        self._initialize_alarms()

    @private
    async def netdata_extend(self, data):
        # We get data alarms as a dict e.g
        # {"alarms": {"alarm1": {"enabled": True}, "alarm2": {"enabled": True}}}
        alarms = copy.deepcopy(self._alarms)
        alarms.update(data['alarms'])
        data['alarms'] = alarms
        for alarm in data['alarms']:
            # Remove conf file paths
            data['alarms'][alarm].pop('read_path', None)
            data['alarms'][alarm].pop('write_path', None)
        return data

    @accepts()
    async def ips(self):
        """
        Returns a list of user configured addresses with which netdata can be accessed.
        """
        ips = []
        for ip in (await self.config())['bind']:
            if ip == '0.0.0.0':
                ips.extend([
                    f'http://{d["address"]}/netdata/'
                    for d in await self.middleware.call('interface.ip_in_use', {'ipv4': True})
                ])
            elif ip == '::':
                ips.extend([
                    f'http://{d["address"]}/netdata/'
                    for d in await self.middleware.call('interface.ip_in_use', {'ipv6': True})
                ])
            else:
                ips.append(f'http://{ip}/netdata/')
        return ips

    @private
    async def list_alarms(self):
        alarms = copy.deepcopy(self._alarms)
        config = await self.config()
        for alarm in config['alarms']:
            if alarm not in alarms:
                # An unlikely case when a previously configured alarm does not exist in conf files anymore
                alarms[alarm] = {}
            alarms[alarm]['enabled'] = config['alarms'][alarm]['enabled']

        return alarms

    @private
    def _initialize_alarms(self):
        pattern = re.compile(r'alarm: +(.*)(?:[\s\S]*?os: +(.*)\n)?')

        for file in [f for f in os.listdir(self.READ_HEALTH_DIRECTORY) if 'sample' not in f]:
            path = os.path.join(self.READ_HEALTH_DIRECTORY, file)
            with open(path, 'r') as f:
                for alarm in re.findall(pattern, f.read()):
                    # By default all alarms are enabled in netdata
                    # When we list alarms, alarms which have been configured by user to be disabled
                    # will show up as disabled only
                    if 'freebsd' in alarm[1] or not alarm[1]:
                        self._alarms[alarm[0].strip()] = {
                            'read_path': path,
                            'enabled': True,
                            'write_path': os.path.join(self.WRITE_HEALTH_DIRECTORY, file)
                        }

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

        bind_to_ips = data.get('bind')
        if bind_to_ips:
            valid_ips = [ip['address'] for ip in await self.middleware.call('interface.ip_in_use')]
            valid_ips.extend(['127.0.0.1', '::1', '0.0.0.0', '::'])

            for bind_ip in bind_to_ips:
                if bind_ip not in valid_ips:
                    verrors.add(
                        'netdata_update.bind',
                        f'Invalid {bind_ip} bind IP'
                    )
        else:
            verrors.add(
                'netdata_update.bind',
                'This field is required'
            )

        update_alarms = data.pop('update_alarms', {})
        valid_alarms = self._alarms
        if update_alarms:
            for alarm in update_alarms:
                if alarm not in valid_alarms:
                    verrors.add(
                        'netdata_update.alarms',
                        f'{alarm} not a valid alarm'
                    )

            verrors.extend(
                validate_attributes(
                    [Dict(key, Bool('enabled', required=True)) for key in update_alarms],
                    {'attributes': update_alarms}
                )
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

            destinations = data.get('destination')
            if destinations:
                ip_addr = IpAddress()
                port = Port()
                for dest in destinations:
                    ip = dest.split(':')[0]
                    try:
                        ip_addr(ip)
                    except ValueError as e:
                        verrors.add(
                            'netdata_update.destination',
                            str(e)
                        )
                    else:
                        if ':' in dest:
                            try:
                                port(int(dest.split(':')[1]))
                            except ValueError as e:
                                verrors.add(
                                    'netdata_update.destination',
                                    f'Not a valid port: {e}'
                                )
        elif stream_mode == 'MASTER':
            for key in ('allow_from', 'api_key'):
                if not data.get(key):
                    verrors.add(
                        f'netdata_update.{key}',
                        f'{key} is required with stream mode as MASTER'
                    )

        verrors.check()

        data['alarms'].update(update_alarms)

        return data

    @accepts(
        Dict(
            'netdata_update',
            Str('additional_params', max_length=None),
            Dict(
                'alarms',
                additional_attrs=True
            ),
            List('allow_from', items=[Str('pattern')]),
            Str('api_key', validators=[UUID()]),
            List('bind', validators=[Unique()], items=[Str('bind_ip')]),
            Int('port', validators=[Port()]),
            List('destination', validators=[Unique()], items=[Str('destination')]),
            Int('history'),
            Int('http_port_listen_backlog'),
            Str('stream_mode', enum=['NONE', 'MASTER', 'SLAVE']),
            Int('update_every'),
            update=True
        )
    )
    async def do_update(self, data):
        """
        Update Netdata Service Configuration

        `alarms` is a dictionary where user specifies a key,value pair with key being alarm name and value is a
        dictionary which is of the schema "{'enabled': True}" indicating should the alarm be enabled or not.
        Middlewared supports interacting (changing) alarms in /usr/local/etc/netdata/health.d/ directory.

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
                        "used_swap": {"enabled": true},
                        "ram_in_swap": {"enabled": true}
                    }
                }]
            }
        """
        old = await self.config()
        new = old.copy()
        # We separate alarms we have in db and the ones user supplies
        new['update_alarms'] = data.pop('alarms', {})
        new.update(data)

        new = await self.validate_attrs(new)

        # If port value is updated, we don't restart nginx, that has to be done manually
        await self._update_service(old, new)

        return await self.config()
