import humanfriendly


def get_memory_info() -> dict:
    with open('/proc/meminfo') as f:
        meminfo = {
            s[0]: humanfriendly.parse_size(s[1], binary=True)
            for s in [
                line.split(':', 1)
                for line in f.readlines()
            ]
        }

        return {
            'total': meminfo['MemTotal'],
            'mapped': meminfo['Mapped'],
            'active': meminfo['Active'],
            'inactive': meminfo['Inactive'],
        }
