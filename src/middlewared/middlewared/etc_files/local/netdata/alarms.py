async def render(service, middleware):
    def update_alarms(alarms, valid_alarms):
        for alarm in valid_alarms:

            # These are valid alarms and their respective config files exist as well
            if alarm in alarms:
                with open(valid_alarms[alarm], 'r') as f:
                    content = f.readlines()

                with open(valid_alarms[alarm], 'w') as f:
                    check = False
                    for line in content:
                        if any(i in line for i in ('alarm:', 'template:')):
                            # A new entity is starting
                            if line.split(':')[1].strip() == alarm:
                                check = True
                            elif check:
                                # This means to: wasn't present in the section of that alarm - let's write it
                                f.write(f'      to: {"silent" if not alarms[alarm] else "sysadmin"}\n')
                                check = False

                        if 'to:' in line and check:
                            f.write(f'{line[:line.find(":") + 1]} {"silent" if not alarms[alarm] else "sysadmin"}\n')
                            check = False
                            continue
                        f.write(line)

                    if check:
                        # For last alarm cases - is this ideal ?
                        f.write(f'      to: {"silent" if not alarms[alarm] else "sysadmin"}\n')

    alarms = (await middleware.call('netdata.config'))['alarms']
    valid_alarms = await middleware.call('netdata.list_alarms')

    await middleware.run_in_thread(update_alarms, alarms, valid_alarms)
