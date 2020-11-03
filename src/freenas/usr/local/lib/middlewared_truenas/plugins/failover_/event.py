# Copyright (c) 2020 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.
from middlewared.utils import filter_list
from middlewared.service import Service, private

from lockfile import LockFile, AlreadyLocked
from collections import defaultdict
import multiprocessing
import os
import sqlite3
import subprocess
import logging
try:
    import sysctl
except ImportError:
    sysctl = None
import time
import struct


# GUI sentinel files
ELECTING_FILE = '/tmp/.failover_electing'
IMPORTING_FILE = '/tmp/.failover_importing'
FAILED_FILE = '/tmp/.failover_failed'
FAILOVER_STATE = '/tmp/.failover_state'
FAILOVER_ASSUMED_MASTER = '/tmp/.failover_master'

# GUI alert file
AD_ALERT_FILE = '/tmp/.adalert'

# MUTEX files
# Advanced TODO Merge to one mutex
FAILOVER_IFQ = '/tmp/.failover_ifq'
FAILOVER_EVENT = '/tmp/.failover_event'

# Fast track, user initiated failover
FAILOVER_OVERRIDE = '/tmp/failover_override'

# Samba sentinel file
SAMBA_USER_IMPORT_FILE = "/root/samba/.usersimported"

# This sentinel is created by the pool decryption
# script to let us know we need to do something
FAILOVER_NEEDOP = '/tmp/.failover_needop'

# These files are created by a cron job
# and used to fast track determining a master
HEARTBEAT_BARRIER = '/tmp/heartbeat_barrier'
HEARTBEAT_STATE = '/tmp/heartbeat_state'

# This file is managed in freeNAS code (unscheduled_reboot_alert.py)
# Ticket 39114
WATCHDOG_ALERT_FILE = "/data/sentinels/.watchdog-alert"

# FAILOVER_IFQ is the mutex used to protect per-interface events.
# Before creating the lockfile that this script is handing events
# on a given interface, this lock is aquired.  This lock attempt
# sleeps indefinitely, which is (ab)used to create an event queue.
# For instance, if igb0 link_down, link_up, link_down happens in
# rapid succession, the script will fire with all three events, but
# event two and three will wait until event one runs to completion.
# It's important to note that when the event handlers fire one of
# the first things they do is check to see if the event that fired
# them is still in affect.  For instance, by the time the link_up
# event handler runs in this example igb0 will be link_down and it
# will exit.

# FAILOVER_EVENT is the mutex to protect the critical sections of
# the "become active" or "become standby" actions in this script.
# This is needed in situations where there are multiple interfaces
# that all go link_up or link_down simultaniously (such as when the
# partner node reboots).  In that case each interface will acquire
# it's per-interface lock and run the link_up or link_down event
# FAILOVER_EVENT prevents them both from starting fenced or
# importing volumes or whatnot.

logger = logging.getLogger('failover')


def run(cmd, stderr=False):
    proc = subprocess.Popen(
        cmd,
        stderr=subprocess.PIPE if not stderr else subprocess.STDOUT,
        stdout=subprocess.PIPE,
        shell=True,
        encoding='utf8',
    )
    output = proc.communicate()[0]
    return (proc.returncode, output.strip('\n'))


def run_async(cmd):
    subprocess.Popen(
        cmd,
        shell=True,
    )
    return


class IgnoreFailoverEvent(Exception):
    pass


