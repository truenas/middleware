from __future__ import annotations

import asyncio
import errno
import os
from typing import TYPE_CHECKING, Any, Literal, overload

from middlewared.alert.source.deprecated_service import DeprecatedServiceAlert
from middlewared.api import api_method
from middlewared.api.current import (
    QueryFilters,
    QueryOptions,
    ServiceControlArgs,
    ServiceControlResult,
    ServiceEntry,
    ServiceOptions,
    ServiceStartedArgs,
    ServiceStartedOrEnabledArgs,
    ServiceStartedOrEnabledResult,
    ServiceStartedResult,
    ServiceUpdate,
    ServiceUpdateArgs,
    ServiceUpdateResult,
)
from middlewared.service import CallError, CRUDService, filterable_api_method, job, periodic, private
from middlewared.service_exception import MatchNotFound, ValidationError
import middlewared.sqlalchemy as sa
from middlewared.utils.filter_list import filter_getattrs, filter_list
from middlewared.utils.os import terminate_pid

from .services.all import all_services
from .services.base_interface import IdentifiableServiceInterface
from .services.dbus_router import ServiceActionError
from .utils import app_has_write_privilege_for_service

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.api.current import QueryOptionsCount, QueryOptionsGet
    from middlewared.job import Job
    from middlewared.main import Middleware
    from middlewared.utils.types import AuditCallback

    from .services.base_interface import ServiceInterface
    from .services.base_state import ServiceState


class ServiceModel(sa.Model):
    __tablename__ = 'services_services'

    id = sa.Column(sa.Integer(), primary_key=True)
    srv_service = sa.Column(sa.String(120))
    srv_enable = sa.Column(sa.Boolean(), default=False)


