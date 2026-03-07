from __future__ import annotations

import typing

from middlewared.api import api_method
from middlewared.api.base import Event
from middlewared.api.current import (
    DockerEntry, ZFSResourceQuery, DockerStateChangedEvent,
    DockerStatusArgs, DockerStatusResult,
    DockerUpdateArgs, DockerUpdateResult,
    DockerNvidiaPresentArgs, DockerNvidiaPresentResult,
)
from middlewared.service import GenericConfigService, job, periodic, private

from .config import DockerConfigServicePart
from .state_management import (
    after_start_check, before_start_check, initialize_state, set_status as docker_set_status, start_service,
    validate_state, periodic_check, terminate, terminate_timeout
)
from .state_utils import Status

if typing.TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware


__all__ = ('DockerService',)


class DockerService(GenericConfigService[DockerEntry]):

    class Config:
        cli_namespace = 'app.docker'
        role_prefix = 'DOCKER'
        entry = DockerEntry
        events = [
            Event(
                name='docker.state',
                description='Docker state events',
                roles=['DOCKER_READ'],
                models={'CHANGED': DockerStateChangedEvent},
            )
        ]

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = DockerConfigServicePart(self.context)

    @private
    async def after_start_check(self) -> None:
        return await after_start_check(self.context)

    @private
    async def before_start_check(self) -> None:
        await before_start_check(self.context)

    @private
    async def initialize_state(self) -> None:
        return await initialize_state(self.context)

    @private
    @periodic(interval=86400)
    async def state_periodic_check(self) -> None:
        await periodic_check(self.context)

    @private
    async def set_status(self, new_status: str, extra: str | None = None) -> None:
        await docker_set_status(self.context, new_status, extra)

    @private
    async def start_service(self) -> None:
        await start_service(self.context)

    @private
    async def terminate(self) -> None:
        await terminate(self.context)

    @private
    async def terminate_timeout(self) -> int:
        return terminate_timeout()

    @private
    async def validate_state(self, raise_error: bool = True) -> None:
        await validate_state(self.context, raise_error)


async def _event_system_ready(middleware: Middleware, event_type: str, args: typing.Any) -> None:
    # we ignore the 'ready' event on an HA system since the failover event plugin
    # is responsible for starting this service
    if await middleware.call('failover.licensed'):
        return

    if (await middleware.call2(middleware.s.docker.config)).pool:
        middleware.create_task(middleware.call2(middleware.s.docker.start_service, True))
    else:
        await middleware.call2(middleware.s.docker.set_status, Status.UNCONFIGURED.value)


async def handle_license_update(middleware: Middleware, *args, **kwargs):
    if not await middleware.call('docker.license_active'):
        # We will like to stop docker in this case
        await middleware.call('service.control', 'STOP', 'docker')


async def setup(middleware: Middleware) -> None:
    middleware.event_subscribe('system.ready', _event_system_ready)
    await middleware.call2(middleware.s.docker.initialize_state)
    middleware.register_hook('system.post_license_update', handle_license_update)
