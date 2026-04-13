from middlewared.api.current import ISCSIGlobalSessionsItem
from middlewared.plugins.fc.utils import wwn_as_colon_hex
from middlewared.service import private, Service, filterable_api_method
from middlewared.service_exception import MatchNotFound
from middlewared.utils.filter_list import filter_list


class ISCSIGlobalService(Service):
    class Config:
        namespace = 'iscsi.global'

    @filterable_api_method(
        item=ISCSIGlobalSessionsItem, roles=['SHARING_ISCSI_GLOBAL_READ']
    )
    def sessions(self, filters, options):
        """
        Get a list of currently running iSCSI sessions. This includes initiator and target names
        and the unique connection IDs.
        """
        global_info = self.middleware.call_sync('iscsi.global.config')
        if self.middleware.call_sync('iscsi.global.lio_enabled'):
            raw = self.middleware.call_sync('iscsi.lio.sessions', global_info)
        else:
            raw = self.middleware.call_sync('iscsi.scst.sessions', global_info)
        return filter_list(raw, filters, options)

    @private
    def resync_readonly_property_for_zvol(self, id_, read_only_value):
        try:
            extent = self.middleware.call_sync(
                'iscsi.extent.query',
                [['enabled', '=', True], ['path', '=', f'zvol/{id_}']],
                {'get': True},
            )
            ro = True if read_only_value.lower() == 'on' else False
            if extent['ro'] != ro:
                self.middleware.call_sync(
                    'iscsi.extent.update', extent['id'], {'ro': ro}
                )
        except MatchNotFound:
            return

    @private
    def resync_lun_size_for_zvol(self, id_):
        if not self.middleware.call_sync('service.started', 'iscsitarget'):
            return

        extent = self.middleware.call_sync(
            'iscsi.extent.query',
            [['enabled', '=', True], ['path', '=', f'zvol/{id_}']],
            {'select': ['name', 'enabled', 'path']},
        )
        if not extent:
            return

        name = extent[0]['name']
        try:
            if self.middleware.call_sync('iscsi.global.lio_enabled'):
                self.middleware.call_sync('iscsi.lio.resync_lun_size_for_zvol', name)
            else:
                self.middleware.call_sync('iscsi.scst.resync_lun_size_for_zvol', name)
        except Exception as e:
            if isinstance(e, OSError) and e.errno == 124:
                # 124 == Wrong medium type
                # This is raised when all the iscsi targets are removed causing /etc/scst.conf to
                # be written with a "blank" config. Once this occurs, any time a new iscsi target
                # is added and the size gets changed, it will raise this error. In my testing,
                # SCST sees the zvol size change and so does the initiator so it's safe to ignore.
                pass
            else:
                self.logger.warning(
                    'Failed to resync lun size for %r', name, exc_info=True
                )

    @private
    def resync_lun_size_for_file(self, path):
        if not self.middleware.call_sync('service.started', 'iscsitarget'):
            return

        extent = self.middleware.call_sync(
            'iscsi.extent.query',
            [['enabled', '=', True], ['type', '=', 'FILE'], ['path', '=', path]],
            {'select': ['enabled', 'type', 'path', 'name']},
        )
        if not extent:
            return

        name = extent[0]['name']
        try:
            if self.middleware.call_sync('iscsi.global.lio_enabled'):
                self.middleware.call_sync('iscsi.lio.resync_lun_size_for_file', name)
            else:
                self.middleware.call_sync('iscsi.scst.resync_lun_size_for_file', name)
        except Exception as e:
            if isinstance(e, OSError) and e.errno == 124:
                # 124 == Wrong medium type
                # This is raised when all the iscsi targets are removed causing /etc/scst.conf to
                # be written with a "blank" config. Once this occurs, any time a new iscsi target
                # is added and the size gets changed, it will raise this error. In my testing,
                # SCST sees the zvol size change and so does the initiator so it's safe to ignore.
                pass
            else:
                self.logger.warning(
                    'Failed to resync lun size for %r', name, exc_info=True
                )

    @private
    async def terminate_luns_for_pool(self, pool_name):
        if not await self.middleware.call('service.started', 'iscsitarget'):
            return

        g_config = await self.middleware.call('iscsi.global.config')
        targets = {t['id']: t for t in await self.middleware.call('iscsi.target.query')}
        extents = {
            t['id']: t
            for t in await self.middleware.call(
                'iscsi.extent.query',
                [['enabled', '=', True]],
                {'select': ['enabled', 'path', 'id']},
            )
        }
        lio = await self.middleware.call('iscsi.global.lio_enabled')
        alua = await self.middleware.call('iscsi.global.alua_enabled')

        node = await self.middleware.call('failover.node')
        fcports_by_target = {}
        for fp in await self.middleware.call('fcport.query'):
            tid = fp['target']['id']
            wwpn_str = fp['wwpn_b'] if node == 'B' else fp['wwpn']
            fcports_by_target.setdefault(tid, [])
            fcports_by_target[tid].append(wwn_as_colon_hex(wwpn_str))

        for associated_target in filter(
            lambda a: (
                a['extent'] in extents
                and extents[a['extent']]['path'].startswith(f'zvol/{pool_name}/')
            ),
            await self.middleware.call('iscsi.targetextent.query'),
        ):
            target = targets[associated_target['target']]
            lun_id = associated_target['lunid']
            mode = target['mode']
            self.middleware.logger.debug(
                'Terminating associated target %r', associated_target['id']
            )

            if mode in ('ISCSI', 'BOTH'):
                iqn = f'{g_config["basename"]}:{target["name"]}'
                if lio:
                    await self.middleware.call(
                        'iscsi.lio.remove_target_lun', iqn, lun_id
                    )
                else:
                    await self.middleware.call(
                        'iscsi.scst.remove_target_lun', iqn, lun_id
                    )

            if mode in ('FC', 'BOTH'):
                for wwpn in fcports_by_target.get(target['id'], []):
                    if lio:
                        await self.middleware.call(
                            'iscsi.lio.remove_target_lun', wwpn, lun_id
                        )
                    else:
                        await self.middleware.call(
                            'iscsi.scst.remove_target_lun', wwpn, lun_id
                        )

            if not lio and alua:
                ha_iqn = f'{g_config["basename"]}:HA:{target["name"]}'
                await self.middleware.call(
                    'iscsi.scst.remove_target_lun', ha_iqn, lun_id
                )
