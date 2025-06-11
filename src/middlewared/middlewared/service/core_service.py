import asyncio
from collections import defaultdict
import errno
import inspect
import ipaddress
import os
import re
import socket
from subprocess import run
import threading
import time
import traceback
import uuid

from remote_pdb import RemotePdb

import middlewared.main

from middlewared.api import api_method
from middlewared.api.base.jsonschema import get_json_schema
from middlewared.api.current import (
    CoreGetServicesArgs, CoreGetServicesResult,
    CoreGetMethodsArgs, CoreGetMethodsResult,
    CoreGetJobsItem,
    CoreResizeShellArgs, CoreResizeShellResult,
    CoreJobDownloadLogsArgs, CoreJobDownloadLogsResult,
    CoreJobWaitArgs, CoreJobWaitResult,
    CoreJobAbortArgs, CoreJobAbortResult,
    CorePingArgs, CorePingResult,
    CorePingRemoteArgs, CorePingRemoteResult,
    CoreArpArgs, CoreArpResult,
    CoreDownloadArgs, CoreDownloadResult,
    CoreDebugArgs, CoreDebugResult,
    CoreBulkArgs, CoreBulkResult,
    CoreSetOptionsArgs, CoreSetOptionsResult,
    CoreSubscribeArgs, CoreSubscribeResult,
    CoreUnsubscribeArgs, CoreUnsubscribeResult,
    QueryArgs,
)
from middlewared.common.environ import environ_update
from middlewared.job import Job, JobAccess
from middlewared.pipe import Pipes
from middlewared.service_exception import CallError, ValidationErrors, InstanceNotFound
from middlewared.utils import BOOTREADY, filter_list, MIDDLEWARE_STARTED_SENTINEL_PATH
from middlewared.utils.debug import get_frame_details, get_threads_stacks
from middlewared.validators import IpAddress

from .compound_service import CompoundService
from .config_service import ConfigService
from .crud_service import CRUDService
from .decorators import filterable_api_method, job, no_authz_required, private
from .service import Service


def is_service_class(service, klass):
    return (
        isinstance(service, klass) or
        (isinstance(service, CompoundService) and any(isinstance(part, klass) for part in service.parts))
    )


