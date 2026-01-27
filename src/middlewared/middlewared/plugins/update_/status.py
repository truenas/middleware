from __future__ import annotations

import errno

from middlewared.api.current import (
    UpdateStatus, UpdateStatusCurrentVersion, UpdateStatusError, UpdateStatusStatus, UpdateDownloadProgress,
)
from middlewared.service import ServiceContext
from middlewared.service_exception import CallError, ErrnoMixin, get_errname  # type: ignore

from .trains import ReleaseManifest
from .trains import get_trains, get_train_releases, get_current_train_name, get_next_trains_names
from .profile_ import current_version_profile, profile_matches
from .version import can_update_to, version_from_manifest


# Module-level state
_update_download_progress: UpdateDownloadProgress | None = None


async def status(context: ServiceContext) -> UpdateStatus:
    return await status_internal(context)


async def status_internal(context: ServiceContext, propagate_exception: bool = False) -> UpdateStatus:
    try:
        try:
            applied = await context.middleware.call('cache.get', 'update.applied')
        except KeyError:
            applied = False
        if applied:
            raise CallError(
                'System update was already applied, system reboot is required.',
                ErrnoMixin.EREBOOTREQUIRED,
            )

        if await context.middleware.call('failover.licensed'):
            if await context.middleware.call('failover.disabled.reasons'):
                raise CallError(
                    'HA is configured but currently unavailable.',
                    ErrnoMixin.EHAUNAVAILABLE,
                )

        current_version = await context.middleware.call('system.version_short')
        config = await context.call2(context.s.update.config)
        trains = await get_trains(context)

        current_train_name = await get_current_train_name(context, trains)
        current_profile = await current_version_profile(context)
        matches_profile = await profile_matches(context, current_profile, config.profile)

        new_version = None
        for next_train in await get_next_trains_names(context, trains):
            releases = await get_train_releases(context, next_train)
            for version_number, version in reversed(releases.items()):
                if await profile_matches(context, version.profile, config.profile):
                    new_version = ReleaseManifest(**{**version.model_dump(), "train": next_train,
                                                     "version": version_number})
                    break

            if new_version is not None:
                break
        else:
            raise CallError('No releases match specified update profile.', errno.ENOPKG)

        if new_version.version == current_version:
            status_new_version = None
        else:
            if not await can_update_to(context, new_version.version):
                raise CallError(
                    (
                        f'Currently installed version {current_version} is newer than the newest version '
                        f'{new_version.version} provided by train {next_train}.'
                    ),
                    errno.ENOPKG,
                )

            status_new_version = await version_from_manifest(context, new_version)

        return _result(
            context,
            'NORMAL',
            status=UpdateStatusStatus(
                current_version=UpdateStatusCurrentVersion(
                    train=current_train_name,
                    profile=current_profile,
                    matches_profile=matches_profile,
                ),
                new_version=status_new_version,
            ),
        )
    except Exception as e:
        if propagate_exception:
            raise

        if isinstance(e, CallError):
            return _error(context, e.errno, e.errmsg)
        else:
            context.logger.exception('Failed to get update status')
            return _error(context, errno.EFAULT, repr(e))


def _result(
    context: ServiceContext,
    code: str,
    status: UpdateStatusStatus | None = None,
    error: UpdateStatusError | None = None,
) -> UpdateStatus:
    if (
        _update_download_progress is not None and
        status is not None and
        status.new_version is not None and
        status.new_version.version == _update_download_progress.version
    ):
        update_download_progress = _update_download_progress
    else:
        update_download_progress = None

    return UpdateStatus(code=code, status=status, error=error, update_download_progress=update_download_progress)


def _error(context: ServiceContext, code: int, reason: str) -> UpdateStatus:
    return _result(context, 'ERROR', error=UpdateStatusError(errname=get_errname(code), reason=reason))


async def set_update_download_progress(
    context: ServiceContext,
    progress: UpdateDownloadProgress | None,
    update_status: UpdateStatus,
) -> None:
    global _update_download_progress
    _update_download_progress = progress
    context.middleware.send_event('update.status', 'CHANGED', status={
        **update_status.model_dump(),
        'update_download_progress': progress,
    })
