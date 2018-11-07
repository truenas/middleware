async def render(service, middleware):
    netdata_config = await middleware.call('netdata.configuration.config')
    alarms = netdata_config['alarms']
    valid_alarms = await middleware.call('netdata.configuration.list_alarms')
    print('\n\n\nin render')
    for alarm in valid_alarms:
        # These are valid alarms and their respective config files exist as well
        if alarm in alarms:
            with open(valid_alarms[alarm], 'r') as file:
                content = file.readlines()
            # TODO: Execute this efficiently -- improve -- see different approaches
            with open(valid_alarms[alarm], 'w') as file:
                print('\n\n\nwriiting file', valid_alarms[alarm])
                check = False
                for line in content:
                    if 'alarm:' in line:
                        if line.split(':')[1].strip() == alarm:
                            check = True
                        elif check:
                            # This means to: wasn't present in the section of that alarm - let's write it
                            # case - last alarm - this won't work - FIXME
                            file.write(f'      to: {"silent" if not alarms[alarm] else "sysadmin"}\n')
                            check = False

                    if 'to:' in line and check:
                        file.write(f'{line[:line.find(":") + 1]} {"silent" if not alarms[alarm] else "sysadmin"}\n')
                        check = False
                        continue
                    file.write(line)
