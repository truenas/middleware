# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import errno
import os
import json
import subprocess
import xmlrpc.client

from freenasUI.failover.enc_helper import LocalEscrowCtl
from freenasUI.failover.notifier import INTERNAL_IFACE_NF
from freenasUI.middleware.client import client, ClientException
from freenasUI.middleware.notifier import notifier

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource

FAILOVER_JSON = '/tmp/failover.json'


class FailoverCheckAlertSource(ThreadedAlertSource):
    level = AlertLevel.CRITICAL
    title = "Failover is not working"

    def check_sync(self):
        alerts = []

        if not self.middleware.call_sync('failover.licensed'):
            return alerts

        if os.path.exists(INTERNAL_IFACE_NF):
            alerts.append(Alert(
                'Failover internal interface not found. Contact support.',
            ))

        try:
            with client as c:
                c.call('failover.call_remote', 'core.ping')

                local_version = c.call('system.version')
                remote_version = c.call('failover.call_remote', 'system.version')
                if local_version != remote_version:
                    return [
                        Alert(
                            'TrueNAS versions mismatch in failover.  Update both nodes to the same version.',
                        )
                    ]
        except Exception as e:
            try:
                if e.errno not in (errno.ECONNREFUSED, ClientException.ENOMETHOD) and e.trace['class'] not in ('KeyError', 'ConnectionRefusedError'):
                    raise
                try:
                    s = notifier().failover_rpc()
                    if s is not None:
                        s.run_sql("SELECT 1", None)
                except xmlrpc.client.Fault as e:
                    if e.faultCode == 5:
                        return [
                            Alert(
                                'Failover access denied. Please reconfigure it.',
                            )
                        ]
                    elif e.faultCode == 55:
                        return [
                            Alert(
                                'TrueNAS versions mismatch in failover.  Update both nodes to the same version.',
                            )
                        ]
                    else:
                        raise

            except Exception as e:
                return [
                    Alert(
                        'Failed to check failover status with the other node: %s',
                        args=[str(e)],
                    )
                ]

        status = notifier().failover_status()

        fobj = None
        try:
            with open(FAILOVER_JSON, 'r') as f:
                fobj = json.loads(f.read())
        except:
            pass

        if status == 'ERROR':
            errmsg = None
            args = None
            if os.path.exists('/tmp/.failover_failed'):
                with open('/tmp/.failover_failed', 'r') as fh:
                    errmsg = fh.read()
            if errmsg:
                args = [errmsg]
                errmsg = "Failover failed: %s"
            else:
                errmsg = "Failover failed"
            alerts.append(Alert(
                errmsg,
                args=args,
            ))
        elif status not in ('MASTER', 'BACKUP', 'SINGLE'):
            alerts.append(Alert(
                'Could not determine external failover link status, check cabling.',
                level=AlertLevel.WARNING,
            ))
        internal_ifaces = notifier().failover_internal_interfaces()
        if internal_ifaces:
            p1 = subprocess.Popen(
                "/sbin/ifconfig %s|grep -E 'vhid (10|20) '|grep 'carp:'" % internal_ifaces[0],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                encoding='utf8',
            )
            stdout = p1.communicate()[0].strip()
            if status != "SINGLE" and stdout.count("\n") != 1:
                alerts.append(Alert(
                    'Could not determine internal failover link status, Automatic failover disabled.',
                    level=AlertLevel.WARNING,
                ))

        if status != "SINGLE":
            try:
                if notifier().sysctl('kern.cam.ctl.ha_link') == 1:
                    alerts.append(Alert(
                        'CTL HA link is not connected',
                    ))
            except:
                pass

        if status == 'MASTER':
            masters, backups = notifier().get_carp_states()
            if len(backups) > 0:
                alerts.append(Alert(
                    'Check external failover links.',
                    level=AlertLevel.WARNING,
                ))

        if status == 'BACKUP':
            try:
                if len(fobj['phrasedvolumes']) > 0:
                    escrowctl = LocalEscrowCtl()
                    if not escrowctl.status():
                        alerts.append(Alert(
                            'No escrowed passphrase for failover. Automatic failover disabled.',
                        ))
                        # Kick a syncfrompeer if we don't.
                        with client as c:
                            passphrase = c.call('failover.call_remote', 'failover.encryption_getkey')
                        if passphrase:
                            escrowctl.setkey(passphrase)
            except:
                pass

        return alerts
