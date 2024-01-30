import asyncio
import errno

import psutil

from middlewared.plugins.service_.services.all import all_services
from middlewared.plugins.service_.services.base import IdentifiableServiceInterface
from middlewared.plugins.service_.utils import app_has_write_privilege_for_service

from middlewared.schema import accepts, Bool, Dict, Int, List, Ref, returns, Str
from middlewared.service import filterable, CallError, CRUDService, pass_app, periodic, private
from middlewared.service_exception import MatchNotFound
import middlewared.sqlalchemy as sa
from middlewared.utils import filter_list, filter_getattrs


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

    ENTRY = Dict(
        'service_entry',
        Int('id'),
        Str('service'),
        Bool('enable'),
        Str('state'),
        List('pids', items=[Int('pid')]),
    )

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

    @filterable
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

    @accepts(
        Str('id_or_name'),
        Dict(
            'service-update',
            Bool('enable', default=False),
        ),
        roles=['SERVICE_WRITE', 'SHARING_NFS_WRITE', 'SHARING_SMB_WRITE', 'SHARING_ISCSI_WRITE']
    )
    @returns(Int('service_primary_key'))
    @pass_app(rest=True)
    async def do_update(self, app, id_or_name, data):
        """
        Update service entry of `id_or_name`.

        Currently, it only accepts `enable` option which means whether the service should start on boot.

        """
        if not id_or_name.isdigit():
            filters = [['service', '=', id_or_name]]
        else:
            filters = [['id', '=', id_or_name]]

        if not (svc := await self.middleware.call('datastore.query', 'services.services', filters, {'prefix': 'srv_'})):
            raise CallError(f'Service {id_or_name} not found.', errno.ENOENT)

        svc = svc[0]
        if not app_has_write_privilege_for_service(app, svc['service']):
            raise CallError(f'{svc["service"]}: authenticated session lacks privilege to update service', errno.EPERM)

        rv = await self.middleware.call(
            'datastore.update', 'services.services', svc['id'], {'srv_enable': data['enable']}
        )
        await self.middleware.call('etc.generate', 'rc')
        return rv

    @accepts(
        Str('service'),
        Dict(
            'service-control',
            Bool('ha_propagate', default=True),
            Bool('silent', default=True),
            register=True,
        ),
        roles=['SERVICE_WRITE', 'SHARING_NFS_WRITE', 'SHARING_SMB_WRITE', 'SHARING_ISCSI_WRITE']
    )
    @returns(Bool('started_service'))
    @pass_app(rest=True)
    async def start(self, app, service, options):
        """
        Start the service specified by `service`.

        If `silent` is `true` then in case of service startup failure, `false` will be returned. If `silent` is `false`
        then in case of service startup failure, an exception will be raised.
        """
        service_object = await self.middleware.call('service.object', service)

        if not app_has_write_privilege_for_service(app, service):
            raise CallError(f'{service}: authenticated session lacks privilege to start service', errno.EPERM)

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
        else:
            self.logger.error("Service %r not running after start", service)
            await self.middleware.call('service.notify_running', service)
            if options['silent']:
                return False
            else:
                raise CallError(await service_object.failure_logs() or 'Service not running after start')

    @accepts(Str('service'), roles=['SERVICE_READ'])
    @returns(Bool('service_started', description='Will return `true` if service is running'))
    async def started(self, service):
        """
        Test if service specified by `service` has been started.
        """
        service_object = await self.middleware.call('service.object', service)

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

    @accepts(Str('service'), roles=['SERVICE_READ'])
    @returns(Bool('service_started_or_enabled',
                  description='Will return `true` if service is started or enabled to start automatically.'))
    async def started_or_enabled(self, service):
        """
        Test if service specified by `service` is started or enabled to start automatically.
        """
        svc = await self.middleware.call('service.query', [['service', '=', service]], {'get': True})
        return svc['state'] == 'RUNNING' or svc['enable']

    @accepts(
        Str('service'),
        Ref('service-control'),
        roles=['SERVICE_WRITE', 'SHARING_NFS_WRITE', 'SHARING_SMB_WRITE', 'SHARING_ISCSI_WRITE']
    )
    @returns(Bool('service_stopped', description='Will return `true` if service successfully stopped'))
    @pass_app(rest=True)
    async def stop(self, app, service, options):
        """
        Stop the service specified by `service`.
        """
        service_object = await self.middleware.call('service.object', service)

        if not app_has_write_privilege_for_service(app, service):
            raise CallError(f'{service}: authenticated session lacks privilege to stop service')

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

            return False
        else:
            self.logger.error("Service %r running after stop", service)
            await self.middleware.call('service.notify_running', service)
            return True

    @accepts(
        Str('service'),
        Ref('service-control'),
        roles=['SERVICE_WRITE', 'SHARING_NFS_WRITE', 'SHARING_SMB_WRITE', 'SHARING_ISCSI_WRITE']
    )
    @returns(Bool('service_restarted'))
    @pass_app(rest=True)
    async def restart(self, app, service, options):
        """
        Restart the service specified by `service`.
        """
        service_object = await self.middleware.call('service.object', service)

        if not app_has_write_privilege_for_service(app, service):
            raise CallError(f'{service}: authenticated session lacks privilege to restart service', errno.EPERM)

        await self.middleware.call_hook('service.pre_action', service, 'restart', options)

        await self.middleware.call('service.generate_etc', service_object)

        return await self._restart(service, service_object)

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

    @accepts(
        Str('service'),
        Ref('service-control'),
        roles=['SERVICE_WRITE', 'SHARING_NFS_WRITE', 'SHARING_SMB_WRITE', 'SHARING_ISCSI_WRITE']
    )
    @returns(Bool('service_reloaded'))
    @pass_app(rest=True)
    async def reload(self, app, service, options):
        """
        Reload the service specified by `service`.
        """
        service_object = await self.middleware.call('service.object', service)

        if not app_has_write_privilege_for_service(app, service):
            raise CallError(f'{service}: authenticated session lacks privilege to restart service', errno.EPERM)

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

    SERVICES = {}

    @private
    async def register_object(self, object_):
        if object_.name in self.SERVICES:
            raise CallError(f"Service object {object_.name} is already registered")

        self.SERVICES[object_.name] = object_

    @private
    async def object(self, name):
        try:
            return self.SERVICES[name]
        except KeyError:
            raise MatchNotFound(name) from None

    @private
    async def generate_etc(self, object_):
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

    @accepts(Int("pid"), Int("timeout", default=10))
    @returns(Bool(
        "process_terminated_nicely",
        description="`true` is process has been successfully terminated with `TERM` and `false` if we had to use `KILL`"
    ))
    def terminate_process(self, pid, timeout):
        """
        Terminate process by `pid`.

        First send `TERM` signal, then, if was not terminated in `timeout` seconds, send `KILL` signal.
        """
        try:
            process = psutil.Process(pid)
            process.terminate()
            gone, alive = psutil.wait_procs([process], timeout)
        except psutil.NoSuchProcess:
            raise CallError("Process does not exist")

        if not alive:
            return True

        try:
            alive[0].kill()
        except psutil.NoSuchProcess:
            return True

        return False

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
