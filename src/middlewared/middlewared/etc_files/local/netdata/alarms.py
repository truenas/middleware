import re


async def render(service, middleware):
    def update_alarms(alarms):
        for key, alarm in alarms.items():

            # These are valid alarms and their respective config files exist as well
            if alarm.get('path'):
                with open(alarm['path'], 'r+') as f:
                    content = f.read()
                    f.seek(0)
                    f.write(
                        re.sub(
                            fr'(alarm: {key}[\s\S]*?to: )(.*)',
                            fr'\1{"silent" if not alarm["enabled"] else "sysadmin"}',
                            content
                        )
                    )
                    f.truncate()
            else:
                middleware.logger.debug(f'Could not find config file for {key} alarm')

    alarms = await middleware.call('netdata.list_alarms')

    await middleware.run_in_thread(update_alarms, alarms)