class CoreService(Service):

    class Config:
        cli_private = True

    @api_method(CoreResizeShellArgs, CoreResizeShellResult, authorization_required=False)
    async def resize_shell(self, id_, cols, rows):
        """
        Resize terminal session (/websocket/shell) to cols x rows
        """
        shell = middlewared.main.ShellApplication.shells.get(id_)
        if shell is None:
            raise CallError('Shell does not exist', errno.ENOENT)

        shell.resize(cols, rows)

    @private
    def get_tasks(self):
        for task in asyncio.all_tasks(loop=self.middleware.loop):
            formatted = None
            frame = None
            frames = []
            for frame in task.get_stack():
                cur_frame = get_frame_details(frame, self.logger)
                if cur_frame:
                    frames.append(cur_frame)

            if frame:
                formatted = traceback.format_stack(frame)
            yield {
                'stack': formatted,
                'frames': frames,
            }

    def _job_by_app_and_id(self, app, job_id, access):
        if app is None:
            try:
                return self.middleware.jobs[job_id]
            except KeyError:
                raise InstanceNotFound(f"Job with id {job_id} does not exist")
        else:
            return self.__job_by_credential_and_id(app.authenticated_credentials, job_id, access)

    def __job_by_credential_and_id(self, credential, job_id, access):
        job = self.middleware.jobs.get(job_id)
        if job is None:
            raise InstanceNotFound(f"Job with id {job_id} does not exist")

        if (error := job.credential_access_error(credential, access)) is not None:
            raise CallError(error, errno.EPERM)

        return job

    @filterable_api_method(item=CoreGetJobsItem, authorization_required=False, pass_app=True, pass_app_rest=True)
    def get_jobs(self, app, filters, options):
        """
        Get information about long-running jobs.
        If authenticated session does not have the FULL_ADMIN role, only
        jobs owned by the current authenticated session will be returned.

        `result` key will have sensitive values redacted by default for external
        clients.

        Redaction behavior may be explicitly specfied via the `extra`
        query-option `raw_result`. If `raw_result` is True then unredacted result
        is returned.
        """

        # Get raw result by default for internal calls to core.get_jobs otherwise
        # redact result by default

        raw_result_default = False if app else True

        if app:
            jobs = list(self.middleware.jobs.for_credential(app.authenticated_credentials, JobAccess.READ).values())
        else:
            jobs = list(self.middleware.jobs.all().values())

        raw_result = options['extra'].get('raw_result', raw_result_default)
        jobs = filter_list([
            i.__encode__(raw_result) for i in jobs
        ], filters, options)
        return jobs

    @api_method(CoreJobDownloadLogsArgs, CoreJobDownloadLogsResult, authorization_required=False,
                pass_app=True, pass_app_rest=True)
    async def job_download_logs(self, app, id_, filename, buffered):
        """
        Download logs of the job `id`.

        Please see `core.download` method documentation for explanation on `filename` and `buffered` arguments,
        and return value.
        """
        job = self._job_by_app_and_id(app, id_, JobAccess.READ)

        if job.logs_path is None:
            raise CallError('This job has no logs')

        return (await self._download(app, 'filesystem.get', [job.logs_path], filename, buffered))[1]

    @api_method(CoreJobWaitArgs, CoreJobWaitResult, authorization_required=False)
    @job()
    async def job_wait(self, job, id_):
        target_job = self.__job_by_credential_and_id(job.credentials, id_, JobAccess.READ)

        return await job.wrap(target_job)

    @private
    def job_update(self, id_, data):
        job = self.middleware.jobs[id_]
        progress = data.get('progress')
        if progress:
            job.set_progress(
                progress['percent'],
                description=progress.get('description'),
                extra=progress.get('extra'),
            )

    @private
    def is_starting_during_boot(self):
        # Returns True if middleware is being currently started during boot
        return not os.path.exists(MIDDLEWARE_STARTED_SENTINEL_PATH)

    @private
    def notify_postinit(self):
        self.middleware.call_sync('migration.run')

        # Sentinel file to tell we have gone far enough in the boot process.
        # See #17508
        open(BOOTREADY, 'w').close()

        # Send event to middlewared saying we are late enough in the process to call it ready
        self.middleware.call_sync('core.event_send', 'system.ready', 'ADDED')

        # Let's setup periodic tasks now
        self.middleware._setup_periodic_tasks()

    @api_method(CoreJobAbortArgs, CoreJobAbortResult, authorization_required=False, pass_app=True, pass_app_rest=True)
    def job_abort(self, app, id_):
        job = self._job_by_app_and_id(app, id_, JobAccess.ABORT)
        job.abort()

    def _should_list_service(self, name, service, target):
        if service._config.private is True:
            if not (target == 'REST' and name == 'resttest'):
                return False

        if target == 'CLI' and service._config.cli_private:
            return False

        return True

    @api_method(CoreGetServicesArgs, CoreGetServicesResult, authorization_required=False, pass_app=True)
    def get_services(self, app, target):
        """Returns a list of all registered services."""
        services = {}
        for k, v in list(self.middleware.get_services().items()):
            if not self._should_list_service(k, v, target):
                continue

            if is_service_class(v, CRUDService):
                _typ = 'crud'
            elif is_service_class(v, ConfigService):
                _typ = 'config'
            else:
                _typ = 'service'

            config = {
                k: v for k, v in list(v._config.__dict__.items())
                if not (k in ['entry', 'events', 'event_sources', 'process_pool', 'thread_pool'] or k.startswith('_'))
            }
            if config['cli_description'] is None:
                if v.__doc__:
                    config['cli_description'] = inspect.getdoc(v).split("\n")[0].strip()

            services[k] = {
                'config': config,
                'type': _typ,
            }

        return services

    @api_method(CoreGetMethodsArgs, CoreGetMethodsResult, authorization_required=False, pass_app=True)
    def get_methods(self, app, service, target):
        """
        Return methods metadata of every available service.
        """
        data = {}
        for name, svc in list(self.middleware.get_services().items()):
            if service is not None and name != service:
                continue

            if not self._should_list_service(name, svc, target):
                continue

            for attr in dir(svc):
                if attr.startswith('_'):
                    continue

                method = None
                # For CRUD.do_{update,delete} they need to be accounted
                # as "item_method", since they are just wrapped.
                item_method = None
                if is_service_class(svc, CRUDService):
                    """
                    For CRUD the create/update/delete are special.
                    The real implementation happens in do_create/do_update/do_delete
                    so thats where we actually extract pertinent information.
                    """
                    if attr in ('create', 'update', 'delete'):
                        method = getattr(svc, 'do_{}'.format(attr), None)
                        if method is None:
                            continue
                        if attr in ('update', 'delete'):
                            item_method = True
                    elif attr in ('do_create', 'do_update', 'do_delete'):
                        continue
                elif is_service_class(svc, ConfigService):
                    """
                    For Config the update is special.
                    The real implementation happens in do_update
                    so thats where we actually extract pertinent information.
                    """
                    if attr == 'update':
                        original_name = 'do_{}'.format(attr)
                        if hasattr(svc, original_name):
                            method = getattr(svc, original_name, None)
                        else:
                            method = getattr(svc, attr)
                        if method is None:
                            continue
                    elif attr in ('do_update',):
                        continue

                if method is None:
                    method = getattr(svc, attr, None)

                if method is None or not callable(method):
                    continue

                # Skip private methods
                if hasattr(method, '_private') and method._private is True:
                    continue
                if target == 'CLI' and getattr(method, '_cli_private', False):
                    continue

                # terminate is a private method used to clean up a service on shutdown
                if attr == 'terminate':
                    continue

                method_name = f'{name}.{attr}'
                no_auth_required = hasattr(method, '_no_auth_required')
                no_authz_required = hasattr(method, '_no_authz_required')

                # Skip methods that are not allowed for the currently authenticated credentials
                if app is not None:
                    if not no_auth_required:
                        if not app.authenticated_credentials:
                            continue

                        if not no_authz_required and not app.authenticated_credentials.authorize('CALL', method_name):
                            continue

                examples = defaultdict(list)
                doc = inspect.getdoc(method)
                if doc:
                    """
                    Allow method docstring to have sections in the format of:

                      .. section_name::

                    Currently the following sections are available:

                      .. examples:: - goes into `__all__` list in examples
                      .. examples(cli):: - goes into `cli` list in examples
                      .. examples(rest):: - goes into `rest` list in examples
                      .. examples(websocket):: - goes into `websocket` list in examples
                    """
                    sections = re.split(r'^.. (.+?)::$', doc, flags=re.M)
                    doc = sections[0]
                    for i in range((len(sections) - 1) // 2):
                        idx = (i + 1) * 2 - 1
                        reg = re.search(r'examples(?:\((.+)\))?', sections[idx])
                        if reg is None:
                            continue
                        exname = reg.groups()[0]
                        if exname is None:
                            exname = '__all__'
                        examples[exname].append(sections[idx + 1])

                method_schemas = {
                    'accepts': get_json_schema(method.new_style_accepts),
                    'returns': get_json_schema(method.new_style_returns),
                }

                data[method_name] = {
                    'description': doc,
                    'cli_description': (doc or '').split('\n\n')[0].split('.')[0].replace('\n', ' '),
                    'examples': examples,
                    'item_method': True if item_method else hasattr(method, '_item_method'),
                    'no_auth_required': no_auth_required,
                    'filterable': issubclass(method.new_style_accepts, QueryArgs),
                    'filterable_schema': None,
                    'pass_application': hasattr(method, '_pass_app'),
                    'require_websocket': hasattr(method, '_pass_app') and not method._pass_app['rest'],
                    'job': hasattr(method, '_job'),
                    'downloadable': hasattr(method, '_job') and 'output' in method._job['pipes'],
                    'uploadable': hasattr(method, '_job') and 'input' in method._job['pipes'],
                    'check_pipes': hasattr(method, '_job') and method._job['pipes'] and method._job['check_pipes'],
                    'roles': self.middleware.role_manager.roles_for_method(method_name),
                    **method_schemas,
                }

        return data

    @private
    async def call_hook(self, name, args, kwargs=None):
        kwargs = kwargs or {}
        await self.middleware.call_hook(name, *args, **kwargs)

    @private
    async def event_send(self, name, event_type, kwargs=None):
        kwargs = kwargs or {}
        self.middleware.send_event(name, event_type, **kwargs)

    @api_method(CorePingArgs, CorePingResult, authorization_required=False)
    def ping(self):
        """
        Utility method which just returns "pong".
        Can be used to keep connection/authtoken alive instead of using
        "ping" protocol message.
        """
        return 'pong'

    def _ping_host(self, version, host, timeout, count=None, interface=None, interval=None):
        if version == 4:
            command = ['ping', '-4', '-w', f'{timeout}']
        elif version == 6:
            command = ['ping6', '-w', f'{timeout}']
        if count:
            command.extend(['-c', str(count)])
        if interface:
            command.extend(['-I', interface])
        if interval:
            command.extend(['-i', interval])
        command.append(host)
        return run(command).returncode == 0

    @api_method(CorePingRemoteArgs, CorePingRemoteResult, roles=['FULL_ADMIN'])
    def ping_remote(self, options):
        """
        Method that will send an ICMP echo request to "hostname"
        and will wait up to "timeout" for a reply.
        """
        ip = None
        ip_found = True
        verrors = ValidationErrors()
        try:
            ip = IpAddress()
            ip(options['hostname'])
            ip = options['hostname']
        except ValueError:
            ip_found = False
        if not ip_found:
            try:
                if options['type'] == 'ICMP':
                    ip = socket.getaddrinfo(options['hostname'], None)[0][4][0]
                elif options['type'] == 'ICMPV4':
                    ip = socket.getaddrinfo(options['hostname'], None, socket.AF_INET)[0][4][0]
                elif options['type'] == 'ICMPV6':
                    ip = socket.getaddrinfo(options['hostname'], None, socket.AF_INET6)[0][4][0]
            except socket.gaierror:
                verrors.add(
                    'options.hostname',
                    f'{options["hostname"]} cannot be resolved to an IP address.'
                )

        verrors.check()

        addr = ipaddress.ip_address(ip)
        if not addr.version == 4 and (options['type'] == 'ICMP' or options['type'] == 'ICMPV4'):
            verrors.add(
                'options.type',
                f'Requested ICMPv4 protocol, but the address provided "{addr}" is not a valid IPv4 address.'
            )
        if not addr.version == 6 and options['type'] == 'ICMPV6':
            verrors.add(
                'options.type',
                f'Requested ICMPv6 protocol, but the address provided "{addr}" is not a valid IPv6 address.'
            )
        verrors.check()

        ping_host = False
        if addr.version in [4, 6]:
            ping_host = self._ping_host(addr.version, ip, options['timeout'], options.get('count'), options.get('interface'), options.get('interval'))

        return ping_host

    @api_method(CoreArpArgs, CoreArpResult, roles=['FULL_ADMIN'])
    def arp(self, options):
        arp_command = ['arp', '-n']
        if interface := options.get('interface'):
            arp_command.extend(['-i', interface])
        rv = run(arp_command, capture_output=True)
        search_ip = options.get('ip')
        result = {}
        for line in rv.stdout.decode().strip().splitlines():
            sline = line.split()
            try:
                line_ip = str(ipaddress.ip_address(sline[0]))
            except ValueError:
                continue
            if sline[1] != 'ether':
                continue
            if search_ip:
                if line_ip == search_ip:
                    result[line_ip] = sline[2]
            else:
                result[line_ip] = sline[2]
        return result

    @api_method(CoreDownloadArgs, CoreDownloadResult, authorization_required=False, pass_app=True, pass_app_rest=True)
    async def download(self, app, method, args, filename, buffered):
        """
        Core helper to call a job marked for download.
        """
        if app is not None:
            if not app.authenticated_credentials.authorize('CALL', method):
                raise CallError('Not authorized', errno.EACCES)

        return await self._download(app, method, args, filename, buffered)

    async def _download(self, app, method, args, filename, buffered):
        serviceobj, methodobj = self.middleware.get_method(method)
        job = await self.middleware.call_with_audit(
            method, serviceobj, methodobj, args, app=app,
            pipes=Pipes(output=self.middleware.pipe(buffered))
        )
        token = await self.middleware.call(
            'auth.generate_token',
            300,  # ttl
            {'filename': filename, 'job': job.id},  # attrs
            True,  # match origin
            True,  # single-use token
            app=app
        )
        self.middleware.fileapp.register_job(job.id, buffered)
        return job.id, f'/_download/{job.id}?auth_token={token}'

    @private
    @no_authz_required
    @job()
    def job_test(self, job, data=None):
        """
        Private no-op method to test a job, simply returning `true`.
        """
        data = data or {}
        sleep = data.get('sleep')
        if sleep is not None:
            def sleep_fn():
                i = 0
                while i < sleep:
                    job.set_progress((i / sleep) * 100)
                    time.sleep(1)
                    i += 1
                job.set_progress(100)

            t = threading.Thread(target=sleep_fn, daemon=True)
            t.start()
            t.join()
        return True

    @api_method(CoreDebugArgs, CoreDebugResult, roles=['FULL_ADMIN'])
    async def debug(self, data):
        """
        Setup middlewared for remote debugging.

        engine currently used:
          - REMOTE_PDB: Remote vanilla PDB (over TCP sockets)

        options:
            - bind_address: local ip address to bind the remote debug session to
            - bind_port: local port to listen on
            - threaded: run debugger in a new thread instead of the main event loop
        """
        if data['threaded']:
            self.middleware.create_task(
                self.middleware.run_in_thread(
                    RemotePdb, data['bind_address'], data['bind_port']
                )
            )
        else:
            RemotePdb(data['bind_address'], data['bind_port']).set_trace()

    @private
    async def profile(self, method, params=None):
        return await self.middleware.call(method, *(params or []), profile=True)

    @private
    def threads_stacks(self):
        return get_threads_stacks()

    @private
    def get_pid(self):
        return os.getpid()

    @private
    def get_oom_score_adj(self, pid):
        try:
            with open(f'/proc/{pid}/oom_score_adj', 'r') as f:
                return int(f.read().strip())
        except ValueError:
            self.logger.error("Value inside of /proc/%r/oom_score_adj is NOT a number.", pid)
        except Exception:
            self.logger.error("Unexpected error looking up process %r.", pid, exc_info=True)
        return None

    @api_method(CoreBulkArgs, CoreBulkResult, authorization_required=False, pass_app=True)
    @job(lock=lambda args: f"bulk:{args[0]}")
    async def bulk(self, app, job, method, params, description):
        """
        Will sequentially call `method` with arguments from the `params` list. For example, running

            call("core.bulk", "zfs.snapshot.delete", [["tank@snap-1", true], ["tank@snap-2", false]])

        will call

            call("zfs.snapshot.delete", "tank@snap-1", true)
            call("zfs.snapshot.delete", "tank@snap-2", false)

        If the first call fails and the seconds succeeds (returning `true`), the result of the overall call will be:

            [
                {"result": null, "error": "Error deleting snapshot"},
                {"result": true, "error": null}
            ]

        Important note: the execution status of `core.bulk` will always be a `SUCCESS` (unless an unlikely internal
        error occurs). Caller must check for individual call results to ensure the absence of any call errors.
        """
        serviceobj, methodobj = self.middleware.get_method(method)

        if params:
            if mock := self.middleware._mock_method(method, params[0]):
                methodobj = mock

        if app is not None:
            if not app.authenticated_credentials.authorize("CALL", method):
                await self.middleware.log_audit_message_for_method(
                    method, methodobj, params[0] if params else [], app, True, False, False,
                )

                raise CallError("Not authorized", errno.EPERM)

        statuses = []
        if not params:
            return statuses

        for i, p in enumerate(params):
            progress_description = f"{i} / {len(params)}"
            if description is not None:
                progress_description += ": " + description.format(*p)

            job.set_progress(100 * i / len(params), progress_description)

            try:
                # Convention for the auditing backend is to only generate audit
                # entries for external callers to methods. app is only None
                # on internal calls to core.bulk.
                if app:
                    msg = await self.middleware.call_with_audit(method, serviceobj, methodobj, p, app)
                else:
                    msg = await self.middleware.call(method, *p)

                status = {"job_id": None, "result": None, "error": None}

                if isinstance(msg, Job):
                    b_job = msg
                    status["job_id"] = b_job.id
                    status["result"] = await msg.wait()
                    status["error"] = b_job.error
                else:
                    status["result"] = self.middleware.dump_result(serviceobj, methodobj, app, msg)

                statuses.append(status)
            except Exception as e:
                statuses.append({"job_id": None, "error": str(e), "result": None})

        return statuses

    _environ = {}

    @private
    async def environ(self):
        return self._environ

    @private
    async def environ_update(self, update):
        environ_update(update)

        for k, v in update.items():
            if v is None:
                self._environ.pop(k, None)
            else:
                self._environ[k] = v

        self.middleware.send_event('core.environ', 'CHANGED', fields=update)

    @api_method(CoreSetOptionsArgs, CoreSetOptionsResult, authentication_required=False, rate_limit=False,
                pass_app=True)
    async def set_options(self, app, options):
        if "legacy_jobs" in options:
            app.legacy_jobs = options["legacy_jobs"]
        if "private_methods" in options:
            app.private_methods = options["private_methods"]
        if "py_exceptions" in options:
            app.py_exceptions = options["py_exceptions"]

        return {
            "legacy_jobs": app.legacy_jobs,
            "private_methods": app.private_methods,
            "py_exceptions": app.py_exceptions,
        }

    @api_method(CoreSubscribeArgs, CoreSubscribeResult, authorization_required=False, pass_app=True)
    async def subscribe(self, app, event):
        if not self.middleware.can_subscribe(app, event):
            raise CallError('Not authorized', errno.EACCES)

        ident = str(uuid.uuid4())
        await app.subscribe(ident, event)
        return ident

    @api_method(CoreUnsubscribeArgs, CoreUnsubscribeResult, authorization_required=False, pass_app=True)
    async def unsubscribe(self, app, ident):
        await app.unsubscribe(ident)
