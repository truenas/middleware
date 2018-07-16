import subprocess
import psutil
import ntplib
import time
import re
import os
import logging

from datetime import timedelta
from middlewared.alert.base import UnavailableException, Alert, AlertLevel, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule

logger = logging.getLogger(__name__)

# 30 minutes in seconds for starting up NTP
STARTUP_PERIOD = 30 * 60
REQUEST_TIMEOUT = 5
SINCE_BOOT = 0

SELECT_STATUS_RE = re.compile('^([x\.\-\+\#\*o]?)')
SELECT_STATUS = {
    '': {'code': 0, 'message': 'sel_reject', 'description': 'discarded as not valid (TEST10-TEST13)'},
    'x': {'code': 1, 'message': 'sel_falsetick', 'description': 'discarded by intersection algorithm'},
    '.': {'code': 2, 'message': 'sel_excess', 'description': 'discarded by table overflow (not used)'},
    '-': {'code': 3, 'message': 'sel_outlier', 'description': 'discarded by the cluster algorithm'},
    '+': {'code': 4, 'message': 'sel_candidate', 'description': 'included by the combine algorithm'},
    '#': {'code': 5, 'message': 'sel_backup', 'description': 'backup (more than tos maxclock sources)'},
    '*': {'code': 6, 'message': 'sel_sys.peer', 'description': 'system peer'},
    'o': {'code': 7, 'message': 'sel_pps.peer', 'description': 'PPS peer (when the prefer peer is valid)'},
}

TYPE = {
    'l': 'local',
    'u': 'unicast',
    'm': 'multicast',
    'b': 'broadcast',
    'p': 'pool'
}

FIELDS = ['remote', 'refid', 'stratum', 'type', 'when', 'poll', 'reach', 'delay', 'offset', 'jitter']
FIELDS_CNT = len(FIELDS)


def since_boot():
    return time.time() - psutil.boot_time()


def reachability(byte):
    return '{0:08b}'.format(byte)


def parse_peers(output):
    peers = []

    try:
        remote = ''
        select = ''
        for line in output.rpartition('=====')[2].strip().splitlines():
            peer = line.strip().split()
            peer_cnt = len(peer)

            """Extract peer's select status and address"""
            if peer_cnt in (1, FIELDS_CNT):
                match = SELECT_STATUS_RE.match(peer[0])
                select = match.group(0) if match else ''
                remote = peer[0].lstrip(select)
                if peer_cnt == 1:
                    continue
                peer[0] = remote
            elif peer_cnt == FIELDS_CNT - 1 and remote:
                """Continuation line"""
                peer.insert(0, remote)
                remote = ''
            else:
                logger.warning("Invalid line: '{:s}'".format(line))
                remote = ''
                select = ''
                continue

            info = dict(zip(FIELDS, peer))

            info['select'] = SELECT_STATUS.get(select, '')['message']
            info['stratum'] = int(info['stratum'])
            info['type'] = TYPE.get(info['type'], '-')
            info['poll'] = int(info['poll'])
            info['reach'] = int(info['reach'], 8)
            info['delay'] = float(info['delay'])
            info['offset'] = float(info['offset'])
            info['jitter'] = float(info['jitter'])

            if info['refid'] == '.INIT.':
                if SINCE_BOOT < STARTUP_PERIOD:
                    raise UnavailableException()
                else:
                    raise Exception("still initializing after {:d} seconds since boot".format(since_boot))

            """Skip discarded peers """
            if info['select'] not in ('sel_candidate', 'sel_backup', 'sel_sys.peer', 'sel_pps.peer'):
                continue

            peers.append(info)
            remote = ''
            select = ''

    except Exception as e:
        logger.warning("NTP status: {:s}".format(str(e)), exc_info=True)
        return []

    return peers


