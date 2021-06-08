import asyncio
import errno

import psutil

from middlewared.plugins.service_.services.all import all_services
from middlewared.plugins.service_.services.base import IdentifiableServiceInterface

from middlewared.schema import accepts, Bool, Dict, Int, List, Ref, returns, Str
from middlewared.service import filterable, CallError, CRUDService, private
from middlewared.service_exception import MatchNotFound
import middlewared.sqlalchemy as sa
from middlewared.utils import filter_list


class ServiceModel(sa.Model):
    __tablename__ = 'services_services'

    id = sa.Column(sa.Integer(), primary_key=True)
    srv_service = sa.Column(sa.String(120))
    srv_enable = sa.Column(sa.Boolean(), default=False)


class ServiceService(CRUDService):

    class Config:
        cli_namespace = "service"

    ENTRY = Dict(
        'service_entry',
        Int('id'),
        Str('service'),
        Bool('enable'),
        Str('state'),
        List('pids', items=[Int('pid')]),
    )

    @filterable
    async def query(self, filters, options):
        """
        Query all system services with `query-filters` and `query-options`.
        """
        if options is None:
            options = {}
        options['prefix'] = 'srv_'

        services = await self.middleware.call('datastore.query', 'services.services', filters, options)

        # In case a single service has been requested
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
                entry['state'] = 'UNKNOWN'
                entry['pids'] = []
            else:
                entry['state'] = 'RUNNING' if result.running else 'STOPPED'
                entry['pids'] = result.pids

            return entry

        services = list(map(result, jobs))
        return filter_list(services, filters, options)

    @accepts(
        Str('id_or_name'),
        Dict(
            'service-update',
            Bool('enable', default=False),
        ),
    )
    @returns(Int('service_primary_key'))
    async def do_update(self, id_or_name, data):
        """
        Update service entry of `id_or_name`.

        Currently it only accepts `enable` option which means whether the
        service should start on boot.

        """
        if not id_or_name.isdigit():
            svc = await self.middleware.call('datastore.query', 'services.services', [('srv_service', '=', id_or_name)])
            if not svc:
                raise CallError(f'Service {id_or_name} not found.', errno.ENOENT)
            id_or_name = svc[0]['id']

        rv = await self.middleware.call(
            'datastore.update', 'services.services', id_or_name, {'srv_enable': data['enable']}
        )
        await self.middleware.call('etc.generate', 'rc')
        return rv

    @accepts(
        Str('service'),
        Dict(
            'service-control',
            Bool('ha_propagate', default=True),
            register=True,
        ),
    )
    @returns(Bool('started_service'))
    async def start(self, service, options):
        """
        Start the service specified by `service`.
        """
        service_object = await self.middleware.call('service.object', service)

        await self.middleware.call_hook('service.pre_action', service, 'start', options)

        await self.middleware.call('service.generate_etc', service_object)

        await service_object.before_start()
        await service_object.start()
        state = await service_object.get_state()
        if state.running:
            await service_object.after_start()
            await self.middleware.call('service.notify_running', service)
            return True
        else:
            self.logger.error("Service %r not running after start", service)
            await self.middleware.call('service.notify_running', service)
            return False

    @accepts(Str('service'))
    @returns(Bool('service_started', description='Will return `true` if service is running'))
    async def started(self, service):
        """
        Test if service specified by `service` has been started.
        """
        service_object = await self.middleware.call('service.object', service)

        state = await service_object.get_state()
        return state.running

    @accepts(
        Str('service'),
        Ref('service-control'),
    )
    @returns(Bool('service_stopped', description='Will return `true` if service successfully stopped'))
    async def stop(self, service, options):
        """
        Stop the service specified by `service`.
        """
        service_object = await self.middleware.call('service.object', service)

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
            return False
        else:
            self.logger.error("Service %r running after stop", service)
            await self.middleware.call('service.notify_running', service)
            return True

    @accepts(
        Str('service'),
        Ref('service-control'),
    )
    @returns(Bool('service_restarted'))
    async def restart(self, service, options):
        """
        Restart the service specified by `service`.
        """
        service_object = await self.middleware.call('service.object', service)

        await self.middleware.call_hook('service.pre_action', service, 'restart', options)

        await self.middleware.call('service.generate_etc', service_object)

        return await self._restart(service, service_object)

    async def _restart(self, service, service_object):
        if service_object.restartable:
            await service_object.before_restart()
            await service_object.restart()
            await service_object.after_restart()

            state = await service_object.get_state()
            if state.running:
                await self.middleware.call('service.notify_running', service)
                return True
            else:
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
            if state.running:
                await service_object.after_start()
                await self.middleware.call('service.notify_running', service)
                return True
            else:
                await self.middleware.call('service.notify_running', service)
                self.logger.error("Service %r not running after restart-caused start", service)
                return False

    @accepts(
        Str('service'),
        Ref('service-control'),
    )
    @returns(Bool('service_reloaded'))
    async def reload(self, service, options):
        """
        Reload the service specified by `service`.
        """
        service_object = await self.middleware.call('service.object', service)

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
    async def register_object(self, object):
        if object.name in self.SERVICES:
            raise CallError(f"Service object {object.name} is already registered")

        self.SERVICES[object.name] = object

    @private
    async def object(self, name):
        return self.SERVICES[name]

    @private
    async def generate_etc(self, object):
        for etc in object.etc:
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

    @accepts(Int("pid"), Int("timeout", default=10))
    @returns(Bool('process_terminated'))
    def terminate_process(self, pid, timeout):
        """
        Terminate process by `pid`.

        First send `TERM` signal, then, if was not terminated in `timeout` seconds, send `KILL` signal.

        Returns `true` is process has been successfully terminated with `TERM` and `false` if we had to use `KILL`.
        """
        try:
            process = psutil.Process(pid)
        except psutil.NoSuchProcess:
            raise CallError("Process does not exist")

        process.terminate()

        gone, alive = psutil.wait_procs([process], timeout)
        if not alive:
            return True

        alive[0].kill()
        return False


async def setup(middleware):
    for klass in all_services:
        await middleware.call('service.register_object', klass(middleware))
