import errno

from middlewared.api import api_method, Event
from middlewared.api.current import UpdateStatusArgs, UpdateStatusResult, UpdateStatusChangedEvent
from middlewared.service import private, Service
from middlewared.service_exception import CallError, ErrnoMixin, get_errname


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
        return await self.status_internal()

    @private
    async def status_internal(self, propagate_exception=False):
        try:
            try:
                applied = await self.middleware.call('cache.get', 'update.applied')
            except KeyError:
                applied = False
            if applied:
                raise CallError(
                    'System update was already applied, system reboot is required.',
                    ErrnoMixin.EREBOOTREQUIRED,
                )

            if await self.middleware.call('failover.licensed'):
                if await self.middleware.call('failover.disabled.reasons'):
                    raise CallError(
                        'HA is configured but currently unavailable.',
                        ErrnoMixin.EHAUNAVAILABLE,
                    )

            current_version = await self.middleware.call('system.version_short')
            config = await self.middleware.call('update.config')
            trains = await self.middleware.call('update.get_trains')

            current_train_name = await self.middleware.call('update.get_current_train_name', trains)
            current_profile = await self.middleware.call('update.current_version_profile')
            matches_profile = await self.middleware.call('update.profile_matches', current_profile, config['profile'])

            new_version = None
            for next_train in await self.middleware.call('update.get_next_trains_names', trains):
                releases = await self.middleware.call('update.get_train_releases', next_train)
                for version_number, version in reversed(releases.items()):
                    if await self.middleware.call('update.profile_matches', version['profile'], config['profile']):
                        new_version = {**version, 'train': next_train, 'version': version_number}
                        break

                if new_version is not None:
                    break
            else:
                raise CallError('No releases match specified update profile.', errno.ENOPKG)

            if new_version['version'] == current_version:
                new_version = None
            else:
                if not await self.middleware.call('update.can_update_to', new_version['version']):
                    raise CallError(
                        (
                            f'Currently installed version {current_version} is newer than the newest version '
                            f'{new_version["version"]} provided by train {next_train}.'
                        ),
                        errno.ENOPKG,
                    )

                new_version = await self.middleware.call('update.version_from_manifest', new_version)

            return self._result('NORMAL', {
                'status': {
                    'current_version': {
                        'train': current_train_name,
                        'profile': current_profile,
                        'matches_profile': matches_profile,
                    },
                    'new_version': new_version,
                },
                'update_download_progress': self.update_download_progress,
            })
        except Exception as e:
            if propagate_exception:
                raise

            if isinstance(e, CallError):
                return self._error(e.errno, e.errmsg)
            else:
                self.logger.exception('Failed to get update status')
                return self._error(errno.EFAULT, repr(e))

    def _result(self, code, data=None):
        result = {
            'code': code,
            'error': None,
            'status': None,
            **(data or {}),
        }

        if (
            self.update_download_progress is not None and
            result['status'] is not None and
            result['status']['new_version']['version'] == self.update_download_progress['version']
        ):
            result['update_download_progress'] = self.update_download_progress
        else:
            result['update_download_progress'] = None

        return result

    def _error(self, code, reason):
        return self._result('ERROR', {
            'error': {
                'errname': get_errname(code),
                'reason': reason,
            }
        })

    @private
    async def set_update_download_progress(self, progress, update_status):
        self.update_download_progress = progress
        self.middleware.send_event('update.status', 'CHANGED', status={
            **update_status,
            'update_download_progress': progress,
        })
