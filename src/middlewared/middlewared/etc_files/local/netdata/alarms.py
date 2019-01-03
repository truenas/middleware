import os
import re


async def render(service, middleware):
    def update_alarms(alarms):
        for path, alarm_dict in alarms.items():
            if os.path.exists(path):
                with open(path, 'r') as f:
                    content = f.read()

                alarm = None
                for key, alarm in alarm_dict.items():
                    content = re.sub(
                        fr'(alarm: {key}[\s\S]*?to: )(.*)',
                        fr'\1{"silent" if not alarm["enabled"] else "sysadmin"}',
                        content
                    )
                # Better safe then sorry
                if alarm:
                    with open(alarm['write_path'], 'w') as f:
                        f.write(content)

            else:
                middleware.logger.debug(
                    f'Could not find config file {path} for {",".join(list(alarm_dict))} alarm(s)'
                )

    listed_alarms = await middleware.call('netdata.list_alarms')
    alarms = {}
    # Let's not unnecessarily open a single file again and again for reading/writing
    for key, alarm in listed_alarms.items():
        if not alarms.get(alarm.get('read_path')):
            alarms[alarm.get('read_path')] = {}

        alarms[alarm.get('read_path')].update({key: alarm})

    await middleware.run_in_thread(update_alarms, alarms)
