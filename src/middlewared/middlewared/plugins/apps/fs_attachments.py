from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.common.attachment import FSAttachmentDelegate

if TYPE_CHECKING:
    from middlewared.main import Middleware


class AppFSAttachmentDelegate(FSAttachmentDelegate):
    name = "apps"
    title = "Apps"
    # Apps depend on Docker, so they start after and stop before Docker
    priority = 5

    async def query(
        self, path: str, enabled: bool, options: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        apps_attached: list[dict[str, str]] = []
        for app in await self.call2(self.s.app.query):
            # We don't want to consider those apps which fit in the following criteria:
            # - app has no volumes
            # - app is stopped and we are looking for enabled apps
            # - app is not stopped and we are looking for disabled apps
            if not (skip_app := not app.active_workloads.volumes):
                if enabled:
                    skip_app |= app.state == "STOPPED"
                else:
                    skip_app |= app.state != "STOPPED"

            if skip_app:
                continue

            if await self.middleware.call(
                "filesystem.is_child", [volume.source for volume in app.active_workloads.volumes], path
            ):
                apps_attached.append({
                    "id": app.name,
                    "name": app.name,
                })

        return apps_attached

    async def delete(self, attachments: list[dict[str, str]]) -> None:
        for attachment in attachments:
            try:
                await (await self.call2(self.s.app.stop, attachment["id"])).wait(raise_error=True)
            except Exception:
                self.middleware.logger.error("Unable to stop %r app", attachment["id"], exc_info=True)

    async def toggle(self, attachments: list[dict[str, str]], enabled: bool) -> None:
        # if enabled is true - we are going to ignore that as we don't want to scale up releases
        # automatically when a path becomes available
        for attachment in ([] if enabled else attachments):
            try:
                await (await self.call2(self.s.app.stop, attachment["id"])).wait(raise_error=True)
            except Exception:
                self.middleware.logger.error("Unable to stop %r app", attachment["id"], exc_info=True)

    async def stop(self, attachments: list[dict[str, str]]) -> None:
        await self.toggle(attachments, False)

    async def start(self, attachments: list[dict[str, str]]) -> None:
        await self.toggle(attachments, True)


async def setup(middleware: Middleware) -> None:
    middleware.create_task(
        middleware.call("pool.dataset.register_attachment_delegate", AppFSAttachmentDelegate(middleware))
    )
