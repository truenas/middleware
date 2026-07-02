from __future__ import annotations

import typing

from middlewared.utils.types import AuditCallback, JobProgressCallback

if typing.TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    import middlewared.main
    from middlewared.pipe import Pipes


class CallMixin:
    middleware: middlewared.main.Middleware

    @property
    def s(self) -> middlewared.main.ServiceContainer:
        return self.middleware.services

    # The callee's parameters are grafted onto this signature per call site by the `mypy_call2`
    # plugin; the keyword-only options below are the typed options it appends to every call.
    async def call2(
        self,
        f: typing.Callable[..., typing.Any],
        *args: typing.Any,
        app: App | None = None,
        audit_callback: AuditCallback | None = None,
        job_on_progress_cb: JobProgressCallback = None,
        job_silent: bool = False,
        pipes: Pipes | None = None,
        profile: bool = False,
        **kwargs: typing.Any,
    ) -> typing.Any:
        return await self.middleware.call2(
            f,
            *args,
            app=app,
            audit_callback=audit_callback,
            job_on_progress_cb=job_on_progress_cb,
            job_silent=job_silent,
            pipes=pipes,
            profile=profile,
            **kwargs,
        )

    # The callee's parameters are grafted onto this signature per call site by the `mypy_call2`
    # plugin; the keyword-only options below are the typed options it appends to every call.
    def call_sync2(
        self,
        f: typing.Callable[..., typing.Any],
        *args: typing.Any,
        app: App | None = None,
        audit_callback: AuditCallback | None = None,
        background: bool = False,
        job_on_progress_cb: JobProgressCallback = None,
        job_silent: bool = False,
        **kwargs: typing.Any,
    ) -> typing.Any:
        return self.middleware.call_sync2(
            f,
            *args,
            app=app,
            audit_callback=audit_callback,
            background=background,
            job_on_progress_cb=job_on_progress_cb,
            job_silent=job_silent,
            **kwargs,
        )
