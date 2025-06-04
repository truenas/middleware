from middlewared.api import api_method, Event
from middlewared.api.current import UpdateStatusArgs, UpdateStatusResult, UpdateStatusChangedEvent
from middlewared.service import private, Service


class UpdateService(Service):

    class Config:
        events = [
            Event(
                name='update.status',
                description='Updated on update status changes.',
                roles=['SYSTEM_UPDATE_READ'],
                models={
                    'CHANGED': UpdateStatusChangedEvent,
                },
            ),
        ]

    update_download_progress = None

    @api_method(UpdateStatusArgs, UpdateStatusResult, roles=['SYSTEM_UPDATE_READ'])
    async def status(self):
        """
        Update status.
        """
        try:
            applied = await self.middleware.call('cache.get', 'update.applied')
        except KeyError:
            applied = False
        if applied:
            return self._result('REBOOT_REQUIRED')

        if await self.middleware.call('failover.licensed'):
            if await self.middleware.call('failover.disabled.reasons'):
                return self._result('HA_UNAVAILABLE')

        try:
            current_version = await self.middleware.call('system.version_short')
            config = await self.middleware.call('update.config')
            trains = await self.middleware.call('update.get_trains')

            current_train_name = await self.middleware.call('update.get_current_train_name', trains)
            current_train_profile = trains['trains'][current_train_name]['update_profile']
            matches_profile = await self.middleware.call(
                'update.profile_matches', current_train_profile, config['profile'],
            )

            update_train_name = None
            for train_name, train_data in trains['trains'].items():
                if await self.middleware.call(
                    'update.profile_matches', train_data['update_profile'], config['profile'],
                ):
                    update_train_name = train_name

            if update_train_name is None:
                return self._result('ERROR', {'error': 'No trains match specified update profile.'})

            update_train_manifest = await self.middleware.call('update.get_train_manifest', update_train_name)

            if update_train_manifest['version'] == current_version:
                new_version = None
            else:
                new_version_number = update_train_manifest['version']
                if not await self.middleware.call('update.can_update_to', new_version_number):
                    return self._result('ERROR', {
                        'error': (
                            f'Currently installed version {current_version} is newer than the newest version '
                            f'{new_version_number} provided by train {update_train_manifest}.'
                        ),
                    })

                new_version = await self.middleware.call('update.version_from_manifest', update_train_manifest)
            return self._result('NORMAL', {
                'status': {
                    'current_train': {
                        'name': current_train_name,
                        'profile': current_train_profile,
                        'matches_profile': matches_profile,
                    },
                    'new_version': new_version,
                },
                'update_download_progress': self.update_download_progress,
            })
        except Exception as e:
            return self._result('ERROR', {
                'error': repr(e),
            })

    def _result(self, code, data=None):
        return {
            'code': code,
            'error': None,
            'status': None,
            'update_download_progress': self.update_download_progress,
            **(data or {}),
        }

    @private
    async def set_update_download_progress(self, progress, update_status):
        self.update_download_progress = progress
        self.middleware.send_event('update.status', 'CHANGED', status={
            **update_status,
            'update_download_progress': progress,
        })
