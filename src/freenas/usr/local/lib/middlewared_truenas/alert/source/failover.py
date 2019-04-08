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
from freenasUI.middleware.notifier import notifier

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource
from middlewared.service_exception import CallError

FAILOVER_JSON = '/tmp/failover.json'


class FailoverInterfaceNotFoundAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Failover Internal Interface Not Found"
    text = "Failover internal interface not found. Contact support."


class TrueNASVersionsMismatchAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "TrueNAS Versions Mismatch In Failover"
    text = "TrueNAS versions mismatch in failover. Update both nodes to the same version."


class FailoverAccessDeniedAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Failover Access Denied"
    text = "Failover access denied. Please reconfigure it."


class FailoverStatusCheckFailedAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Failed to Check Failover Status with the Other Node"
    text = "Failed to check failover status with the other node: %s."


class FailoverFailedAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Failover Failed"
    text = "Failover failed: %s."


class ExternalFailoverLinkStatusAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Could not Determine External Failover Link Status"
    text = "Could not determine external failover link status, check cabling."


class InternalFailoverLinkStatusAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Could not Determine Internal Failover Link Status"
    text = "Could not determine internal failover link status. Automatic failover disabled."


class CARPStatesDoNotAgreeAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Nodes CARP States Do Not Agree"
    text = "Nodes CARP states do not agree: %(error)s."


class CTLHALinkAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "CTL HA link Is not Connected"
    text = "CTL HA link is not connected."


class CheckExternalFailoverLinksAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "Check External Failover Links"
    text = "Check external failover links."


class NoFailoverEscrowedPassphraseAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = "No Escrowed Passphrase for Failover"
    text = "No escrowed passphrase for failover. Automatic failover disabled."


def check_carp_states(local, remote):
    errors = []
    interfaces = set(local[0] + local[1] + remote[0] + remote[1])
    if not interfaces:
        errors.append(f"There are no failover interfaces")
    for name in interfaces:
        if name not in local[0] + local[1]:
            errors.append(f"Interface {name} is not configured for failover on local system")
        if name not in remote[0] + remote[1]:
            errors.append(f"Interface {name} is not configured for failover on remote system")
        if name in local[0] and name in remote[0]:
            errors.append(f"Interface {name} is MASTER on both nodes")
        if name in local[1] and name in remote[1]:
            errors.append(f"Interface {name} is BACKUP on both nodes")

    return errors


class FailoverlertSource(ThreadedAlertSource):
    def check_sync(self):
        alerts = []

        if not self.middleware.call_sync('failover.licensed'):
            return alerts

        if os.path.exists(INTERNAL_IFACE_NF):
            alerts.append(Alert(FailoverInterfaceNotFoundAlertClass))

        try:
            self.middleware.call_sync('failover.call_remote', 'core.ping')

            local_version = self.middleware.call_sync('system.version')
            remote_version = self.middleware.call_sync('failover.call_remote', 'system.version')
            if local_version != remote_version:
                return [Alert(TrueNASVersionsMismatchAlertClass)]

        except CallError as e:
            try:
                if e.errno not in (errno.ECONNREFUSED, errno.EHOSTDOWN, CallError.ENOMETHOD):
                    raise
                try:
                    s = notifier().failover_rpc()
                    if s is not None:
                        s.run_sql("SELECT 1", None)
                except xmlrpc.client.Fault as e:
                    if e.faultCode == 5:
                        return [Alert(FailoverAccessDeniedAlertClass)]
                    elif e.faultCode == 55:
                        return [Alert(TrueNASVersionsMismatchAlertClass)]
                    else:
                        raise

            except Exception as e:
                return [Alert(FailoverStatusCheckFailedAlertClass, [str(e)])]

        status = self.middleware.call_sync('failover.status')

        fobj = None
        try:
            with open(FAILOVER_JSON, 'r') as f:
                fobj = json.loads(f.read())
        except Exception:
            pass

        if status == 'ERROR':
            errmsg = None
            if os.path.exists('/tmp/.failover_failed'):
                with open('/tmp/.failover_failed', 'r') as fh:
                    errmsg = fh.read()
            if not errmsg:
                errmsg = 'Unknown error'

            alerts.append(Alert(FailoverFailedAlertClass, [errmsg]))

        elif status not in ('MASTER', 'BACKUP', 'SINGLE'):
            alerts.append(Alert(ExternalFailoverLinkStatusAlertClass))

        internal_ifaces = self.middleware.call_sync('failover.internal_interfaces')
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
                alerts.append(Alert(InternalFailoverLinkStatusAlertClass))

        local = self.middleware.call_sync('failover.status')
        remote = self.middleware.call_sync('failover.call_remote', 'failover.status')
        errors = check_carp_states(local, remote)
        for error in errors:
            alerts.append(Alert(
                CARPStatesDoNotAgreeAlertClass,
                {"error": error},
            ))

        if status != "SINGLE":
            try:
                if notifier().sysctl('kern.cam.ctl.ha_link') == 1:
                    alerts.append(Alert(CTLHALinkAlertClass))
            except Exception:
                pass

        if status == 'MASTER':
            masters, backups = self.middleware.call_sync('failover.get_carp_states')
            if len(backups) > 0:
                alerts.append(Alert(CheckExternalFailoverLinksAlertClass))

        if status == 'BACKUP':
            try:
                if len(fobj['phrasedvolumes']) > 0:
                    escrowctl = LocalEscrowCtl()
                    if not escrowctl.status():
                        alerts.append(Alert(NoFailoverEscrowedPassphraseAlertClass))
                        # Kick a syncfrompeer if we don't.
                        passphrase = self.middleware.call_sync(
                            'failover.call_remote', 'failover.encryption_getkey'
                        )
                        if passphrase:
                            escrowctl.setkey(passphrase)
            except Exception:
                pass

        return alerts