class ServiceService(CRUDService[ServiceEntry]):

    class Config:
        cli_namespace = "service"
        datastore_prefix = 'srv_'
        datastore_extend = 'service.service_extend'
        datastore_extend_context = 'service.service_extend_context'
        role_prefix = "SERVICE"
        entry = ServiceEntry
        generic = True

    @private
    async def service_extend_context(
        self,
        services_or_service: dict[str, Any],
        extra: dict[str, Any],
    ) -> dict[str, Any]:
        if not extra.get('include_state', True):
            return {}

        if isinstance(services_or_service, list):
            services = services_or_service
        else:
            services = [services_or_service]

        jobs = {
            asyncio.ensure_future(self.get_state(service['service'])): service
            for service in services
        }

        if jobs:
            done, pending = await asyncio.wait(list(jobs.keys()), timeout=15)

        def result(task: asyncio.Task[ServiceState]) -> dict[str, Any] | None:
            """
            Method to handle results of the coroutines.
            In case of error or timeout, provide UNKNOWN state.
            """
            entry = jobs[task]

            result = None
            if task in done:
                try:
                    result = task.result()
                except Exception:
                    self.logger.warning('Task %r failed', exc_info=True)

            if result is None:
                return None

            return {
                'service': entry['service'],
                'info': {
                    'state': 'RUNNING' if result.running else 'STOPPED',
                    'pids': result.pids
                }
            }

        return {srv['service']: srv['info'] for srv in map(result, jobs) if srv is not None}

    @private
    async def service_extend(self, svc: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        return svc | ctx.get(svc['service'], {'state': 'UNKNOWN', 'pids': []})  # type: ignore[no-any-return]

    @overload  # type: ignore[override]
    async def query(  # type: ignore[overload-overlap]
        self, filters: QueryFilters, options: QueryOptionsCount,
    ) -> int: ...

    @overload
    async def query(  # type: ignore[overload-overlap]
        self, filters: QueryFilters, options: QueryOptionsGet,
    ) -> ServiceEntry: ...

    @overload
    async def query(
        self, filters: QueryFilters, options: QueryOptions = QueryOptions(),
    ) -> list[ServiceEntry]: ...

    @filterable_api_method(item=ServiceEntry, check_annotations=True)
    async def query(self, filters: QueryFilters, options: QueryOptions = QueryOptions()) -> (
        list[ServiceEntry] | ServiceEntry | int
    ):
        """
        Query all system services with ``query-filters`` and ``query-options``.

        The following ``query-options.extra`` options are supported:

        ``include_state`` *(bool)*:
            Include the running state of each service (``true`` by default). Set to ``false`` as a performance
            optimization when service state is not needed.
        """
        default_options = {
            'prefix': self._config.datastore_prefix,
            'extend': self._config.datastore_extend,
            'extend_context': self._config.datastore_extend_context
        }

        if set(filter_getattrs(filters)) & {'state', 'pids'}:
            services = [
                ServiceEntry(**row)
                for row in await self.middleware.call('datastore.query', 'services.services', [], default_options)
            ]
            return filter_list(services, filters, options, model=ServiceEntry)

        return self._handle_generic_query_result(
            await self.middleware.call(
                'datastore.query', 'services.services', filters, options.model_dump() | default_options,
            ),
            options.count,
            options.get,
        )

    @api_method(
        ServiceUpdateArgs,
        ServiceUpdateResult,
        roles=['SERVICE_WRITE', 'SHARING_NFS_WRITE', 'SHARING_SMB_WRITE', 'SHARING_ISCSI_WRITE',
               'SHARING_FTP_WRITE', 'SHARING_NVME_TARGET_WRITE'],
        audit='Update service configuration',
        audit_callback=True,
        pass_app=True,
        check_annotations=True,
    )
    async def do_update(
        self,
        app: App,
        audit_callback: AuditCallback,
        id_or_name: int | str,
        data: ServiceUpdate,
    ) -> int:
        """
        Update service entry of ``id_or_name``.
        """
        if isinstance(id_or_name, int) or id_or_name.isdigit():
            filters = [['id', '=', int(id_or_name)]]
        else:
            filters = [['service', '=', id_or_name]]

        if not (svc := await self.middleware.call('datastore.query', 'services.services', filters, {'prefix': 'srv_'})):
            raise CallError(f'Service {id_or_name} not found.', errno.ENOENT)

        svc = svc[0]
        audit_callback(svc['service'])
        if not app_has_write_privilege_for_service(app, svc['service']):
            raise CallError(f'{svc["service"]}: authenticated session lacks privilege to update service', errno.EPERM)

        rv = await self.middleware.call(
            'datastore.update', 'services.services', svc['id'], {'srv_enable': data.enable}
        )
        await self.middleware.call('etc.generate', 'rc')
        await self.call2(self.s.service.notify_running, svc['service'])
        return rv  # type: ignore[no-any-return]

    @api_method(
        ServiceControlArgs,
        ServiceControlResult,
        roles=['SERVICE_WRITE', 'SHARING_NFS_WRITE', 'SHARING_SMB_WRITE', 'SHARING_ISCSI_WRITE',
               'SHARING_FTP_WRITE', 'SHARING_NVME_TARGET_WRITE'],
        pass_app=True,
        audit='Service Control:',
        audit_extended=lambda verb, service: f'{verb} {service}',
        check_annotations=True,
    )
    @job(lock=lambda args: f'service_{args[1]}')
    async def control(
        self,
        app: App,
        job: Job,
        verb: Literal['START', 'STOP', 'RESTART', 'RELOAD'],
        service: str,
        options: ServiceOptions = ServiceOptions(),
    ) -> bool:
        """
        Perform the control operation given by ``verb`` (``START``, ``STOP``, ``RESTART``, or ``RELOAD``) on the
        system service named ``service``. This is the general entry point for managing the running state of a
        service; the configured enable-on-boot setting is changed separately via :method:`service.update`.

        The result reflects whether the service is running after a ``START``, ``RESTART``, or ``RELOAD``, or
        whether it was successfully stopped for a ``STOP``. By default failures are reported by returning
        ``false`` rather than raising; set ``options.silent`` to ``false`` to receive an error instead.
        """
        # Check permissions before calling the private method
        if not app_has_write_privilege_for_service(app, service):
            raise CallError(f'{service}: authenticated session lacks privilege to {verb.lower()} service', errno.EPERM)
        return await getattr(self, verb.lower())(service, options)  # type: ignore[no-any-return]

    @private
    async def start(self, service: str, options: ServiceOptions) -> bool:
        """
        Start the service specified by `service`.
        """
        service_object = await self.object(service)

        try:
            async with asyncio.timeout(options.timeout):
                await self.middleware.call_hook('service.pre_action', service, 'start', options)

                await self.call2(self.s.service.generate_etc, service_object)

                try:
                    await service_object.check_configuration()
                except CallError:
                    if options.silent:
                        self.logger.warning('%s: service failed configuration check',
                                            service_object.name, exc_info=True)
                        return False

                    raise

                await service_object.before_start()
                try:
                    await service_object.start()
                except ServiceActionError as e:
                    self.logger.warning('%s: %s', service, e)
                ok, failed_units = await self._check_service_health(
                    service, service_object, "start",
                )
                if ok:
                    await service_object.after_start()
                    await self.call2(self.s.service.notify_running, service)
                    if service_object.deprecated:
                        await self.call2(
                            self.s.alert.oneshot_create,
                            DeprecatedServiceAlert(service=service_object.name),
                        )
                    return True

                await self.call2(self.s.service.notify_running, service)
                if options.silent:
                    return False

                raise CallError(
                    await service_object.failure_logs(failed_units=failed_units)
                    or 'Service not running after start'
                )
        except asyncio.TimeoutError:
            if options.silent:
                return False

            raise CallError('Timed out while starting the service', errno.ETIMEDOUT)

    @api_method(ServiceStartedArgs, ServiceStartedResult, roles=['SERVICE_READ'], check_annotations=True)
    async def started(self, service: str) -> bool:
        """
        Test if service specified by ``service`` has been started.
        """
        service_object = await self.object(service)

        state = await service_object.get_state()

        if service_object.deprecated:
            if state.running:
                await self.call2(self.s.alert.oneshot_create, DeprecatedServiceAlert(service=service_object.name))
            else:
                await self.call2(self.s.alert.oneshot_delete, 'DeprecatedService', service_object.name)

        return state.running

    @api_method(ServiceStartedOrEnabledArgs, ServiceStartedOrEnabledResult, roles=['SERVICE_READ'],
                check_annotations=True)
    async def started_or_enabled(self, service: str) -> bool:
        """
        Test if service specified by ``service`` is started or enabled to start automatically.
        """
        svc = await self.query([['service', '=', service]], QueryOptions(get=True))
        return svc.state == 'RUNNING' or svc.enable

    @private
    async def stop(self, service: str, options: ServiceOptions) -> bool:
        """
        Stop the service specified by `service`.
        """
        service_object = await self.object(service)

        try:
            async with asyncio.timeout(options.timeout):
                await self.middleware.call_hook('service.pre_action', service, 'stop', options)

                try:
                    await service_object.before_stop()
                except Exception:
                    self.logger.error("Failed before stop action for %r service", service)
                await service_object.stop()
                state = await service_object.get_state()
                if not state.running:
                    await service_object.after_stop()
                    await self.call2(self.s.service.notify_running, service)
                    if service_object.deprecated:
                        await self.call2(self.s.alert.oneshot_delete, 'DeprecatedService', service_object.name)

                    return True

                self.logger.error("Service %r running after stop", service)
                await self.call2(self.s.service.notify_running, service)
                if options.silent:
                    return False
                raise CallError(await service_object.failure_logs() or 'Service still running after stop')
        except asyncio.TimeoutError:
            if options.silent:
                return False

            raise CallError('Timed out while stopping the service', errno.ETIMEDOUT)

    @private
    async def restart(self, service: str, options: ServiceOptions) -> bool:
        """
        Restart the service specified by `service`.
        """
        service_object = await self.object(service)

        try:
            async with asyncio.timeout(options.timeout):
                await self.middleware.call_hook('service.pre_action', service, 'restart', options)

                await self.call2(self.s.service.generate_etc, service_object)

                return await self._restart(service, service_object)
        except asyncio.TimeoutError:
            if options.silent:
                return False

            raise CallError('Timed out while restarting the service', errno.ETIMEDOUT)

    async def _check_service_health(self, service: str, service_object: ServiceInterface, action: str) -> (
        tuple[bool, dict[str, tuple[str, int]]]
    ):
        """Check service state and sub-unit health after a start/restart/reload.

        Returns (ok, failed_units) where ok is True if the service is running
        with no failed dependencies.
        """
        state = await service_object.get_state()
        failed_units = await service_object.get_failed_sub_units()
        if state.running and not failed_units:
            return True, failed_units

        if failed_units:
            self.logger.error(
                "Service %r has failed dependencies after %s: %s",
                service,
                action,
                ", ".join(failed_units),
            )
        else:
            self.logger.error("Service %r not running after %s", service, action)
        return False, failed_units

    async def _restart(self, service: str, service_object: ServiceInterface) -> bool:
        if service_object.restartable:
            await service_object.before_restart()
            try:
                await service_object.restart()
            except ServiceActionError as e:
                self.logger.warning('%s: %s', service, e)
            await service_object.after_restart()

            ok, failed_units = await self._check_service_health(
                service, service_object, "restart",
            )
            if not ok:
                await self.call2(self.s.service.notify_running, service)
                return False

        else:
            try:
                await service_object.before_stop()
            except Exception:
                self.logger.error("Failed before stop action for %r service", service)
            await service_object.stop()
            state = await service_object.get_state()
            if not state.running:
                await service_object.after_stop()
            else:
                self.logger.error("Service %r running after restart-caused stop", service)

            await service_object.before_start()
            try:
                await service_object.start()
            except ServiceActionError as e:
                self.logger.warning('%s: %s', service, e)
            ok, failed_units = await self._check_service_health(
                service, service_object, "restart",
            )
            if not ok:
                await self.call2(self.s.service.notify_running, service)
                return False

            await service_object.after_start()

        await self.call2(self.s.service.notify_running, service)
        if service_object.deprecated:
            await self.call2(self.s.alert.oneshot_create, DeprecatedServiceAlert(service=service_object.name))

        return True

    @private
    async def reload(self, service: str, options: ServiceOptions) -> bool:
        """
        Reload the service specified by `service`.
        """
        service_object = await self.object(service)

        try:
            async with asyncio.timeout(options.timeout):
                await self.middleware.call_hook('service.pre_action', service, 'reload', options)

                await self.call2(self.s.service.generate_etc, service_object)

                # Check if service is running before attempting reload
                state = await service_object.get_state()
                if not state.running:
                    # Service is not running, nothing to reload
                    # Config was regenerated above, so just return
                    return False

                if service_object.reloadable:
                    await service_object.before_reload()
                    try:
                        await service_object.reload()
                    except ServiceActionError as e:
                        self.logger.warning('%s: %s', service, e)
                    await service_object.after_reload()

                    ok, failed_units = await self._check_service_health(
                        service, service_object, "reload",
                    )
                    return ok
                else:
                    return await self._restart(service, service_object)
        except asyncio.TimeoutError:
            if options.silent:
                return False

            raise CallError('Timed out while reloading the service', errno.ETIMEDOUT)

    SERVICES: dict[str, ServiceInterface] = {}

    @private
    async def register_object(self, object_: ServiceInterface) -> None:
        if object_.name in self.SERVICES:
            raise CallError(f"Service object {object_.name} is already registered")

        self.SERVICES[object_.name] = object_

    @private
    async def object(self, name: str) -> ServiceInterface:
        try:
            return self.SERVICES[name]
        except KeyError:
            raise MatchNotFound(name) from None

    @private
    async def get_state(self, name: str) -> ServiceState:
        return await (await self.object(name)).get_state()

    @private
    async def generate_etc(self, object_: ServiceInterface) -> None:
        for etc in await object_.select_etc():
            await self.middleware.call("etc.generate", etc)

    @private
    async def notify_running(self, service: str) -> None:
        try:
            svc = await self.call2(self.s.service.query, [('service', '=', service)], QueryOptions(get=True))
        except MatchNotFound:
            return

        self.middleware.send_event('service.query', 'CHANGED', fields=svc)

    @private
    async def identify_process(self, procname: str) -> str | None:
        for service_name, service in self.SERVICES.items():
            if isinstance(service, IdentifiableServiceInterface):
                if await service.identify(procname):
                    return service_name

        return None

    @private
    async def get_unit_state(self, service: str) -> str | None:
        service_object = await self.object(service)
        return await service_object.get_unit_state()

    @private
    async def become_active(self, service: str) -> None:
        """During a HA failover event certain services may support this method being called
        when the node is becoming the new ACTIVE node"""
        service_object = await self.object(service)
        await service_object.become_active()

    @private
    async def become_standby(self, service: str) -> None:
        """During a HA failover event certain services may support this method being called
        when the node is becoming the new STANDBY node"""
        service_object = await self.object(service)
        await service_object.become_standby()

    @private
    def terminate_process(self, pid: int, timeout: int = 10) -> bool:
        """
        Terminate the process with the given `pid`.

        Send SIGTERM, wait up to `timeout` seconds for the process to terminate.
        If the process is still running after the timeout, send SIGKILL.

        Returns:
            boolean: True if process was terminated with SIGTERM, false if SIGKILL was used
        """
        if pid <= 0 or pid == os.getpid():
            raise ValidationError('terminate_process.pid', 'Invalid PID')
        try:
            return terminate_pid(pid, timeout)
        except ProcessLookupError:
            raise ValidationError(
                'terminate_process.pid',
                f'No such process with PID: {pid}',
                errno.ENOENT,
            )

    @periodic(3600, run_on_start=False)
    @private
    async def check_deprecated_services(self) -> None:
        """
        Simple call to service.started is sufficient to toggle alert
        """
        for service_name, service in self.SERVICES.items():
            if not service.deprecated:
                continue

            await self.started(service.name)

    @private
    async def systemd_units(self, name: str) -> list[str]:
        service = await self.object(name)
        if hasattr(service, 'systemd_unit'):
            return [service.systemd_unit] + await service.systemd_extra_units()
        return []


async def __event_service_ready(middleware: Middleware, event_type: Any, args: Any) -> None:
    middleware.create_task(middleware.call2(middleware.services.service.check_deprecated_services))


async def setup(middleware: Middleware) -> None:
    for klass in all_services:
        await middleware.call2(middleware.services.service.register_object, klass(middleware))

    middleware.event_subscribe('system.ready', __event_service_ready)
