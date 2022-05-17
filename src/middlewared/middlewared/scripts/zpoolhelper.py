#!/usr/bin/python3
from collections import deque
from time import time, sleep
from sys import exit

from pyudev import Context, Monitor, MonitorObserver

dq = deque()


def callback(dev):
    t = time()
    if uuid := dev.get('ID_PART_ENTRY_UUID'):
        dq.append({'time': t, 'name': dev.sys_name, 'uuid': uuid, 'action': dev.action})


def get_observer():
    ctx = Context()
    mon = Monitor.from_netlink(ctx)
    mon.filter_by('block')
    return MonitorObserver(mon, callback=callback)


def main():
    obs = get_observer(dq)
    obs.start()  # start background thread

    max_time_to_wait = 600  # total time to wait in seconds
    interval = 5  # seconds to sleep before checking for new event
    last_event = {}
    while max_time_to_wait > 0:
        max_time_to_wait -= interval
        sleep(interval)

        try:
            event = dq[-1]
        except IndexError:
            # no events received
            break
        else:
            if event == last_event:
                # we've waited 5 seconds and no more events have come in
                break
            else:
                last_event = event

    obs.send_stop()  # clean up background thread (non-blocking)


if __name__ == '__main__':
    try:
        main()
    finally:
        exit(0)  # always exit success (for now)
