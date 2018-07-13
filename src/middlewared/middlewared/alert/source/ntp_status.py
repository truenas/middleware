from datetime import timedelta

from middlewared.alert.base import Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule
from middlewared.utils import run

import psutil
import ntplib
import time
import re
import os
import logging

logger = logging.getLogger(__name__)

# 30 minutes in seconds
STARTUP_PERIOD = 30*60
REQUEST_TIMEOUT = 5

SELECT_STATUS_RE = re.compile('^([x\.\-\+\#\*o]?)')
SELECT_STATUS = {
    '':  {'code': 0, 'message': 'sel_reject', 'description': "discarded as not valid (TEST10-TEST13)"},
    'x': {'code': 1, 'message': 'sel_falsetick', 'description': "discarded by intersection algorithm"},
    '.': {'code': 2, 'message': 'sel_excess', 'description': "discarded by table overflow (not used)"},
    '-': {'code': 3, 'message': 'sel_outlier', 'description': "discarded by the cluster algorithm"},
    '+': {'code': 4, 'message': 'sel_candidate', 'description': "included by the combine algorithm"},
    '#': {'code': 5, 'message': 'sel_backup', 'description': "backup (more than tos maxclock sources)"},
    '*': {'code': 6, 'message': 'sel_sys.peer', 'description': "system peer"},
    'o': {'code': 7, 'message': 'sel_pps.peer', 'description': "PPS peer (when the prefer peer is valid)"},
}

# type - local, unicast, multicast or broadcast
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
            """ """
            peer = line.strip().split()
            peer_cnt = len(peer)

            """Extract peer select status and peer address"""
            if peer_cnt in (1, FIELDS_CNT):
                match = SELECT_STATUS_RE.match(peer[0])
                select = match.group(0) if match else ''
                remote = peer[0].lstrip(select)
                if peer_cnt == 1:
                    continue
                peer[0] = remote
            elif peer_cnt == FIELDS_CNT-1 and remote:
                """Continuation line"""
                peer.insert(0, remote)
                remote = ''
            else:
                raise Exception("invalid row: '{}'".format(line))

            info = dict(zip(FIELDS, peer))

            info['select'] = SELECT_STATUS.get(select, '')['message']
            info['type'] = TYPE.get(info['type'], '-')
            info['reach'] = int(info['reach'], 8)

            if info['refid'] == '.INIT.':
                if since_boot() < STARTUP_PERIOD:
                    break
                else:
                    raise Exception("still initializing after {} seconds from boot".format(since_boot()))

            """Skip discarded peers """
            if info['select'] not in ('sel_candidate', 'sel_backup', 'sel_sys.peer', 'sel_pps.peer'):
                continue

            peers.append(info)
            remote = ''
            select = ''

    except Exception as e:
            logger.warning("NTP status: {}".format(str(e)))
            return []

    return peers


class NTPStatusAlertSource(AlertSource):
    level = AlertLevel.CRITICAL
    title = "NTP status"

    schedule = IntervalSchedule(timedelta(minutes=1))

    async def _get_peers(self):
        if os.path.exists('/var/tmp/ntp/query'):
            with open('/var/tmp/ntp/query', encoding='utf-8') as query:
                peers = query.read()
        else:
            peers = (await run(['/usr/bin/ntpq', '-pwn'], encoding='utf8')).stdout

        return parse_peers(peers)

    async def check(self):
        alerts = []

        info = next((peer for peer in await self._get_peers() if peer.get('select', '-') in ('sel_sys.peer')), None)
        if info:
            """ Success of the last 4 probes """
            if info['reach'] < 255 and info['reach'] & 0x0F != 0x0F:
                alerts.append(Alert(
                        title="NTP status: %(times)d out of 4 last probes failed",
                        args={'times': reachability(info['reach']).count('0')},
                        level=AlertLevel.WARNING
                    )
                )

            """ Check connectivity to the peer """
            try:
                client = ntplib.NTPClient()
                client.request(info['remote'], timeout=REQUEST_TIMEOUT)
            except ntplib.NTPException as ne:
                alerts.append(Alert(
                        title="NTP status: %(error)s",
                        args={'error': str(ne)},
                        key=['ntplib_exception'],
                        level=AlertLevel.CRITICAL
                    )
                )
            except Exception as e:
                alerts.append(Alert(
                        title="NTP status: %(error)s",
                        args={'error': str(e)},
                        key=['other_exception', 'ntp_client'],
                        level=AlertLevel.CRITICAL
                    )
                )
        else:
            alerts.append(Alert(
                    title="No usable NTP peers were found",
                    level=AlertLevel.CRITICAL
                )
            )

        return alerts
