import asyncio
import errno
import os
from typing import TYPE_CHECKING

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (
    ServiceEntry, ServiceReloadArgs, ServiceReloadResult, ServiceRestartArgs, ServiceRestartResult, ServiceStartArgs,
    ServiceStartResult, ServiceStartedArgs, ServiceStartedResult, ServiceStartedOrEnabledArgs,
    ServiceStartedOrEnabledResult, ServiceStopArgs, ServiceStopResult, ServiceUpdateArgs, ServiceUpdateResult,
    ServiceControlArgs, ServiceControlResult,
)
from middlewared.plugins.service_.services.all import all_services
from middlewared.plugins.service_.services.base import IdentifiableServiceInterface
from middlewared.plugins.service_.utils import app_has_write_privilege_for_service
from middlewared.service import filterable_api_method, CallError, CRUDService, job, periodic, private
from middlewared.service_exception import MatchNotFound, ValidationError
from middlewared.utils import filter_list, filter_getattrs
from middlewared.utils.os import terminate_pid

if TYPE_CHECKING:
    from middlewared.plugins.service_.services.base_interface import ServiceInterface


class ServiceModel(sa.Model):
    __tablename__ = 'services_services'

    id = sa.Column(sa.Integer(), primary_key=True)
    srv_service = sa.Column(sa.String(120))
    srv_enable = sa.Column(sa.Boolean(), default=False)