def get_peers():
    if os.path.exists('/var/tmp/ntp/query'):
        with open('/var/tmp/ntp/query', encoding='utf-8') as query:
            peers = query.read()
    else:
        proc = subprocess.Popen(
            ['/usr/bin/ntpq', '-pwn'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf8'
        )
        peers = proc.communicate()[0]

        if proc.returncode != 0:
            logger.warning(
                "NTP status: [Exit {:d}] failed to run 'ntpq'".format(proc.returncode),
                exc_info=True
            )
            return []

    return parse_peers(peers)


class NTPStatusAlertSource(ThreadedAlertSource):
    level = AlertLevel.CRITICAL
    title = 'NTP status'

    schedule = IntervalSchedule(timedelta(minutes=5))

    def check_sync(self):
        global SINCE_BOOT, STARTUP_PERIOD
        alerts = []

        if SINCE_BOOT < STARTUP_PERIOD:
            SINCE_BOOT = since_boot()

        """ sel_pps.peer? """
        info = next((peer for peer in get_peers() if peer.get('select', '-') == 'sel_sys.peer'), None)
        if info:
            STARTUP_PERIOD = info['poll'] * 8
            """ Delay """
            if abs(info['delay']) > 500:
                level = AlertLevel.WARNING
                if abs(info['delay']) > 1000:
                    level = AlertLevel.CRITICAL

                alerts.append(Alert(
                    title="NTP status: delay %(delay)f is too large for the normal operations",
                    args={'delay': info['delay']},
                    key=['ntp_delay', str(level)],
                    level=level
                ))
            """ Offset """
            if abs(info['offset']) > 300:
                level = AlertLevel.WARNING
                if abs(info['offset']) > 500:
                    level = AlertLevel.CRITICAL

                alerts.append(Alert(
                    title="NTP status: offset %(offset)f is too large for the normal operations",
                    args={'offset': info['offset']},
                    key=['ntp_offset', str(level)],
                    level=level
                ))
            """ Jitter """
            if abs(info['jitter']) > 300:
                level = AlertLevel.WARNING
                if abs(info['jitter']) > 500:
                    level = AlertLevel.CRITICAL

                alerts.append(Alert(
                    title="NTP status: jitter %(jitter)f is too large for the normal operations",
                    args={'jitter': info['jitter']},
                    key=['ntp_jitter', str(level)],
                    level=level
                ))
            """ Stratum """
            if info['stratum'] > 3:
                level = AlertLevel.WARNING
                if info['stratum'] > 5:
                    level = AlertLevel.CRITICAL

                alerts.append(Alert(
                    title="NTP status: stratum %(stratum)d is too large for the normal operations",
                    args={'stratum': info['stratum']},
                    level=level
                ))
            """ Reachability """
            if (info['reach'] < 255) and (info['poll'] * 8 < SINCE_BOOT):
                alerts.append(Alert(
                    title="NTP status: %(times)d out of 8 probes failed",
                    args={'times': reachability(info['reach']).count('0')},
                    key=['ntp_flapping'],
                    level=AlertLevel.WARNING
                ))

                if info['reach'] & 0x0F == 0x00:
                    alerts.append(Alert(
                        title="NTP status: Last 4 probes failed",
                        key=['ntp_failed'],
                        level=AlertLevel.CRITICAL
                    ))

            """ Check connectivity with the peer """
            try:
                client = ntplib.NTPClient()
                client.request(info['remote'], timeout=REQUEST_TIMEOUT)
            except ntplib.NTPException as ne:
                alerts.append(Alert(
                    title='NTP status: %(error)s',
                    args={'error': str(ne)},
                    key=['ntp_exception'],
                    level=AlertLevel.CRITICAL
                ))
            except Exception as e:
                alerts.append(Alert(
                    title='NTP status: %(error)s',
                    args={'error': str(e)},
                    key=['ntp_client', 'other_exception'],
                    level=AlertLevel.CRITICAL
                ))
        else:
            alerts.append(Alert(
                title='No usable NTP peers were found',
                level=AlertLevel.CRITICAL
            ))

        return alerts
