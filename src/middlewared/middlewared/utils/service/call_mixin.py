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

    @typing.overload
    async def call2[**P, T](
        self,
        f: typing.Callable[P, typing.Coroutine[typing.Any, typing.Any, T]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        ...

    @typing.overload
    async def call2[**P, T](
        self,
        f: typing.Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        ...

    async def call2(
        self,
        f: typing.Callable[..., typing.Any],
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> typing.Any:
        app: App | None = kwargs.pop("app", None)
        audit_callback: AuditCallback | None = kwargs.pop("audit_callback", None)
        job_on_progress_cb: JobProgressCallback = kwargs.pop("job_on_progress_cb", None)
        pipes: Pipes | None = kwargs.pop("pipes", None)
        profile: bool = kwargs.pop("profile", False)
        return await self.middleware.call2(
            f,
            *args,
            app=app,
            audit_callback=audit_callback,
            job_on_progress_cb=job_on_progress_cb,
            pipes=pipes,
            profile=profile,
            **kwargs,
        )

    @typing.overload
    def call_sync2[**P, T](
        self,
        f: typing.Callable[P, typing.Coroutine[typing.Any, typing.Any, T]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        ...

    @typing.overload
    def call_sync2[**P, T](
        self,
        f: typing.Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        ...

    def call_sync2(
        self,
        f: typing.Callable[..., typing.Any],
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> typing.Any:
        app: App | None = kwargs.pop("app", None)
        audit_callback: AuditCallback | None = kwargs.pop("audit_callback", None)
        background: bool = kwargs.pop("background", False)
        job_on_progress_cb: JobProgressCallback = kwargs.pop("job_on_progress_cb", None)
        return self.middleware.call_sync2(
            f,
            *args,
            app=app,
            audit_callback=audit_callback,
            background=background,
            job_on_progress_cb=job_on_progress_cb,
            **kwargs,
        )
