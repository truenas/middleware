def host_config(middleware):
    config = middleware.call_sync('network.configuration.config')
    yield f'hostname="{config["hostname"]}.{config["domain"]}"'

    if config['ipv4gateway']:
        yield f'defaultrouter="{config["ipv4gateway"]}"'

    if config['ipv6gateway']:
        yield f'ipv6_defaultrouter="{config["ipv6gateway"]}"'

    if config['netwait_enabled']:
        yield 'netwait_enable="YES"'
        if not config['netwait_ip']:
            if config['ipv4gateway']:
                config['netwait_ip'] = config['ipv4gateway']
            elif config['ipv6gateway']:
                config['netwait_ip'] = config['ipv6gateway']
        yield f'netwait_ip="{config["netwait_ip"]}"'


def render(service, middleware):

    rcs = []
    for i in (
        host_config,
    ):
        rcs += list(i(middleware))

    with open('/etc/rc.conf.freenas', 'w') as f:
        f.write('\n'.join(rcs) + '\n')
