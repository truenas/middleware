import os
import re

from collections import defaultdict


def render(service, middleware):
    listed_alarms = middleware.call_sync('netdata.list_alarms')
    alarms = defaultdict(dict)
    # Let's not unnecessarily open a single file again and again for reading/writing
    for key, alarm in listed_alarms.items():
        alarms[alarm.get('read_path')].update({key: alarm})

    for path, alarm_dict in alarms.items():
        if os.path.exists(path):
            with open(path, 'r') as f:
                original_content = content = f.read()

            alarm = None
            for key, alarm in alarm_dict.items():
                content = re.sub(
                    fr'(alarm: {key}[\s\S]*?to: )(.*)',
                    fr'\1{"silent" if not alarm["enabled"] else "sysadmin"}',
                    content
                )
            # Better safe than sorry
            if alarm:
                if original_content != content:
                    with open(alarm['write_path'], 'w') as f:
                        f.write(content)
                elif os.path.exists(alarm['write_path']):
                    middleware.logger.debug(
                        f'Removing {alarm["write_path"]} as original content has not changed'
                    )
                    os.remove(alarm['write_path'])

        else:
            middleware.logger.debug(
                f'Could not find config file {path} for {",".join(list(alarm_dict))} alarm(s)'
            )
