from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource
from middlewared.utils.zfs import query_imported_fast_impl


class VolumeStatusAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.CRITICAL
    title = 'Pool Status Is Not Healthy'
    text = 'Pool %(volume)s state is %(state)s: %(status)s%(devices)s'
    proactive_support = True


class BootPoolStatusAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = 'Boot Pool Is Not Healthy'
    text = 'Boot pool status is %(status)s: %(status_detail)s.'
    proactive_support = True


class VolumeStatusAlertSource(ThreadedAlertSource):
    def check_sync(self):
        alerts = []
        boot_name = self.middleware.call_sync('boot.pool_name')
        pools = alerts = None
        for guid, info in query_imported_fast_impl().items():
            if info['status'] == 'ONLINE':
                continue

            if alerts is None:
                alerts = self.middleware.call_sync('alert.list')

            alert_already_generated = False
            for i in filter(lambda x: x['klass'] in ('VolumeStatus', 'BootPoolStatus'), alerts):
                # before we do anything expensive, let's make sure that we don't
                # already have an alert generated for this zpool
                if i['klass'] == 'BootPoolStatus' and info['name'] == boot_name:
                    # boot pool alert already generated
                    alert_already_generated = True
                    break
                elif i['klass'] == 'VolumeStatus' and info['name'] in i['args']:
                    # zpool alert has already been generated for this pool
                    alert_already_generated = True
                    break

            if alert_already_generated:
                continue

            if pools is None:
                try:
                    pools = self.middleware.call_sync('pool.query')
                except Exception:
                    # edge-case but could be that by the time we checked sysfs and then queried
                    # the pool using libzfs, the pool could have vanished
                    continue

            try:
                pool = [i for i in pools if i['name'] == info['name']][0]
            except IndexError:
                # shouldn't happen but our alert system has ugly behavior if we crash here
                continue

            if info['name'] == boot_name:
                alerts.append(Alert(
                    BootPoolStatusAlertClass,
                    {'status': pool['status'], 'status_detail': pool['status_detail']},
                ))
                continue

            if not pool['healthy'] or (pool['warning'] and pool['status_code'] != 'FEAT_DISABLED'):
                if self.middleware.call_sync('system.is_enterprise'):
                    try:
                        self.middleware.call_sync('enclosure.sync_zpool', pool['name'])
                    except Exception:
                        pass

                bad_vdevs, devices = [], ''
                if pool['topology']:
                    for vdev in self.middleware.call_sync('pool.flatten_topology', pool['topology']):
                        if vdev['type'] == 'DISK' and vdev['status'] != 'ONLINE':
                            name = vdev['guid']
                            if (ud := vdev.get('unavail_disk')):
                                name = f"{ud['model']} {ud['serial']}"

                            bad_vdevs.append(f"Disk {name} is {vdev['status']}")

                if bad_vdevs:
                    devices = (f'<br>The following devices are not healthy:'
                               f'<ul><li>{"</li><li>".join(bad_vdevs)}</li></ul>')

                alerts.append(Alert(VolumeStatusAlertClass, {
                    'volume': pool['name'],
                    'state': pool['status'],
                    'status': pool['status_detail'],
                    'devices': devices,
                }))

        return alerts
