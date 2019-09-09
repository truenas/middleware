#!/usr/bin/env python
import importlib

spec = importlib.util.spec_from_file_location(
    'failover', '/usr/local/lib/middlewared_truenas/plugins/failover.py',
)
failover = importlib.util.module_from_spec(spec)
spec.loader.exec_module(failover)


def main():
    print(':'.join(str(i) for i in failover.FailoverService._ha_mode()))


if __name__ == '__main__':
    main()
