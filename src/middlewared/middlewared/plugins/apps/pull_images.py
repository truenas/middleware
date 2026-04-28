from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api.current import AppEntry, AppPullImages
from middlewared.plugins.apps_images.utils import normalize_reference
from middlewared.service import ServiceContext

from .compose_utils import compose_action
from .crud import get_instance

if TYPE_CHECKING:
    from middlewared.job import Job


def outdated_docker_images_for_app(context: ServiceContext, app_name: str) -> list[str]:
    app = get_instance(context, app_name)
    # FIXME: Fix this usage
    image_update_cache = context.middleware.call_sync('app.image.op.get_update_cache', True)
    images = []
    for image_tag in app.active_workloads.images:
        if image_update_cache.get(normalize_reference(image_tag)['complete_tag']):
            images.append(image_tag)

    return images


def pull_images_for_app(context: ServiceContext, job: Job, app_name: str, options: AppPullImages) -> None:
    app = get_instance(context, app_name)
    return pull_images_internal(context, app_name, app, options, job)


def pull_images_internal(
    context: ServiceContext, app_name: str, app: AppEntry, options: AppPullImages, job: Job | None = None,
) -> None:
    if job is not None:
        job.set_progress(20, 'Pulling app images')

    compose_action(app_name, app.version, action='pull')
    if job is not None:
        job.set_progress(80 if options.redeploy else 100, 'Images pulled successfully')

    # We will update image cache so that it reflects the fact that image has been pulled again
    # We won't really check again here but rather just update the cache directly because we know
    # compose action didn't fail and that means the pull succeeded and we should have the newer version
    # already in the system
    for image_tag in app.active_workloads.images:
        context.middleware.call_sync('app.image.op.clear_update_flag_for_tag', image_tag)

    if options.redeploy:
        context.call_sync2(context.s.app.redeploy, app_name).wait_sync(raise_error=True)
        if job is not None:
            job.set_progress(100, 'App redeployed successfully')
