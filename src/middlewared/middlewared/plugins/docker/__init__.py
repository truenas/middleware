from __future__ import annotations

import typing

from middlewared.api import api_method
from middlewared.api.current import (
    DockerEntry, ZFSResourceQuery,
    DockerStatusArgs, DockerStatusResult,
    DockerUpdateArgs, DockerUpdateResult,
    DockerNvidiaPresentArgs, DockerNvidiaPresentResult,
)
from middlewared.service import GenericConfigService, job, private

from .config import DockerConfigServicePart


if typing.TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware


__all__ = ('DockerService',)


class DockerService(GenericConfigService[DockerEntry]):

    class Config:
        cli_namespace = 'app.docker'
        role_prefix = 'DOCKER'
        entry = DockerEntry

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = DockerConfigServicePart(self.context)