class ServiceService(CRUDService):

    class Config:
        cli_namespace = "service"
        datastore_prefix = 'srv_'
        datastore_extend = 'service.service_extend'
        datastore_extend_context = 'service.service_extend_context'
        role_prefix = "SERVICE"
        entry = ServiceEntry

    @private
    async def service_extend_context(self, services, extra):
        if not extra.get('include_state', True):
            return {}

        if not isinstance(services, list):
            services = [services]

        jobs = {
            asyncio.ensure_future(
                (await self.middleware.call('service.object', service['service'])).get_state()
            ): service
            for service in services
        }

        if jobs:
            done, pending = await asyncio.wait(list(jobs.keys()), timeout=15)

        def result(task):
            """
            Method to handle results of the coroutines.
            In case of error or timeout, provide UNKNOWN state.
            """
            entry = jobs.get(task)

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
    async def service_extend(self, svc, ctx):
        return svc | ctx.get(svc['service'], {'state': 'UNKNOWN', 'pids': []})

    @filterable_api_method(item=ServiceEntry)
    async def query(self, filters, options):
        """
        Query all system services with `query-filters` and `query-options`.

        Supports the following extra options:
        `include_state` - performance optimization to avoid getting service state.
        defaults to True.
        """
        default_options = {
            'prefix': self._config.datastore_prefix,
            'extend': self._config.datastore_extend,
            'extend_context': self._config.datastore_extend_context
        }

        if set(filter_getattrs(filters)) & {'state', 'pids'}:
            services = await self.middleware.call('datastore.query', 'services.services', [], default_options)
            return filter_list(services, filters, options)

        return await self.middleware.call('datastore.query', 'services.services', filters, options | default_options)

    @api_method(
        ServiceUpdateArgs,
        ServiceUpdateResult,
        roles=['SERVICE_WRITE', 'SHARING_NFS_WRITE', 'SHARING_SMB_WRITE', 'SHARING_ISCSI_WRITE', 'SHARING_FTP_WRITE'],
        audit='Update service configuration',
        audit_callback=True,
        pass_app=True,
        pass_app_rest=True,
    )
    async def do_update(self, app, audit_callback, id_or_name, data):
        """
        Update service entry of `id_or_name`.
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
            'datastore.update', 'services.services', svc['id'], {'srv_enable': data['enable']}
        )
        await self.middleware.call('etc.generate', 'rc')
        return rv

    @api_method(
        ServiceControlArgs,
        ServiceControlResult,
        roles=['SERVICE_WRITE', 'SHARING_NFS_WRITE', 'SHARING_SMB_WRITE', 'SHARING_ISCSI_WRITE', 'SHARING_FTP_WRITE'],
        pass_app=True,
        pass_app_rest=True,
        audit='Service Control:',
        audit_extended=lambda verb, service: f'{verb} {service}',
    )
    @job(lock=lambda args: f'service_{args[1]}')
    async def control(self, app, job, verb, service, options):
        return await getattr(self, verb.lower())(app, service, options)

    @api_method(
        ServiceStartArgs,
        ServiceStartResult,
        roles=['SERVICE_WRITE', 'SHARING_NFS_WRITE', 'SHARING_SMB_WRITE', 'SHARING_ISCSI_WRITE', 'SHARING_FTP_WRITE'],
        pass_app=True,
        pass_app_rest=True,
        removed_in="v26.04",
        audit='Service: start',
        audit_extended=lambda service: service,
    )
    async def start(self, app, service, options):
        """
        Start the service specified by `service`.
        """
        service_object = await self.middleware.call('service.object', service)

        if not app_has_write_privilege_for_service(app, service):
            raise CallError(f'{service}: authenticated session lacks privilege to start service', errno.EPERM)

        try:
            async with asyncio.timeout(options['timeout']):
                await self.middleware.call_hook('service.pre_action', service, 'start', options)

                await self.middleware.call('service.generate_etc', service_object)

                try:
                    await service_object.check_configuration()
                except CallError:
                    if options['silent']:
                        self.logger.warning('%s: service failed configuration check',
                                            service_object.name, exc_info=True)
                        return False

                    raise

                await service_object.before_start()
                await service_object.start()
                state = await service_object.get_state()
                if state.running:
                    await service_object.after_start()
                    await self.middleware.call('service.notify_running', service)
                    if service_object.deprecated:
                        await self.middleware.call(
                            'alert.oneshot_create',
                            'DeprecatedService',
                            {"service": service_object.name}
                        )
                    return True

                self.logger.error("Service %r not running after start", service)
                await self.middleware.call('service.notify_running', service)
                if options['silent']:
                    return False

                raise CallError(await service_object.failure_logs() or 'Service not running after start')
        except asyncio.TimeoutError:
            if options['silent']:
                return False

            raise CallError('Timed out while starting the service', errno.ETIMEDOUT)

    @api_method(ServiceStartedArgs, ServiceStartedResult, roles=['SERVICE_READ'])
    async def started(self, service):
        """
        Test if service specified by `service` has been started.
        """
        service_object: 'ServiceInterface' = await self.middleware.call('service.object', service)

        state = await service_object.get_state()

        if service_object.deprecated:
            if state.running:
                await self.middleware.call(
                    'alert.oneshot_create',
                    'DeprecatedService',
                    {"service": service_object.name}
                )
            else:
                await self.middleware.call('alert.oneshot_delete', 'DeprecatedService', service_object.name)

        return state.running

    @api_method(ServiceStartedOrEnabledArgs, ServiceStartedOrEnabledResult, roles=['SERVICE_READ'])
    async def started_or_enabled(self, service):
        """
        Test if service specified by `service` is started or enabled to start automatically.
        """
        svc = await self.middleware.call('service.query', [['service', '=', service]], {'get': True})
        return svc['state'] == 'RUNNING' or svc['enable']

    @api_method(
        ServiceStopArgs,
        ServiceStopResult,
        roles=['SERVICE_WRITE', 'SHARING_NFS_WRITE', 'SHARING_SMB_WRITE', 'SHARING_ISCSI_WRITE', 'SHARING_FTP_WRITE'],
        pass_app=True,
        pass_app_rest=True,
        removed_in="v26.04",
        audit='Service: stop',
        audit_extended=lambda service: service,
    )
    async def stop(self, app, service, options):
        """
        Stop the service specified by `service`.
        """
        service_object = await self.middleware.call('service.object', service)

        if not app_has_write_privilege_for_service(app, service):
            raise CallError(f'{service}: authenticated session lacks privilege to stop service')

        try:
            async with asyncio.timeout(options['timeout']):
                await self.middleware.call_hook('service.pre_action', service, 'stop', options)

                try:
                    await service_object.before_stop()
                except Exception:
                    self.logger.error("Failed before stop action for %r service", service)
                await service_object.stop()
                state = await service_object.get_state()
                if not state.running:
                    await service_object.after_stop()
                    await self.middleware.call('service.notify_running', service)
                    if service_object.deprecated:
                        await self.middleware.call('alert.oneshot_delete', 'DeprecatedService', service_object.name)

                    return True

                self.logger.error("Service %r running after stop", service)
                await self.middleware.call('service.notify_running', service)
                if options['silent']:
                    return False
                raise CallError(await service_object.failure_logs() or 'Service still running after stop')
        except asyncio.TimeoutError:
            if options['silent']:
                return False

            raise CallError('Timed out while stopping the service', errno.ETIMEDOUT)

    @api_method(
        ServiceRestartArgs,
        ServiceRestartResult,
        roles=['SERVICE_WRITE', 'SHARING_NFS_WRITE', 'SHARING_SMB_WRITE', 'SHARING_ISCSI_WRITE', 'SHARING_FTP_WRITE'],
        pass_app=True,
        pass_app_rest=True,
        removed_in="v26.04",
        audit='Service: restart',
        audit_extended=lambda service: service,
    )
    async def restart(self, app, service, options):
        """
        Restart the service specified by `service`.
        """
        service_object = await self.middleware.call('service.object', service)

        if not app_has_write_privilege_for_service(app, service):
            raise CallError(f'{service}: authenticated session lacks privilege to restart service', errno.EPERM)

        try:
            async with asyncio.timeout(options['timeout']):
                await self.middleware.call_hook('service.pre_action', service, 'restart', options)

                await self.middleware.call('service.generate_etc', service_object)

                return await self._restart(service, service_object)
        except asyncio.TimeoutError:
            if options['silent']:
                return False

            raise CallError('Timed out while restarting the service', errno.ETIMEDOUT)

    async def _restart(self, service, service_object):
        if service_object.restartable:
            await service_object.before_restart()
            await service_object.restart()
            await service_object.after_restart()

            state = await service_object.get_state()
            if not state.running:
                await self.middleware.call('service.notify_running', service)
                self.logger.error("Service %r not running after restart", service)
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
            await service_object.start()
            state = await service_object.get_state()
            if not state.running:
                await self.middleware.call('service.notify_running', service)
                self.logger.error("Service %r not running after restart-caused start", service)
                return False

            await service_object.after_start()

        await self.middleware.call('service.notify_running', service)
        if service_object.deprecated:
            await self.middleware.call('alert.oneshot_create', 'DeprecatedService', {"service": service_object.name})

        return True

    @api_method(
        ServiceReloadArgs,
        ServiceReloadResult,
        roles=['SERVICE_WRITE', 'SHARING_NFS_WRITE', 'SHARING_SMB_WRITE', 'SHARING_ISCSI_WRITE', 'SHARING_FTP_WRITE'],
        pass_app=True,
        pass_app_rest=True,
        removed_in="v26.04",
        audit='Service: reload',
        audit_extended=lambda service: service,
    )
    async def reload(self, app, service, options):
        """
        Reload the service specified by `service`.
        """
        service_object = await self.middleware.call('service.object', service)

        if not app_has_write_privilege_for_service(app, service):
            raise CallError(f'{service}: authenticated session lacks privilege to restart service', errno.EPERM)

        try:
            async with asyncio.timeout(options['timeout']):
                await self.middleware.call_hook('service.pre_action', service, 'reload', options)

                await self.middleware.call('service.generate_etc', service_object)

                if service_object.reloadable:
                    await service_object.before_reload()
                    await service_object.reload()
                    await service_object.after_reload()

                    state = await service_object.get_state()
                    if state.running:
                        return True
                    else:
                        self.logger.error("Service %r not running after reload", service)
                        return False
                else:
                    return await self._restart(service, service_object)
        except asyncio.TimeoutError:
            if options['silent']:
                return False

            raise CallError('Timed out while reloading the service', errno.ETIMEDOUT)

    SERVICES: dict[str, 'ServiceInterface'] = {}

    @private
    async def register_object(self, object_: 'ServiceInterface'):
        if object_.name in self.SERVICES:
            raise CallError(f"Service object {object_.name} is already registered")

        self.SERVICES[object_.name] = object_

    @private
    async def object(self, name: str) -> 'ServiceInterface':
        try:
            return self.SERVICES[name]
        except KeyError:
            raise MatchNotFound(name) from None

    @private
    async def generate_etc(self, object_: 'ServiceInterface'):
        for etc in object_.etc:
            await self.middleware.call("etc.generate", etc)

    @private
    async def notify_running(self, service):
        try:
            svc = await self.middleware.call('service.query', [('service', '=', service)], {'get': True})
        except MatchNotFound:
            return

        self.middleware.send_event('service.query', 'CHANGED', fields=svc)

    @private
    async def identify_process(self, procname):
        for service_name, service in self.SERVICES.items():
            if isinstance(service, IdentifiableServiceInterface):
                if await service.identify(procname):
                    return service_name

    @private
    async def get_unit_state(self, service):
        service_object = await self.middleware.call('service.object', service)
        return await service_object.get_unit_state()

    @private
    async def become_active(self, service):
        """During a HA failover event certain services may support this method being called
        when the node is becoming the new ACTIVE node"""
        service_object = await self.middleware.call('service.object', service)
        return await service_object.become_active()

    @private
    async def become_standby(self, service):
        """During a HA failover event certain services may support this method being called
        when the node is becoming the new STANDBY node"""
        service_object = await self.middleware.call('service.object', service)
        return await service_object.become_standby()

    @private
    def terminate_process(self, pid, timeout=10):
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
            raise ValidationError('terminate_process.pid', f'No such process with PID: {pid}')

    @periodic(3600, run_on_start=False)
    @private
    async def check_deprecated_services(self):
        """
        Simple call to service.started is sufficient to toggle alert
        """
        for service_name, service in self.SERVICES.items():
            if not service.deprecated:
                continue

            await self.started(service.name)


async def __event_service_ready(middleware, event_type, args):
    middleware.create_task(middleware.call('service.check_deprecated_services'))


async def setup(middleware):
    for klass in all_services:
        await middleware.call('service.register_object', klass(middleware))

    middleware.event_subscribe('system.ready', __event_service_ready)
