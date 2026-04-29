from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.api.current import AppImagePull
from middlewared.plugins.apps.ix_apps.docker.images import pull_image
from middlewared.service import ServiceContext

from .utils import get_normalized_auth_config

if TYPE_CHECKING:
    from middlewared.job import Job


def pull_image_action(
    context: ServiceContext, job: Job, data: AppImagePull,
) -> None:
    def callback(entry: Any) -> None:
        # Just having some sanity checks in place in case we come across some weird registry
        if not isinstance(entry, dict) or any(
            k not in entry for k in ('progressDetail', 'status')
        ) or entry['status'].lower().strip() not in ('pull complete', 'downloading'):
            return

        if entry['status'].lower().strip() == 'pull complete':
            job.set_progress(95, 'Image downloaded, doing post processing')
            return

        progress = entry['progressDetail']
        if not isinstance(progress, dict) or any(
            k not in progress for k in ('current', 'total')
        ) or progress['current'] > progress['total']:
            return

        job.set_progress((progress['current'] / progress['total']) * 90, 'Pulling image')

    context.call_sync2(context.s.docker.validate_state)
    image_tag = data.image
    if data.auth_config is not None:
        username: str | None = data.auth_config.username
        password: str | None = data.auth_config.password
        registry_uri: str | None = data.auth_config.registry_uri
    else:
        # If user has not provided any auth creds, try to see if the registry to which the image
        # belongs has saved creds and use those.
        app_registries = {
            registry.uri: registry
            for registry in context.call_sync2(context.s.app.registry.query)
        }
        fallback = get_normalized_auth_config(app_registries, image_tag)
        username = fallback.get('username')
        password = fallback.get('password')
        registry_uri = fallback.get('registry_uri')

    pull_image(image_tag, callback, username, password, registry_uri)
    job.set_progress(100, f'{image_tag!r} image pulled successfully')
