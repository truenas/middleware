#!/usr/bin/python3
from collections import deque
from time import time, sleep
from sys import exit

from pyudev import Context, Monitor, MonitorObserver

DQ = deque(maxlen=2)


def callback(dev):
    if uuid := dev.get('ID_PART_ENTRY_UUID'):
        DQ.append({'time': time(), 'name': dev.sys_name, 'uuid': uuid, 'action': dev.action})


def get_observer():
    ctx = Context()
    mon = Monitor.from_netlink(ctx)
    mon.filter_by(subsystem='block')

    return MonitorObserver(mon, callback=callback)


def main(max_wait=600.0, interval=5.0):
    """
    `max_wait`: float representing the total time (in seconds) we should block
        and wait for disk events.
    `interval`: float representing the time we sleep between each iteration to
        allow new disk events to come in.
    """
    obs = get_observer()
    obs.start()  # start background thread

    last_event = dict()
    while max_wait > 0:
        max_wait -= round(interval, 2)
        sleep(interval)

        try:
            event = DQ[-1]
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
