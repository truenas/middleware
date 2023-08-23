import textwrap


def render(service, middleware):
    with open('/usr/lib/netdata/conf.d/python.d.conf', 'w') as f:
        f.write(textwrap.dedent('''
        enabled: yes
        default_run: no
        cputemp: yes
        smart_log: yes
        k3s_stats: yes
        '''))
