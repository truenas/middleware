from __future__ import annotations

import typing

from middlewared.api import api_method
from middlewared.api.current import (
    AppImageDeleteArgs,
    AppImageDeleteOptions,
    AppImageDeleteResult,
    AppImageDockerhubRateLimitArgs,
    AppImageDockerhubRateLimitInfo,
    AppImageDockerhubRateLimitResult,
    AppImageEntry,
    AppImagePull,
    AppImagePullArgs,
    AppImagePullResult,
    QueryOptions,
)
from middlewared.service import GenericCRUDService, job, private

from .delete import delete_image_action
from .dockerhub_ratelimit import get_dockerhub_rate_limit
from .pull import pull_image_action
from .query import get_image_instance, query_images
from .update_alerts import (
    check_update_impl,
    clear_update_flag_impl,
    get_update_cache_impl,
)

if typing.TYPE_CHECKING:
    from middlewared.job import Job

    class _QueryGetOptions(QueryOptions):
        get: typing.Literal[True]
        count: typing.Literal[False]

    class _QueryCountOptions(QueryOptions):
        count: typing.Literal[True]
        get: typing.Literal[False]


__all__ = ("AppImageService",)


class AppImageService(GenericCRUDService[AppImageEntry, str]):
    class Config:
        namespace = "app.image"
        cli_namespace = "app.image"
        role_prefix = "APPS"
        entry = AppImageEntry
        generic = True
        event_send = False
        event_register = False
        datastore_primary_key = "id"

    @typing.overload  # type: ignore[override]
    def query(  # type: ignore[overload-overlap]
        self,
        filters: list[typing.Any],
        options: _QueryCountOptions,
    ) -> int: ...

    @typing.overload
    def query(  # type: ignore[overload-overlap]
        self,
        filters: list[typing.Any],
        options: _QueryGetOptions,
    ) -> AppImageEntry: ...

    @typing.overload
    def query(
        self,
        filters: list[typing.Any] | None = None,
        options: QueryOptions | None = None,
    ) -> list[AppImageEntry]: ...

    def query(
        self,
        filters: list[typing.Any] | None = None,
        options: QueryOptions | None = None,
    ) -> list[AppImageEntry] | AppImageEntry | int:
        """
        Query all docker images with ``query-filters`` and ``query-options``.

        The following ``query-options.extra`` options are supported:

        ``parse_tags`` *(bool)*:
            Include normalized tags on each entry.
        """
        return query_images(self.context, filters or [], options or QueryOptions())

    async def get_instance(
        self,
        id_: str,
        options: QueryOptions | None = None,
    ) -> AppImageEntry:
        """Returns instance matching `id_`. Raises InstanceNotFound if missing."""
        return await self.context.to_thread(
            get_image_instance,
            self.context,
            id_,
            options or QueryOptions(),
        )

    @api_method(
        AppImagePullArgs,
        AppImagePullResult,
        roles=["APPS_WRITE"],
        check_annotations=True,
    )
    @job()
    def pull(self, job: Job, image_pull: AppImagePull) -> None:
        """
        Pull a docker image.
        """
        return pull_image_action(self.context, job, image_pull)

    @api_method(AppImageDeleteArgs, AppImageDeleteResult, check_annotations=True)
    def do_delete(self, image_id: str, options: AppImageDeleteOptions) -> typing.Literal[True]:
        """
        Delete docker image ``image_id``.
        """
        return delete_image_action(self.context, image_id, options)

    @api_method(
        AppImageDockerhubRateLimitArgs,
        AppImageDockerhubRateLimitResult,
        roles=["APPS_READ"],
        check_annotations=True,
    )
    async def dockerhub_rate_limit(self) -> AppImageDockerhubRateLimitInfo:
        """
        Returns the current rate-limit information for the Docker Hub registry.

        Please refer to https://docs.docker.com/docker-hub/download-rate-limit/ for more information.
        """
        return await get_dockerhub_rate_limit(self.context)

    # Previously the private `app.image.op.*` service. Consolidated onto `app.image` as private
    # methods since there are external consumers (docker, apps, service_ plugins).
    @private
    async def check_update(self) -> None:
        await check_update_impl(self.context)

    @private
    async def get_update_cache(self, normalized: bool = False) -> dict[str, bool]:
        return await get_update_cache_impl(normalized)

    @private
    async def clear_update_flag_for_tag(self, tag: str) -> None:
        await clear_update_flag_impl(tag)
