from __future__ import annotations

import typing

from middlewared.api import api_method
from middlewared.api.current import (
    DockerEntry, ZFSResourceQuery,
    DockerStatusArgs, DockerStatusResult,
    DockerUpdateArgs, DockerUpdateResult,
    DockerNvidiaPresentArgs, DockerNvidiaPresentResult,
)
from middlewared.service import ConfigService, job, private


if typing.TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware


__all__ = ('DockerService',)


class DockerService(ConfigService[DockerEntry]):

    class Config:
        cli_namespace = 'app.docker'
        role_prefix = 'DOCKER'
        entry = DockerEntry
