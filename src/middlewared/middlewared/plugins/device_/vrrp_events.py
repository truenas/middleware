from asyncio import sleep as asyncio_sleep
from dataclasses import dataclass
from collections import deque
from logging import getLogger
from math import floor
from os import mkfifo
from threading import Thread, Event
from time import sleep, time

from middlewared.service import Service
from middlewared.utils.prctl import set_name

LOGGER = getLogger('failover')  # so logs show up in /var/log/failover.log


@dataclass
class VrrpObjs:
    fifo_thread = None
    event_thread = None
    event_queue = None


class VrrpThreadService(Service):
    class Config:
        cli_private = True
        private = True

    def pause_events(self):
        if VrrpObjs.fifo_thread is not None and VrrpObjs.fifo_thread.is_alive():
            VrrpObjs.fifo_thread.pause()
        if VrrpObjs.event_thread is not None and VrrpObjs.event_thread.is_alive():
            VrrpObjs.event_thread.pause()

    def unpause_events(self):
        if VrrpObjs.fifo_thread is not None and VrrpObjs.fifo_thread.is_alive():
            VrrpObjs.fifo_thread.unpause()
        if VrrpObjs.event_thread is not None and VrrpObjs.event_thread.is_alive():
            VrrpObjs.event_thread.unpause()


class VrrpEventThread(Thread):

    def __init__(self, *args, **kwargs):
        super(VrrpEventThread, self).__init__()
        self.middleware = kwargs.get('middleware')
        self.event_queue = kwargs.get('queue')
        self.shutdown_event = Event()
        self.pause_event = Event()
        self.grace_period = 0.5
        self.user_provided_timeout = kwargs.get('timeout') or 2
        self.max_wait = self.user_provided_timeout + self.grace_period
        self.settle_time = (self.max_wait / 2) + self.grace_period
        self.max_rapid_settle_time = 5
        self.rapid_event_settle_time = min(2 * self.user_provided_timeout, self.max_rapid_settle_time)

    def shutdown(self):
        self.shutdown_event.set()

    def format_fifo_msg(self, msg):
        if any((
            not isinstance(msg, dict),
            not msg.get('event'),
            len(msg['event'].split()) != 4,
            not msg.get('time'),
        )):
            LOGGER.error('Ignoring unexpected VRRP event message: %r', msg)
            return

        try:
            info = msg['event'].split()
            ifname = info[1].split('_')[0].strip('"')  # interface
            event = info[2]  # the state that is being transititoned to
        except Exception:
            LOGGER.error('Failed parsing vrrp message', exc_info=True)
            return
        else:
            if event not in ('MASTER', 'BACKUP'):
                return

        return {'ifname': ifname, 'event': event, 'time': msg['time']}

    def pause(self):
        self.pause_event.set()

    def unpause(self):
        self.pause_event.clear()

    @property
    def user_provided_timeout(self):
        return self.__upt

    @user_provided_timeout.setter
    def user_provided_timeout(self, value):
        self.__upt = value

    def run(self):
        set_name('vrrp_event_thread')
        LOGGER.info('vrrp event thread started')
        last_event, backoff = None, False
        while not self.shutdown_event.is_set():
            if self.pause_event.is_set():
                # A BACKUP event has to migrate all the VIPs
                # off of the controller and the only way to
                # do that is to restart the vrrp service.
                # However, restarting the VRRP service triggers
                # more BACKUP events for the other interfaces
                # so we will pause this thread while we become
                # the backup controller and then unpause after
                last_event = None
                self.event_queue.clear()
                sleep(0.2)

            try:
                event = self.event_queue[-1]
                this_event = self.format_fifo_msg(event)
            except IndexError:
                # loop is started but we've received no events
                sleep(0.2)
                continue

            if this_event is None:
                # an event that we ignore (i.e. STOP/FAULT events)
                self.event_queue.pop()
                continue
            elif last_event is None:
                # first event (in the loop) so sleep `max_wait`
                # before we act upon it
                last_event = this_event
                sleep(self.max_wait)
                continue

            # These are the primary scenarios for which we need to handle
            #   1. receive 1 event within `max_wait` period
            #   2. receive 2 events with the most recent event being within
            #       the timeframe of `max_wait`
            #   3. receive 2 events with the most recent event being greater
            #       than the `max_wait` timeframe
            #   4. receive 2+ events with the most recent event being less
            #       than the `max_wait` timeframe (i.e. rapid events)
            #   The first 3 scenarios listed above are easy enough to handle
            #   because we send those messages as-is to be processed. The
            #   last scenario is the situation for which we need to try and
            #   have a "settle" time. If we continue to receive a rapid
            #   succesion of events, then we'll log a message and ignore the
            #   event since it will wreak havoc on the HA system.
            time_diff_floor = floor((this_event['time'] - last_event['time']))
            max_wait_floor = floor(self.max_wait)
            if last_event == this_event or time_diff_floor > max_wait_floor:
                # scenario #1 and scenario #3 listed above
                last_event = None
                backoff = False
                self.event_queue.pop()
                self.middleware.call_hook_sync('vrrp.fifo', data=this_event)
            elif time_diff_floor == max_wait_floor:
                # scenario #2 listed above
                # NOTE:
                # The events looke something like this:
                #   RECEIVED: 'INSTANCE "eno1_v4" BACKUP 254\n' at time: 1701967219.244696
                #   RECEIVED: 'INSTANCE "eno1_v4" MASTER 254\n' at time: 1701967221.2902775
                # In the messages above, the time difference is ~2seconds which is the default
                # timeout for not receiving a MASTER advertisement before VRRP takes over. So
                # we'll send this event down the pipe.
                last_event = None
                backoff = False
                self.event_queue.pop()
                self.middleware.call_hook_sync('vrrp.fifo', data=this_event)
            elif time_diff_floor < max_wait_floor:
                # scenario #4 listed above
                # NOTE:
                # The events could look like this:
                #   RECEIVED: 'INSTANCE "eno1_v4" BACKUP 254\n' at time: 1701967219.244696
                #   RECEIVED: 'INSTANCE "eno1_v4" MASTER 254\n' at time: 1701967220.2902775
                # This happens when both controllers of an HA system start near simultaneously
                # (i.e. power-outage event most often) OR it could be happening because of an
                # external networking problem. Either way, the VRRP service will send adverts
                # but the moment the MASTER controller is determined, it'll send that advert
                # and (while testing in-house), it is _always_ less than the default advert
                # timeout (max_wait). We obviously can't ignore that event because doing so
                # would prevent the HA system from coming up properly (no zpools, no fenced)
                if not backoff:
                    backoff = True
                    last_event = this_event
                    sleep(self.rapid_event_settle_time)
                else:
                    last_event = None
                    backoff = False
                    self.event_queue.pop()
                    LOGGER.warning('Detected rapid succession of failover events: (%r)', this_event)
            else:
                LOGGER.warning('Unhandled failover event. last_event: %r, this_event: %r', last_event, this_event)
                last_event = None
                backoff = False
                self.event_queue.pop()


