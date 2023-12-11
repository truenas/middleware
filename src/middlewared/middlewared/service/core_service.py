import asyncio
import errno
import inspect
import ipaddress
import os
import re
import socket
import threading
import time
import traceback

from collections import defaultdict
from remote_pdb import RemotePdb
from subprocess import run

import middlewared.main

from middlewared.common.environ import environ_update
from middlewared.job import Job
from middlewared.pipe import Pipes
from middlewared.schema import accepts, Any, Bool, Datetime, Dict, Int, List, returns, Str
from middlewared.service_exception import CallError, ValidationErrors
from middlewared.settings import conf
from middlewared.utils import BOOTREADY, filter_list, MIDDLEWARE_RUN_DIR
from middlewared.utils.debug import get_frame_details, get_threads_stacks
from middlewared.utils.privilege import credential_has_full_admin, credential_is_limited_to_own_jobs
from middlewared.validators import IpAddress, Range

from .compound_service import CompoundService
from .config_service import ConfigService
from .crud_service import CRUDService
from .decorators import filterable, filterable_returns, job, no_auth_required, no_authz_required, pass_app, private
from .service import Service


MIDDLEWARE_STARTED_SENTINEL_PATH = os.path.join(MIDDLEWARE_RUN_DIR, 'middlewared-started')


def is_service_class(service, klass):
    return (
        isinstance(service, klass) or
        (isinstance(service, CompoundService) and any(isinstance(part, klass) for part in service.parts))
    )


