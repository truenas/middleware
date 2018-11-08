def render(service, middleware):
    alarms = middleware.call_sync('netdata.configuration.config')['alarms']
    valid_alarms = middleware.call_sync('netdata.configuration.list_alarms')
    for alarm in valid_alarms:
        # TODO: See if we can maybe parse these files differently and what pros and cons would that approach have ?
        # These are valid alarms and their respective config files exist as well
        if alarm in alarms:
            with open(valid_alarms[alarm], 'r') as file:
                content = file.readlines()

            with open(valid_alarms[alarm], 'w') as file:
                check = False
                for line in content:
                    if any(i in line for i in ('alarm:', 'template:')):
                        # A new entity is starting
                        if line.split(':')[1].strip() == alarm:
                            check = True
                        elif check:
                            # This means to: wasn't present in the section of that alarm - let's write it
                            file.write(f'      to: {"silent" if not alarms[alarm] else "sysadmin"}\n')
                            check = False

                    if 'to:' in line and check:
                        file.write(f'{line[:line.find(":") + 1]} {"silent" if not alarms[alarm] else "sysadmin"}\n')
                        check = False
                        continue
                    file.write(line)

                if check:
                    # For last alarm cases - is this ideal ?
                    file.write(f'      to: {"silent" if not alarms[alarm] else "sysadmin"}\n')
