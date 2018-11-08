import os


from middlewared.schema import accepts, Dict, Int, IPAddr, List, Str
from middlewared.service import private, SystemServiceService, ValidationErrors
from middlewared.validators import Port


class NetDataGlobalConfiguration(SystemServiceService):

    class Config:
        service = 'netdata'
        service_model = 'netdataglobalsettings'
        service_verb = 'restart'
        datastore_prefix = ''
        datastore_extend = 'netdata.configuration.netdata_global_config_extend'
        namespace = 'netdata.configuration'

    @private
    async def netdata_global_config_extend(self, data):
        data['memory_mode'] = data['memory_mode'].upper()
        data['stream_mode'] = data['stream_mode'].upper()
        return data

    @private
    async def list_alarms(self):
        path = '/usr/local/etc/netdata/health.d/'
        files = [
            f for f in os.listdir(path) if 'sample' not in f
        ]
        alarms = {}
        for file in files:
            with open(path + file, 'r') as f:
                data = f.readlines()
                for line in data:
                    if 'alarm:' in line:
                        alarms[line.split(':')[1].strip()] = path + file
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

            param_str = ''
            for i in additional_params.split('\n'):
                i = i.strip()
                if not i:
                    continue
                if i.startswith('#'):
                    # Let's not validate this and write it as it is
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

        bind_to_ip = data.get('bind_to')
        if bind_to_ip:
            if (
                    bind_to_ip not in ['127.0.0.1', '::1'] and not [
                        ip for ip in await self.middleware.call('interfaces.ip_in_use') if ip['address'] == bind_to_ip
                    ]
            ):
                verrors.add(
                    'netdata_update.bind_to',
                    'Please provide a valid bind to ip'
                )
        else:
            verrors.add(
                'netdata_update.bind_to',
                'This field is required'
            )

        update_alarms = data.pop('update_alarms')
        valid_alarms = await self.list_alarms()
        if update_alarms:
            for alarm in update_alarms:
                if alarm not in valid_alarms:
                    verrors.add(
                        'netdata_update.alarms',
                        f'{alarm} not a valid alarm'
                    )
                else:
                    if not isinstance(alarm, str):
                        verrors.add(
                            'netdata_update.alarms',
                            f'{alarm} key must be a string'
                        )
                    if not isinstance(update_alarms[alarm], bool):
                        verrors.add(
                            'netdata_update.alarms',
                            f'{alarm} value can only be boolean'
                        )

        if verrors:
            raise verrors

        # TODO: See what can be done to improve this section - is very crude right now - We are probably not getting
        # templates right now, look into that
        for alarm in valid_alarms:
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
            List('allow_from', items=[Str('pattern')]),  # TODO: See if we can come up with regex to verify this pattern
            Str('api_key'),
            IPAddr('bind_to'),  # TODO: nginx.conf will need to be adjusted accordingly
            Int('bind_to_port', validators=[Port()]),
            List('destination', items=[Str('dest')]),
            Int('history'),
            Int('http_port_listen_backlog'),
            Str('memory_mode', enum=['SAVE', 'MAP', 'RAM', 'NONE']),
            Str('stream_mode', enum=['NONE', 'MASTER', 'SLAVE']),
            Int('update_every')
        )
    )
    async def do_update(self, data):
        old = await self.config()
        new = old.copy()
        # We separate alarms we have in db and the ones user supplies. If alarms are valid, we add them to db, else
        # we keep the old ones
        new['update_alarms'] = data.pop('alarms', {})
        new.update(data)

        new = await self.validate_attrs(new)

        await self._update_service(old, new)

        return await self.config()
