from __future__ import annotations

import os
import typing

from middlewared.common.attachment import FSAttachmentDelegate

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


class DockerFSAttachmentDelegate(FSAttachmentDelegate):
    name = 'docker'
    title = 'Docker'
    service = 'docker'
    # Docker must start before apps, and stop after apps
    priority = 10

    async def query(self, path: str, enabled: bool, options: dict[str, str] | None = None) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []

        docker_config = await self.call2(self.s.docker.config)
        if not docker_config.pool:
            return results

        query_dataset = os.path.relpath(path, '/mnt')  # noqa: ASYNC240
        if query_dataset in (docker_config.dataset, docker_config.pool) or query_dataset.startswith(
            f'{docker_config.dataset}/'
        ):
            results.append({'id': docker_config.pool})

        return results

    async def get_attachment_name(self, attachment: dict[str, str]) -> str:
        return attachment['id']

    async def delete(self, attachments: list[dict[str, str]]) -> None:
        if attachments:
            await (await self.call2(self.s.docker.update, {'pool': None})).wait(raise_error=True)

    async def toggle(self, attachments: list[dict[str, str]], enabled: bool) -> None:
        await getattr(self, 'start' if enabled else 'stop')(attachments)

    async def stop(self, attachments: list[dict[str, str]]) -> None:
        if not attachments:
            return
        try:
            await (await self.middleware.call('service.control', 'STOP', self.service)).wait(raise_error=True)
            umount_job = await self.call2(self.s.docker.umount_docker_ds)
            if umount_job:
                await umount_job.wait(raise_error=True)
        except Exception as e:
            self.middleware.logger.error('Failed to stop docker: %s', e)

    async def start(self, attachments: list[dict[str, str]]) -> None:
        if not attachments:
            return
        try:
            await self.call2(self.s.docker.start_service, True)
        except Exception:
            self.middleware.logger.error('Failed to start docker')


async def setup(middleware: Middleware) -> None:
    await middleware.call(
        'pool.dataset.register_attachment_delegate',
        DockerFSAttachmentDelegate(middleware)
    )