class FailoverService(Service):

    @private
    def run_call(self, method, *args):
        try:
            return self.middleware.call_sync(method, *args)
        except Exception as e:
            logger.error('Failed to run %s:%r: %s', method, args, e)

    @private
    def event(self, ifname, vhid, event):
        refresh = True
        try:
            return self._event(ifname, vhid, event)
        except IgnoreFailoverEvent:
            refresh = False
        finally:
            if refresh:
                self.middleware.call_sync('failover.status_refresh')

    @private
    def generate_failover_data(self):

        failovercfg = self.middleware.call_sync('failover.config')
        pools = self.middleware.call_sync('pool.query')
        interfaces = self.middleware.call_sync('interface.query')
        internal_ints = self.middleware.call_sync('failover.internal_interfaces')
        boot_disks = ",".join(self.middleware.call_sync('boot.get_disks'))

        data = {
            'disabled': failovercfg['disabled'],
            'master': failovercfg['master'],
            'timeout': failovercfg['timeout'],
            'groups': defaultdict(list),
            'volumes': [
                i['name'] for i in filter_list(pools, [('encrypt', '<', 2)])
            ],
            'phrasedvolumes': [
                i['name'] for i in filter_list(pools, [('encrypt', '=', 2)])
            ],
            'non_crit_interfaces': [
                i['id'] for i in filter_list(interfaces, [
                    ('failover_critical', '!=', True),
                ])
            ],
            'internal_interfaces': internal_ints,
            'boot_disks': boot_disks,
        }

        for i in filter_list(interfaces, [('failover_critical', '=', True)]):
            data['groups'][i['failover_group']].append(i['id'])

        return data

    @private
    def _event(self, ifname, vhid, event):

        fobj = self.generate_failover_data()

        # We ignore events on the p2p heartbeat connection
        if ifname in fobj['internal_interfaces']:
            logger.warning(
                f'Ignoring event:{event} on internal interface {ifname}')
            raise IgnoreFailoverEvent()

        if event == 'forcetakeover':
            forcetakeover = True
        else:
            forcetakeover = False

        # TODO write the PID into the state file so a stale
        # lockfile won't disable HA forever
        state_file = f'{FAILOVER_STATE}{event}'

        try:
            # Implicit event queuing
            with LockFile(FAILOVER_IFQ):
                if not os.path.exists(state_file):
                    open(state_file, 'w').close()
                else:
                    logger.warning('Failover event already being processed, ignoring.')
                    raise IgnoreFailoverEvent()

            # TODO python any
            if not forcetakeover:
                SENTINEL = False
                for group in fobj['groups']:
                    for interface in fobj['groups'][group]:
                        if ifname == interface:
                            SENTINEL = True

                if not SENTINEL:
                    logger.warning('Ignoring state change on non-critical interface %s.', ifname)
                    raise IgnoreFailoverEvent()

                if fobj['disabled']:
                    if not fobj['master']:
                        logger.warning('Failover disabled. Assuming backup.')
                        return
                    else:
                        try:
                            status = self.middleware.call_sync('failover.call_remote', 'failover.status')
                            if status == 'MASTER':
                                logger.warning('Other node is already active, assuming backup.')
                                return
                        except Exception:
                            logger.info('Failed to contact the other node', exc_info=True)

                        masterret = False
                        for vol in fobj['volumes'] + fobj['phrasedvolumes']:
                            # TODO run, or zfs lib
                            ret = os.system(f'zpool status {vol} > /dev/null')
                            if ret:
                                masterret = True
                                for group in fobj['groups']:
                                    for interface in fobj['groups'][group]:
                                        error, output = run(f"ifconfig {interface} | grep 'carp:' | awk '{{print $4}}'")
                                        for vhid in output.split():
                                            logger.warning('Setting advskew to 0 on interface %s', interface)
                                            run(f'ifconfig {interface} vhid {vhid} advskew 0')
                                logger.warning('Failover disabled.  Assuming active.')
                                run(f'touch {FAILOVER_OVERRIDE}')
                                # interfaces advskew have been changed, switch event
                                event = 'MASTER'
                                break
                        if masterret is False:
                            # All pools are already imported
                            logger.warning('All pools already imported, ignoring.')
                            return

            open(HEARTBEAT_BARRIER, 'a+').close()

            now = int(time.time())
            os.utime(HEARTBEAT_BARRIER, (now, now))

            user_override = True if os.path.exists(FAILOVER_OVERRIDE) else False

            if event == 'MASTER' or event == 'forcetakeover':
                return self.carp_master(fobj, ifname, vhid, event, user_override, forcetakeover)
            elif event == 'BACKUP' or event == 'INIT':
                if sysctl.filter('net.inet.carp.allow')[0].value == 0:
                    user_override = True
                return self.carp_backup(fobj, ifname, vhid, event, user_override)
        finally:
            try:
                os.unlink(state_file)
            except Exception:
                pass

    @private
    def carp_master(self, fobj, ifname, vhid, event, user_override, forcetakeover):

        if forcetakeover:
            logger.warning('Starting force takeover.')
        else:
            logger.warning('Entering MASTER on %s', ifname)

        if not user_override and not forcetakeover:
            sleeper = fobj['timeout']
            # The specs for lagg require that if a subinterface of the lagg interface
            # changes state, all traffic on the entire logical interface will be halted
            # for two seconds while the bundle reconverges.  This means if there's a
            # toplogy change on the active node, the standby node will get a link_up
            # event on the lagg.  To  prevent the standby node from immediately pre-empting
            # we wait 2 seconds to see if the evbent was transient.
            # 28143 - default timeout to solve cases like saturated networks(lost CARP packets)
            if ifname.startswith('lagg'):
                if sleeper < 2:
                    sleeper = 2
            else:
                # Check interlink - if it's down there is no need to wait.
                for iface in fobj['internal_interfaces']:
                    error, output = run(f"ifconfig {iface} | grep 'status:' | awk '{{print $2}}'")
                    if output != 'active':
                        break
                else:
                    # Check whether both vhid are master - link may be acctive while second node reboots.
                    for iface in fobj['internal_interfaces']:
                        error, output = run(
                            f"ifconfig {iface} | grep 'carp:' | awk '{{print $2}}'| grep 'MASTER' | wc -l "
                        )
                        if int(output) >= 2:
                            break
                    else:
                        if sleeper < 2:
                            sleeper = 2

            if sleeper != 0:
                logger.warning('Sleeping %s seconds and rechecking %s', sleeper, ifname)
                time.sleep(sleeper)
                error, output = run(
                    f"ifconfig {ifname} | grep 'carp:' | grep 'vhid {vhid} ' | awk '{{print $2}}'"
                )
                if output != 'MASTER':
                    logger.warning('%s became %s. Previous event ignored.', ifname, output)
                    return

        if os.path.exists(FAILOVER_ASSUMED_MASTER) or forcetakeover:
            error, output = run('ifconfig -l')
            for iface in list(output.split()):
                if iface in fobj['internal_interfaces']:
                    continue
                error, output = run(f"ifconfig {iface} | grep 'carp:' | awk '{{print $4}}'")
                for vhid in list(output.split()):
                    logger.warning('Setting advskew to 1 on interface %s', iface)
                    run(f'ifconfig {iface} vhid {vhid} advskew 1')
            if not forcetakeover:
                return

        if not forcetakeover:
            """
            We check if we have at least one BACKUP interface per group.
            If that turns out to be true we ignore the MASTER state in one of the
            interfaces, otherwise we assume master.
            """
            ignoreall = True
            for group, carpint in list(fobj['groups'].items()):
                totoutput = 0
                ignore = False
                for i in carpint:
                    error, output = run(f"ifconfig {i} | grep -c 'carp: BACKUP'")
                    totoutput += int(output)

                    if not error and totoutput > 0:
                        ignore = True
                ignoreall &= ignore

            if ignoreall:
                logger.warning(
                    'Ignoring UP state on %s because we still have interfaces that are'
                    ' BACKUP.', ifname
                )
                run_async('echo "$(date), $(hostname), {} assumed master while other '
                          'interfaces are still in slave mode." | mail -s "Failover WARNING"'
                          ' root'.format(ifname))
                return

        run('pkill -9 -f fenced')

        try:
            os.unlink(FAILED_FILE)
        except Exception:
            pass
        try:
            os.unlink(IMPORTING_FILE)
        except Exception:
            pass
        open(ELECTING_FILE, 'w').close()

        fasttrack = False
        if not forcetakeover:
            was_connected = True if (
                os.path.exists(HEARTBEAT_STATE) and
                os.stat(HEARTBEAT_STATE).st_mtime > os.stat(HEARTBEAT_BARRIER).st_mtime
            ) else False

            if was_connected:
                time.sleep(1)
                error, status0 = run(
                    f"ifconfig {ifname} | grep 'carp:' | awk '{{print $2}}'"
                )
                if fobj['internal_interfaces']:
                    intiface = fobj['internal_interfaces'][0]
                else:
                    intiface = ''
                error, status1 = run(
                    "ifconfig {} | grep carp: | grep -E 'vhid (10|20) ' | awk '{{print $2;}}' "
                    "|grep -E '(MASTER|INIT)' | wc -l".format(intiface)
                )
                error, status2 = run(
                    "ifconfig {} | grep carp: | grep -E 'vhid (10|20) ' | awk '{{print $2;}}' "
                    "|grep BACKUP | wc -l".format(intiface)
                )

                logger.warning('Status: %s:%s:%s', status0, status1, status2)

                if status0 != 'MASTER':
                    logger.warning('Promoted then demoted, quitting.')
                    # Just in case.  Demote ourselves.
                    run(f'ifconfig {ifname} vhid {vhid} advskew 206')
                    try:
                        os.unlink(ELECTING_FILE)
                    except Exception:
                        pass
                    return

                if int(status1) == 2 and int(status2) == 0:
                    fasttrack = True

        # Start the critical section
        try:
            with LockFile(FAILOVER_EVENT, timeout=0):
                # The lockfile modules cleans up lockfiles if this script exits on it's own accord.
                # For reboots, /tmp is cleared by virtue of being a memory device.
                # If someone does a kill -9 on the script while it's running the lockfile
                # will get left dangling.
                logger.warning('Acquired failover master lock')
                logger.warning('Starting fenced')
                if not user_override and not fasttrack and not forcetakeover:
                    error, output = run(
                        f'LD_LIBRARY_PATH=/usr/local/lib /usr/local/bin/fenced -ed "{fobj["boot_disks"]}"'
                    )
                else:
                    error, output = run(
                        f'LD_LIBRARY_PATH=/usr/local/lib /usr/local/bin/fenced --force -ed "{fobj["boot_disks"]}"'
                    )

                if error:
                    if error == 1:
                        logger.warning('Can not register keys on disks!')
                        run(f'ifconfig {ifname} vhid {vhid} advskew 201')
                    elif error == 2:
                        logger.warning('Remote fenced is running!')
                        run(f'ifconfig {ifname} vhid {vhid} advskew 202')
                    elif error == 3:
                        logger.warning('Can not reserve all disks!')
                        run(f'ifconfig {ifname} vhid {vhid} advskew 203')
                    elif error == 4:
                        logger.warning('Can not exclude all disks!')
                        run(f'ifconfig {ifname} vhid {vhid} advskew 204')
                    elif error == 5:
                        logger.warning('Fencing daemon encountered an unexpected fatal error!')
                        run(f'ifconfig {ifname} vhid {vhid} advskew 205')
                    else:
                        logger.warning('This should never happen: %d', error)
                        run(f'ifconfig {ifname} vhid {vhid} advskew 204')
                    try:
                        os.unlink(ELECTING_FILE)
                    except Exception:
                        pass
                    return False

                # If we reached here, fenced is daemonized and have all drives reserved.
                # Bring up all carps we own.
                error, output = run('ifconfig -l')
                for iface in output.split():
                    for iface in list(output.split()):
                        if iface in fobj['internal_interfaces']:
                            continue
                        error, output = run(f"ifconfig {iface} | grep 'carp:' | awk '{{print $4}}'")
                        for vhid in list(output.split()):
                            logger.warning('Setting advskew to 1 on interface %s', iface)
                            run(f'ifconfig {iface} vhid {vhid} advskew 1')

                open(IMPORTING_FILE, 'w').close()
                try:
                    os.unlink(ELECTING_FILE)
                except Exception:
                    pass

                run("sysctl -n kern.disks | tr ' ' '\\n' | sed -e 's,^,/dev/,' | egrep '^/dev/(da|nvd|pmem)' | xargs -n 1 echo 'false >' | sh")

                if os.path.exists('/data/zfs/killcache'):
                    run('rm -f /data/zfs/zpool.cache /data/zfs/zpool.cache.saved')
                else:
                    open('/data/zfs/killcache', 'w').close()
                    run('fsync /data/zfs/killcache')

                if os.path.exists('/data/zfs/zpool.cache'):
                    stat1 = os.stat('/data/zfs/zpool.cache')
                    if (
                        not os.path.exists('/data/zfs/zpool.cache.saved') or
                        stat1.st_mtime > os.stat('/data/zfs/zpool.cache.saved').st_mtime
                    ):
                        run('cp /data/zfs/zpool.cache /data/zfs/zpool.cache.saved')

                logger.warning('Beginning volume imports.')

                attach_all_job = self.middleware.call_sync('failover.attach_all_geli_providers')
                attach_all_job.wait_sync()
                if attach_all_job.error:
                    logger.error('Failed to attach geli providers: %s', attach_all_job.error)

                p = multiprocessing.Process(target=os.system("""dtrace -qn 'zfs-dbgmsg{printf("\r                            \r%s", stringof(arg0))}' > /dev/console &"""))
                p.start()
                for volume in fobj['volumes']:
                    logger.warning('Importing %s', volume)
                    # TODO: try to import using cachefile and then fallback without if it fails
                    error, output = run('zpool import -o cachefile=none -m -R /mnt -f {}'.format(
                        volume,
                    ), stderr=True)
                    if error:
                        logger.error('Failed to import %s: %s', volume, output)
                        open(FAILED_FILE, 'w').close()
                    else:
                        unlock_job = self.middleware.call_sync('failover.unlock_zfs_datasets', volume)
                        unlock_job.wait_sync()
                        if unlock_job.error:
                            logger.error('Failed to unlock ZFS encrypted datasets: %s', unlock_job.error)
                        elif unlock_job.result['failed']:
                            logger.error(
                                'Failed to unlock %s ZFS encrypted dataset(s)', ','.join(unlock_job.result['failed'])
                            )
                    run(f'zpool set cachefile=/data/zfs/zpool.cache {volume}')

                p.terminate()
                os.system("pkill -9 -f 'dtrace -qn'")
                if not os.path.exists(FAILOVER_NEEDOP):
                    open(FAILOVER_ASSUMED_MASTER, 'w').close()

                try:
                    os.unlink('/data/zfs/killcache')
                except Exception:
                    pass

                if not os.path.exists(FAILED_FILE):
                    run('cp /data/zfs/zpool.cache /data/zfs/zpool.cache.saved')
                try:
                    os.unlink(IMPORTING_FILE)
                except Exception:
                    pass

                logger.warning('Volume imports complete.')
                logger.warning('Restarting services.')
                self.run_call('failover.status_refresh')
                FREENAS_DB = '/data/freenas-v1.db'
                conn = sqlite3.connect(FREENAS_DB)
                c = conn.cursor()

                self.run_call('etc.generate', 'rc')
                self.run_call('etc.generate', 'system_dataset')

                # set this immediately after pool import because ALUA
                # doesnt use the VIP so it doesnt need pf to be disabled
                # 0 for Active node
                run('/sbin/sysctl kern.cam.ctl.ha_role=0')

                # Write the certs to disk based on what is written in db.
                self.run_call('etc.generate', 'ssl')
                # Now we restart the appropriate services to ensure it's using correct certs.
                self.run_call('service.restart', 'http')

                c.execute('SELECT srv_enable FROM services_services WHERE srv_service = "nfs"')
                ret = c.fetchone()
                if ret and ret[0] == 1:
                    self.run_call('service.restart', 'nfs', {'ha_propagate': False})

                c.execute('SELECT srv_enable FROM services_services WHERE srv_service = "cifs"')
                ret = c.fetchone()
                if ret and ret[0] == 1:
                    self.run_call('service.restart', 'cifs', {'ha_propagate': False})

                c.execute('SELECT srv_enable FROM services_services WHERE srv_service = "iscsitarget"')
                ret = c.fetchone()
                if ret and ret[0] == 1:
                    # Do not restart iscsitarget as it is not necessary (but breaks FC connections)
                    if not self.middleware.call_sync('service.started', 'iscsitarget'):
                        self.run_call('service.start', 'iscsitarget')

                c.execute('SELECT srv_enable FROM services_services WHERE srv_service = "afp"')
                ret = c.fetchone()
                if ret and ret[0] == 1:
                    self.run_call('service.restart', 'afp', {'ha_propagate': False})

                self.run_call('zettarepl.update_tasks')

                logger.warning('Service restarts complete.')

                # TODO: This is 4 years old at this point.  Is it still needed?
                # There appears to be a small lag if we allow NFS traffic right away. During
                # this time, we fail NFS requests with ESTALE to the remote system. This
                # gives remote clients heartburn, so rather than try to deal with the
                # downstream effect of that, instead we take a chill pill for 1 seconds.
                time.sleep(1)

                run('/sbin/pfctl -d')

                logger.warning('Allowing network traffic.')
                run_async('echo "$(date), $(hostname), assume master" | mail -s "Failover" root')

                try:
                    os.unlink(FAILOVER_OVERRIDE)
                except Exception:
                    pass

                self.run_call('etc.generate', 'cron')

                # sync disks is disabled on passive node
                self.run_call('disk.sync_all')

                logger.warning('Syncing enclosure')
                self.run_call('enclosure.sync_zpool')

                self.run_call('service.restart', 'collectd', {'ha_propagate': False})
                self.run_call('service.restart', 'syslogd', {'ha_propagate': False})
                self.run_call('service.restart', 'mdns', {'ha_propagate': False})

                for i in (
                    'smartd', 'ftp', 'lldp', 'rsync', 's3', 'snmp', 'ssh', 'tftp', 'webdav', 'ups',
                ):
                    c.execute(f'SELECT srv_enable FROM services_services WHERE srv_service = "{i}"')
                    ret = c.fetchone()
                    if ret and ret[0] == 1:
                        self.run_call('service.restart', i, {'ha_propagate': False})

                self.run_call('jail.start_on_boot')
                self.run_call('vm.start_on_boot')

                self.run_call('alert.block_failover_alerts')
                self.run_call('alert.initialize', False)
                kmip_config = self.run_call('kmip.config')
                if kmip_config and kmip_config['enabled']:
                    # Even though we keep keys in sync, it's best that we do this as well
                    # to ensure that the system is up to date with the latest keys available
                    # from KMIP. If it's unaccessible, the already synced memory keys are used
                    # meanwhile.
                    self.run_call('kmip.initialize_keys')

                conn.close()

                logger.warning('Failover event complete.')
        except AlreadyLocked:
            logger.warning('Failover event handler failed to aquire master lockfile')

    @private
    def carp_backup(self, fobj, ifname, vhid, event, user_override):
        logger.warning('Entering BACKUP on %s', ifname)

        if not user_override:
            sleeper = fobj['timeout']
            # The specs for lagg require that if a subinterface of the lagg interface
            # changes state, all traffic on the entire logical interface will be halted
            # for two seconds while the bundle reconverges.  This means if there's a
            # toplogy change on the active node, the standby node will get a link_up
            # event on the lagg.  To  prevent the standby node from immediately pre-empting
            # we wait 2 seconds to see if the evbent was transient.
            if ifname.startswith('lagg'):
                if sleeper < 2:
                    sleeper = 2
            else:
                # Check interlink - if it's down there is no need to wait.
                for iface in fobj['internal_interfaces']:
                    error, output = run(
                        f"ifconfig {iface} | grep 'status:' | awk '{{print $2}}'"
                    )
                    if output != 'active':
                        break
                else:
                    if sleeper < 2:
                        sleeper = 2

            if sleeper != 0:
                logger.warning('Sleeping %s seconds and rechecking %s', sleeper, ifname)
                time.sleep(sleeper)
                error, output = run(
                    f"ifconfig {ifname} | grep 'carp:' | awk '{{print $2}}'"
                )
                if output == 'MASTER':
                    logger.warning(
                        'Ignoring state on %s because it changed back to MASTER after '
                        '%s seconds.', ifname, sleeper,
                    )
                    return True

        """
        We check if we have at least one MASTER interface per group.
        If that turns out to be true we ignore the BACKUP state in one of the
        interfaces, otherwise we assume backup demoting carps.
        """
        ignoreall = True
        for group, carpint in list(fobj['groups'].items()):
            totoutput = 0
            ignore = False
            for i in carpint:
                error, output = run(f"ifconfig {i} | grep -c 'carp: MASTER'")
                totoutput += int(output)

                if not error and totoutput > 0:
                    ignore = True
                    break
            ignoreall &= ignore

        if ignoreall:
            logger.warning(
                'Ignoring DOWN state on %s because we still have interfaces that '
                'are UP.', ifname)
            return False

        # Start the critical section
        try:
            with LockFile(FAILOVER_EVENT, timeout=0):
                # The lockfile modules cleans up lockfiles if this script exits on it's own accord.
                # For reboots, /tmp is cleared by virtue of being a memory device.
                # If someone does a kill -9 on the script while it's running the lockfile
                # will get left dangling.
                logger.warning('Acquired failover backup lock')
                run('pkill -9 -f fenced')

                for iface in fobj['non_crit_interfaces']:
                    error, output = run(f"ifconfig {iface} | grep 'carp:' | awk '{{print $4}}'")
                    for vhid in output.split():
                        logger.warning('Setting advskew to 100 on non-critical interface %s', iface)
                        run(f'ifconfig {iface} vhid {vhid} advskew 100')

                for group in fobj['groups']:
                    for interface in fobj['groups'][group]:
                        error, output = run(f"ifconfig {interface} | grep 'carp:' | awk '{{print $4}}'")
                        for vhid in output.split():
                            logger.warning('Setting advskew to 100 on critical interface %s', interface)
                            run(f'ifconfig {interface} vhid {vhid} advskew 100')

                run('/sbin/pfctl -ef /etc/pf.conf.block')

                run('/usr/sbin/service watchdogd quietstop')

                # ticket 23361 enabled a feature to send email alerts when an unclean reboot occurrs.
                # TrueNAS HA, by design, has a triggered unclean shutdown.
                # If a controller is demoted to standby, we set a 4 sec countdown using watchdog.
                # If the zpool(s) can't export within that timeframe, we use watchdog to violently reboot the controller.
                # When this occurrs, the customer gets an email about an "Unauthorized system reboot".
                # The idea for creating a new sentinel file for watchdog related panics,
                # is so that we can send an appropriate email alert.

                # If we panic here, middleware will check for this file and send an appropriate email.
                # Ticket 39114
                try:
                    fd = os.open(WATCHDOG_ALERT_FILE, os.O_RDWR | os.O_CREAT | os.O_TRUNC)
                    epoch = int(time.time())
                    b = struct.pack("@i", epoch)
                    os.write(fd, b)
                    os.fsync(fd)
                    os.close(fd)
                except EnvironmentError as err:
                    logger.warning(err)

                run('watchdog -t 4')

                # make CTL to close backing storages, allowing pool to export
                run('/sbin/sysctl kern.cam.ctl.ha_role=1')

                # If the network is flapping, a backup node could get a master
                # event followed by an immediate backup event.  If the other node
                # is master and shoots down our master event we will immediately
                # run the code for the backup event, even though we are already backup.
                # So we use volumes as a sentinel to tell us if we did anything with
                # regards to exporting volumes.  If we don't export any volumes it's
                # ok to assume we don't need to do anything else associated with
                # transitioning to the backup state. (because we are already there)

                # Note this wouldn't be needed with a proper state engine.
                volumes = False
                for volume in fobj['volumes'] + fobj['phrasedvolumes']:
                    error, output = run(f'zpool list {volume}')
                    if not error:
                        volumes = True
                        logger.warning('Exporting %s', volume)
                        error, output = run(f'zpool export -f {volume}')
                        if error:
                            # the zpool status here is extranious.  The sleep
                            # is going to run off the watchdog and the system will reboot.
                            run(f'zpool status {volume}')
                            time.sleep(5)
                        logger.warning('Exported %s', volume)

                run('watchdog -t 0')
                try:
                    os.unlink(FAILOVER_ASSUMED_MASTER)
                except Exception:
                    pass

                # We also remove this file here, because this code path is executed on boot.
                # The middlewared process is removing the file and then sending an email as expected.
                # However, this python file is being called about 1min after middlewared and recreating the file on line 651.
                try:
                    os.unlink(WATCHDOG_ALERT_FILE)
                except EnvironmentError:
                    pass

                self.run_call('failover.status_refresh')
                self.run_call('service.restart', 'syslogd', {'ha_propagate': False})
                self.run_call('service.stop', 'mdns', {'ha_propagate': False})

                self.run_call('etc.generate', 'cron')

                if volumes:
                    run('/usr/sbin/service watchdogd quietstart')
                    self.run_call('service.stop', 'smartd', {'ha_propagate': False})
                    self.run_call('service.stop', 'collectd', {'ha_propagate': False})
                    self.run_call('jail.stop_on_shutdown')
                    for vm in (self.run_call('vm.query', [['status.state', '=', 'RUNNING']]) or []):
                        self.run_call('vm.poweroff', vm['id'], True)
                    run_async('echo "$(date), $(hostname), assume backup" | mail -s "Failover" root')

                for i in (
                    'ssh', 'iscsitarget',
                ):
                    verb = 'restart'
                    if i == 'iscsitarget':
                        if not self.run_call('iscsi.global.alua_enabled'):
                            verb = 'stop'

                    ret = self.run_call('datastore.query', 'services.services', [('srv_service', '=', i)])
                    if ret and ret[0]['srv_enable']:
                        self.run_call(f'service.{verb}', i, {'ha_propagate': False})

                if len(fobj['phrasedvolumes']):
                    detach_all_job = self.middleware.call_sync('failover.encryption_detachall')
                    detach_all_job.wait_sync()
                    if detach_all_job.error:
                        logger.error('Failed to detach geli providers: %s', detach_all_job.error)

                # Sync GELI and/or ZFS encryption keys from MASTER node
                self.middleware.call_sync('failover.sync_keys_from_remote_node')

        except AlreadyLocked:
            logger.warning('Failover event handler failed to acquire backup lockfile')


async def devd_carp_hook(middleware, data):
    if '@' not in data['subsystem']:
        return
    vhid, iface = data['subsystem'].split('@', 1)
    middleware.send_event('failover.carp_event', 'CHANGED', fields={
        'vhid': vhid,
        'interface': iface,
        'type': data['type'],
    })
    await middleware.call('failover.event', iface, vhid, data['type'])


def setup(middleware):
    middleware.event_register('failover.carp_event', 'Sent when a CARP state is changed.')
    middleware.register_hook('devd.carp', devd_carp_hook)