class VrrpFifoThread(Thread):

    def __init__(self, *args, **kwargs):
        super(VrrpFifoThread, self).__init__()
        self._retry_timeout = 2  # timeout in seconds before retrying to connect to FIFO
        self._vrrp_file = '/var/run/vrrpd.fifo'
        self.pause_event = Event()
        self.middleware = kwargs.get('middleware')
        self.event_queue = kwargs.get('queue')
        self.shutdown_line = '--SHUTDOWN--'

    def shutdown(self):
        with open(self._vrrp_file, 'w') as f:
            f.write(f'{self.shutdown_line}\n')

    def pause(self):
        self.pause_event.set()

    def unpause(self):
        self.pause_event.clear()

    def create_fifo(self):
        try:
            mkfifo(self._vrrp_file)
        except FileExistsError:
            pass
        except Exception:
            raise

    def run(self):
        set_name('vrrp_fifo_thread')
        try:
            self.create_fifo()
        except Exception:
            LOGGER.error('FATAL: Unable to create VRRP fifo.', exc_info=True)
            return

        log_it = True
        while True:
            try:
                with open(self._vrrp_file) as f:
                    LOGGER.info('vrrp fifo connection established')
                    for line in f:
                        if self.pause_event.is_set():
                            continue

                        event = line.strip()
                        if event == self.shutdown_line:
                            return
                        else:
                            self.event_queue.append({'event': event, 'time': time()})
            except Exception:
                if log_it:
                    LOGGER.warning(
                        'vrrp fifo connection not established, retrying every %d seconds',
                        self._retry_timeout,
                        exc_info=True
                    )
                    log_it = False
                    sleep(self._retry_timeout)


async def _start_stop_vrrp_threads(middleware):
    while not await middleware.call('system.ready'):
        await asyncio_sleep(0.2)

    licensed = await middleware.call('failover.licensed')
    if not licensed:
        # maybe the system is being downgraded to non-HA
        # (this is rare but still need to handle it) or
        # system is being restarted/shutdown etc
        if VrrpObjs.fifo_thread is not None and VrrpObjs.fifo_thread.is_alive():
            await middleware.run_in_thread(VrrpObjs.fifo_thread.shutdown)
            VrrpObjs.fifo_thread = None

        if VrrpObjs.event_thread is not None and VrrpObjs.event_thread.is_alive():
            await middleware.run_in_thread(VrrpObjs.event_thread.shutdown)
            VrrpObjs.event_thread = None

        if VrrpObjs.event_queue is not None:
            VrrpObjs.event_queue.clear()
            VrrpObjs.event_queue = None
    else:
        # if this is a system that is being licensed for HA for the
        # first time (without being rebooted) then we need to make
        # sure we start these threads
        if VrrpObjs.event_queue is None:
            VrrpObjs.event_queue = deque(maxlen=1)

        timeout = (await middleware.call('failover.config'))['timeout']
        if VrrpObjs.fifo_thread is None or not VrrpObjs.fifo_thread.is_alive():
            VrrpObjs.fifo_thread = VrrpFifoThread(middleware=middleware, queue=VrrpObjs.event_queue)
            VrrpObjs.fifo_thread.start()

        if VrrpObjs.event_thread is None or not VrrpObjs.event_thread.is_alive():
            VrrpObjs.event_thread = VrrpEventThread(middleware=middleware, queue=VrrpObjs.event_queue, timeout=timeout)
            VrrpObjs.event_thread.start()


async def _post_license_update(middleware, *args, **kwargs):
    await _start_stop_vrrp_threads(middleware)


async def setup(middleware):
    middleware.create_task(_start_stop_vrrp_threads(middleware))
    middleware.register_hook('system.post_license_update', _post_license_update)