class CoreService(Service):

    class Config:
        cli_private = True

    @accepts(Str('id'), Int('cols'), Int('rows'))
    async def resize_shell(self, id_, cols, rows):
        """
        Resize terminal session (/websocket/shell) to cols x rows
        """
        shell = middlewared.main.ShellApplication.shells.get(id_)
        if shell is None:
            raise CallError('Shell does not exist', errno.ENOENT)

        shell.resize(cols, rows)

    @filterable
    @filterable_returns(Dict(
        'session',
        Str('id'),
        Str('socket_family'),
        Str('address'),
        Bool('authenticated'),
        Int('call_count'),
    ))
    def sessions(self, filters, options):
        """
        Get currently open websocket sessions.
        """
        sessions = []
        for i in self.middleware.get_wsclients().values():
            try:
                session_id = i.session_id
                authenticated = i.authenticated
                call_count = i._softhardsemaphore.counter
                socket_family = socket.AddressFamily(i.request.transport.get_extra_info('socket').family).name
                address = ''
                if addr := i.request.headers.get('X-Real-Remote-Addr'):
                    port = i.request.headers.get('X-Real-Remote-Port')
                    address = f'{addr}:{port}' if all((addr, port)) else address
                else:
                    if (info := i.request.transport.get_extra_info('peername')):
                        if isinstance(info, list) and len(info) == 2:
                            address = f'{info[0]}:{info[1]}'
            except AttributeError:
                # underlying websocket connection can be ripped down in process
                # of enumerating this information. This is non-fatal, so ignore it.
                pass
            except Exception:
                self.logger.warning('Failed enumerating websocket session.', exc_info=True)
                break
            else:
                sessions.append({
                    'id': session_id,
                    'socket_family': socket_family,
                    'address': address,
                    'authenticated': authenticated,
                    'call_count': call_count,
                })

        return filter_list(sessions, filters, options)

    @accepts(Bool('debug_mode'))
    async def set_debug_mode(self, debug_mode):
        """
        Set `debug_mode` for middleware.
        """
        conf.debug_mode = debug_mode

    @accepts()
    @returns(Bool())
    async def debug_mode_enabled(self):
        return conf.debug_mode

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

    def __job_by_credential_and_id(self, credential, job_id):
        if not credential_is_limited_to_own_jobs(credential):
            return self.middleware.jobs[job_id]

        if not credential.is_user_session or credential_has_full_admin(credential):
            return self.middleware.jobs[job_id]

        job = self.middleware.jobs[job_id]

        if job.credentials.user['username'] == credential.user['username']:
            return job

        raise CallError(f'{job_id}: job is not owned by current session.', errno.EPERM)

    @no_authz_required
    @filterable
    @filterable_returns(Dict(
        'job',
        Int('id'),
        Str('method'),
        List('arguments'),
        Bool('transient'),
        Str('description', null=True),
        Bool('abortable'),
        Str('logs_path', null=True),
        Str('logs_excerpt', null=True),
        Dict(
            'progress',
            Int('percent', null=True),
            Str('description', null=True),
            Any('extra', null=True),
        ),
        Any('result', null=True),
        Str('error', null=True),
        Str('exception', null=True),
        Dict(
            'exc_info',
            Str('repr', null=True),
            Str('type', null=True),
            Any('extra', null=True),
            null=True
        ),
        Str('state'),
        Datetime('time_started', null=True),
        Datetime('time_finished', null=True),
        Dict(
            'credentials',
            Str('type'),
            Dict('data', additional_attrs=True),
            null=True,
        ),
        register=True,
    ))
    @pass_app(rest=True)
    def get_jobs(self, app, filters, options):
        """
        Get information about long-running jobs.
        If authenticated session does not have the FULL_ADMIN role, only
        jobs owned by the current authenticated session will be returned.
        """
        if app and credential_is_limited_to_own_jobs(app.authenticated_credentials):
            username = app.authenticated_credentials.user['username']
            jobs = list(self.middleware.jobs.for_username(username).values())
        else:
            jobs = list(self.middleware.jobs.all().values())

        raw_result = options['extra'].get('raw_result', True)
        jobs = filter_list([
            i.__encode__(raw_result) for i in jobs
        ], filters, options)
        return jobs

    @no_authz_required
    @accepts(Int('id'))
    @job()
    async def job_wait(self, job, id_):
        target_job = self.__job_by_credential_and_id(job.credentials, id_)

        return await job.wrap(target_job)

    @private
    @accepts(Int('id'), Dict(
        'job-update',
        Dict('progress', additional_attrs=True),
    ))
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

    @no_authz_required
    @accepts(Int('id'))
    @pass_app(rest=True)
    def job_abort(self, app, id_):
        if app is None:
            job = self.middleware.jobs[id_]
        else:
            job = self.__job_by_credential_and_id(app.authenticated_credentials, id_)

        return job.abort()

    def _should_list_service(self, name, service, target):
        if service._config.private is True:
            if not (target == 'REST' and name == 'resttest'):
                return False

        if target == 'CLI' and service._config.cli_private:
            return False

        return True

    @no_auth_required
    @accepts(Str('target', enum=['WS', 'CLI', 'REST'], default='WS'))
    @private
    @pass_app()
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

            config = {k: v for k, v in list(v._config.__dict__.items())
                      if not k.startswith(('_', 'process_pool', 'thread_pool'))}
            if config['cli_description'] is None:
                if v.__doc__:
                    config['cli_description'] = inspect.getdoc(v).split("\n")[0].strip()

            services[k] = {
                'config': config,
                'type': _typ,
            }

        return services

    @no_auth_required
    @accepts(Str('service', default=None, null=True), Str('target', enum=['WS', 'CLI', 'REST'], default='WS'))
    @private
    @pass_app()
    def get_methods(self, app, service, target):
        """
        Return methods metadata of every available service.

        `service` parameter is optional and filters the result for a single service.
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
                if hasattr(method, '_private'):
                    continue
                if target == 'CLI' and hasattr(method, '_cli_private'):
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
                    for i in range(int((len(sections) - 1) / 2)):
                        idx = (i + 1) * 2 - 1
                        reg = re.search(r'examples(?:\((.+)\))?', sections[idx])
                        if reg is None:
                            continue
                        exname = reg.groups()[0]
                        if exname is None:
                            exname = '__all__'
                        examples[exname].append(sections[idx + 1])

                method_schemas = {'accepts': None, 'returns': None}
                for schema_type in method_schemas:
                    args_descriptions_doc = doc or ''
                    if attr == 'update':
                        if do_create := getattr(svc, 'do_create', None):
                            args_descriptions_doc += "\n" + inspect.getdoc(do_create)
                    method_schemas[schema_type] = self.get_json_schema(
                        getattr(method, schema_type, None), args_descriptions_doc
                    )

                if filterable_schema := getattr(method, '_filterable_schema', None):
                    # filterable_schema is OROperator here and we just want it's specific schema
                    filterable_schema = self.get_json_schema([filterable_schema.schemas[1]], None)[0]
                elif attr == 'query':
                    if isinstance(svc, CompoundService):
                        for part in svc.parts:
                            if hasattr(part, 'do_create'):
                                d = inspect.getdoc(part.do_create)
                                break
                        else:
                            d = None

                        for part in svc.parts:
                            if hasattr(part, 'ENTRY'):
                                filterable_schema = self.get_json_schema(
                                    [self.middleware._schemas[part.ENTRY.name]],
                                    d,
                                )[0]
                                break
                    elif hasattr(svc, 'ENTRY'):
                        d = None
                        if hasattr(svc, 'do_create'):
                            d = inspect.getdoc(svc.do_create)
                        filterable_schema = self.get_json_schema(
                            [self.middleware._schemas[svc.ENTRY.name]],
                            d,
                        )[0]

                if method_schemas['accepts'] is None:
                    raise RuntimeError(f'Method {method_name} is public but has no @accepts()')

                data[method_name] = {
                    'description': doc,
                    'cli_description': (doc or '').split('\n\n')[0].split('.')[0].replace('\n', ' '),
                    'examples': examples,
                    'item_method': True if item_method else hasattr(method, '_item_method'),
                    'no_auth_required': no_auth_required,
                    'filterable': hasattr(method, '_filterable'),
                    'filterable_schema': filterable_schema,
                    'pass_application': hasattr(method, '_pass_app'),
                    'extra_methods': method._rest_api_metadata['extra_methods'] if hasattr(
                        method, '_rest_api_metadata') else None,
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
    def get_json_schema(self, schema, args_descriptions_doc):
        if not schema:
            return schema

        args_descriptions_doc = args_descriptions_doc or ''
        schema = [i.to_json_schema() for i in schema if not getattr(i, 'hidden', False)]

        names = set()
        for i in schema:
            names.add(i['_name_'])

            if i.get('type') == 'object':
                for j in i['properties'].values():
                    names.add(j['_name_'])

        args_descriptions = self._cli_args_descriptions(args_descriptions_doc, names)
        for i in schema:
            if not i.get('description') and i['_name_'] in args_descriptions:
                i['description'] = args_descriptions[i['_name_']]

            if i.get('type') == 'object':
                for j in i['properties'].values():
                    if not j.get('description') and j['_name_'] in args_descriptions:
                        j['description'] = args_descriptions[j['_name_']]

        return schema

    @accepts()
    def get_events(self):
        """
        Returns metadata for every possible event emitted from websocket server.
        """
        events = {}
        for name, attrs in self.middleware.get_events():
            if attrs['private']:
                continue

            events[name] = {
                'description': attrs['description'],
                'wildcard_subscription': attrs['wildcard_subscription'],
                'accepts': self.get_json_schema(list(filter(bool, attrs['accepts'])), attrs['description']),
                'returns': self.get_json_schema(list(filter(bool, attrs['returns'])), attrs['description']),
            }

        return events

    @private
    async def call_hook(self, name, args, kwargs=None):
        kwargs = kwargs or {}
        await self.middleware.call_hook(name, *args, **kwargs)

    @private
    async def event_send(self, name, event_type, kwargs=None):
        kwargs = kwargs or {}
        self.middleware.send_event(name, event_type, **kwargs)

    @accepts()
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

    @accepts(
        Dict(
            'options',
            Str('type', enum=['ICMP', 'ICMPV4', 'ICMPV6'], default='ICMP'),
            Str('hostname', required=True),
            Int('timeout', validators=[Range(min_=1, max_=60)], default=4),
            Int('count', default=None),
            Str('interface', default=None),
            Str('interval', default=None),
        ),
    )
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

    @accepts(
        Dict(
            'options',
            Str('ip', default=None),
            Str('interface', default=None),
        ),
    )
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

    @accepts(
        Str('method'),
        List('args'),
        Str('filename'),
        Bool('buffered', default=False),
    )
    @pass_app(rest=True)
    async def download(self, app, method, args, filename, buffered):
        """
        Core helper to call a job marked for download.

        Non-`buffered` downloads will allow job to write to pipe as soon as download URL is requested, job will stay
        blocked meanwhile. `buffered` downloads must wait for job to complete before requesting download URL, job's
        pipe output will be buffered to ramfs.

        Returns the job id and the URL for download.
        """
        job = await self.middleware.call(method, *args, pipes=Pipes(output=self.middleware.pipe(buffered)))
        token = await self.middleware.call('auth.generate_token', 300, {'filename': filename, 'job': job.id}, app=app)
        self.middleware.fileapp.register_job(job.id, buffered)
        return job.id, f'/_download/{job.id}?auth_token={token}'

    @private
    @no_authz_required
    @accepts(Dict('core-job', Int('sleep')))
    @job()
    def job_test(self, job, data):
        """
        Private no-op method to test a job, simply returning `true`.
        """
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

    @accepts(Dict(
        'options',
        Str('bind_address', default='0.0.0.0'),
        Int('bind_port', default=3000),
        Bool('threaded', default=False),
    ))
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

    @accepts(Str("method"), List("params"), Str("description", null=True, default=None))
    @job(lock=lambda args: f"bulk:{args[0]}")
    async def bulk(self, job, method, params, description):
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

        `description` contains format string for job progress (e.g. "Deleting snapshot {0[dataset]}@{0[name]}")
        """
        statuses = []
        if not params:
            return statuses

        for i, p in enumerate(params):
            progress_description = f"{i} / {len(params)}"
            if description is not None:
                progress_description += ": " + description.format(*p)

            job.set_progress(100 * i / len(params), progress_description)

            try:
                msg = await self.middleware.call(method, *p)
                status = {"result": msg, "error": None}

                if isinstance(msg, Job):
                    b_job = msg
                    status["job_id"] = b_job.id
                    status["result"] = await msg.wait()

                    if b_job.error:
                        status["error"] = b_job.error

                statuses.append(status)
            except Exception as e:
                statuses.append({"result": None, "error": str(e)})

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

    RE_ARG = re.compile(r'`[a-z0-9_]+`', flags=re.IGNORECASE)
    RE_NEW_ARG_START = re.compile(r'`|[A-Z]|\*')

    def _cli_args_descriptions(self, doc, names):
        descriptions = defaultdict(list)

        current_names = set()
        current_doc = []
        for line in (doc or '').split('\n'):
            if (
                (matched_line_names := {name.strip('`') for name in self.RE_ARG.findall(line)}) and
                (line_names := matched_line_names & names)
            ):
                if line_names & current_names or not self.RE_NEW_ARG_START.match(line):
                    current_names |= line_names
                else:
                    for name in current_names:
                        descriptions[name] += current_doc

                    current_names = line_names
                    current_doc = []

                current_doc.append(line)
            elif line:
                current_doc.append(line)
            else:
                for name in current_names:
                    descriptions[name] += current_doc

                current_names = set()
                current_doc = []

        return {
            k: '\n'.join(v)
            for k, v in descriptions.items()
        }
