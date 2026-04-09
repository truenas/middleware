from __future__ import annotations

from typing import Any, TYPE_CHECKING

from middlewared.service import Service

from .custom_app_ops import convert_to_custom_app, create_custom_app


if TYPE_CHECKING:
    from middlewared.api.current import AppEntry
    from middlewared.job import Job


class AppCustomService(Service):

    class Config:
        namespace = 'app.custom'
        private = True

    def convert(self, job: Job, app_name: str) -> AppEntry:
        return convert_to_custom_app(self.context, job, app_name)

    def create(self, data: dict[str, Any], job: Job | None = None, progress_base: int = 0) -> AppEntry:
        return create_custom_app(self.context, data, job, progress_base)
