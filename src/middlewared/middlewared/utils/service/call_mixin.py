from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    import middlewared.main
    from middlewared.pipe import Pipes

AuditCallback = typing.Callable[[str], None] | None
JobProgressCallback = typing.Callable[[dict], None] | None


class CallMixin:
    @property
    def s(self) -> middlewared.main.ServiceContainer:
        return self.middleware.services

    @typing.overload
    async def call2[**P, T](
        self,
        f: typing.Callable[P, typing.Coroutine[typing.Any, typing.Any, T]],
        *args: P.args,
        app: App | None = None,
        audit_callback: AuditCallback = None,
        job_on_progress_cb: JobProgressCallback = None,
        pipes: Pipes | None = None,
        profile: bool = False,
        **kwargs: P.kwargs
    ) -> T:
        ...

    @typing.overload
    async def call2[**P, T](
        self,
        f: typing.Callable[P, T],
        *args: P.args,
        app: App | None = None,
        audit_callback: AuditCallback = None,
        job_on_progress_cb: JobProgressCallback = None,
        pipes: Pipes | None = None,
        profile: bool = False,
        **kwargs: P.kwargs,
    ) -> T:
        ...

    async def call2(
        self,
        f: typing.Callable[..., typing.Any],
        *args: typing.Any,
        app: App | None = None,
        audit_callback: AuditCallback = None,
        job_on_progress_cb: JobProgressCallback = None,
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
            pipes=pipes,
            profile=profile,
            **kwargs,
        )

    @typing.overload
    def call_sync2[**P, T](
        self,
        f: typing.Callable[P, typing.Coroutine[typing.Any, typing.Any, T]],
        *args: P.args,
        app: App | None = None,
        audit_callback: AuditCallback = None,
        background: bool = False,
        job_on_progress_cb: JobProgressCallback = None,
        **kwargs: P.kwargs,
    ) -> T:
        ...

    @typing.overload
    def call_sync2[**P, T](
        self,
        f: typing.Callable[P, T],
        *args: P.args,
        app: App | None = None,
        audit_callback: AuditCallback = None,
        background: bool = False,
        job_on_progress_cb: JobProgressCallback = None,
        **kwargs: P.kwargs,
    ) -> T:
        ...

    def call_sync2(
        self,
        f: typing.Callable[..., typing.Any],
        *args: typing.Any,
        app: App | None = None,
        audit_callback: AuditCallback = None,
        background: bool = False,
        job_on_progress_cb: JobProgressCallback = None,
        **kwargs: typing.Any,
    ) -> typing.Any:
        return self.middleware.call_sync2(
            f,
            *args,
            app=app,
            audit_callback=audit_callback,
            background=background,
            job_on_progress_cb=job_on_progress_cb,
            **kwargs,
        )
