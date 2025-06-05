import asyncio
import copy
import errno
from typing import Annotated

from pydantic import create_model, Field

from middlewared.api import API_LOADING_FORBIDDEN, api_method
from middlewared.api.base.model import (
    BaseModel, query_result, query_result_item, added_event_model, changed_event_model, removed_event_model,
)
if not API_LOADING_FORBIDDEN:
    from middlewared.api.current import QueryArgs, QueryOptions
from middlewared.service_exception import CallError, InstanceNotFound
from middlewared.schema import accepts, Any, Bool, convert_schema, Dict, Int, List, OROperator, Patch, Ref, returns
from middlewared.utils import filter_list
from middlewared.utils.type import copy_function_metadata

from .base import ServiceBase
from .decorators import filterable, pass_app, private
from .service import Service
from .service_mixin import ServiceChangeMixin


PAGINATION_OPTS = ('count', 'get', 'limit', 'offset', 'select')


def get_datastore_primary_key_schema(klass):
    return convert_schema({
        'type': klass._config.datastore_primary_key_type,
        'name': klass._config.datastore_primary_key,
    })


def get_instance_args(entry, primary_key="id"):
    return create_model(
        entry.__name__.removesuffix("Entry") + "GetInstanceArgs",
        __base__=(BaseModel,),
        id=Annotated[entry.model_fields[primary_key].annotation, Field()],
        options=Annotated[QueryOptions, Field(default={})],
    )


def get_instance_result(entry):
    return create_model(
        entry.__name__.removesuffix("Entry") + "GetInstanceResult",
        __base__=(BaseModel,),
        __module__=entry.__module__,
        result=Annotated[entry, Field()],
    )


class CRUDServiceMetabase(ServiceBase):

    def __new__(cls, name, bases, attrs):
        klass = super().__new__(cls, name, bases, attrs)
        if any(
            name == c_name and len(bases) == len(c_bases) and all(b.__name__ == c_b for b, c_b in zip(bases, c_bases))
            for c_name, c_bases in (
                ('CRUDService', ('ServiceChangeMixin', 'Service')),
                ('SharingTaskService', ('CRUDService',)),
                ('SharingService', ('SharingTaskService',)),
                ('TaskPathService', ('SharingTaskService',)),
            )
        ):
            return klass

        config = klass._config
        entry = config.entry
        private = config.private
        cli_private = config.cli_private

        if not private:
            if not config.role_prefix:
                raise ValueError(f'{config.namespace}: public CRUDService must have role_prefix defined')
            # TODO: Enforce after SMB gets converted
            # if not config.entry:
            #     raise ValueError(f'{config.namespace}: public CRUDService must have entry defined')

        if entry is not None:
            # FIXME: This is to prevent `Method cloudsync.credentials.ENTRY is public but has no @accepts()`, remove
            # eventually.
            klass.ENTRY = None
            # FIXME: Remove `wraps` handling when we get rid of `@filterable` in `CRUDService.query` definition
            query_result_model = query_result(entry)
            if (
                any(klass.query == getattr(parent, 'query', None) for parent in klass.__mro__[1:]) or
                not hasattr(klass.query, '_filterable') or klass.query._filterable is False
            ):
                # No need to inject api method if filterable has been explicitly specified
                klass.query = api_method(QueryArgs, query_result_model, private=private, cli_private=cli_private)(
                    klass.query.wraps if hasattr(klass.query, "wraps") else klass.query
                )
            else:
                if getattr(klass.query, '_legacy_filterable', False):
                    raise RuntimeError(
                        'Legacy-style @filterable can\'t be used on classes with new-style `entry` defined. Please, '
                        'either use @filterable_api_method or don\'t use any decorator at all (it will be applied '
                        f'automatically). Offending class: {klass!r}.'
                    )

            # FIXME: Remove `wraps` handling when we get rid of `@accepts` in `CRUDService.get_instance` definition
            get_instance_args_model = get_instance_args(entry, primary_key=config.datastore_primary_key)
            get_instance_result_model = get_instance_result(entry)
            klass.get_instance = api_method(
                get_instance_args_model, get_instance_result_model, private=private, cli_private=cli_private
            )(klass.get_instance.wraps)

            klass._register_models = [
                (query_result_model, query_result, entry.__name__),
                (query_result_model.__annotations__["result"].__args__[1],
                 query_result_item, entry.__name__),
                (get_instance_args_model, get_instance_args, entry.__name__),
                (get_instance_result_model, get_instance_result, entry.__name__),
            ]

            return klass

        namespace = config.namespace.replace('.', '_')
        entry_key = f'{namespace}_entry'
        if klass.ENTRY == NotImplementedError:
            klass.ENTRY = Dict(entry_key, additional_attrs=True)
        else:
            # We would like to ensure that not all fields are required as select can filter out fields
            if isinstance(klass.ENTRY, (Dict, Patch)):
                entry_key = klass.ENTRY.name
            elif isinstance(klass.ENTRY, Ref):
                entry_key = f'{klass.ENTRY.name}_ref_entry'
            else:
                raise ValueError('Result entry should be Dict/Patch/Ref instance')

        result_entry = copy.deepcopy(klass.ENTRY)
        query_result_entry = copy.deepcopy(klass.ENTRY)
        if isinstance(result_entry, Ref):
            query_result_entry = Patch(result_entry.name, entry_key)
        if isinstance(result_entry, Patch):
            query_result_entry.patches.append(('attr', {'update': True}))
        else:
            query_result_entry.update = True

        result_entry.register = True
        query_result_entry.register = False

        query_method = klass.query.wraps if hasattr(klass.query, 'returns') else klass.query
        klass.query = returns(OROperator(
            List('query_result', items=[copy.deepcopy(query_result_entry)]),
            query_result_entry,
            Int('count'),
            result_entry,
            name='query_result',
        ))(query_method)

        klass.get_instance = returns(Ref(entry_key))(klass.get_instance)

        for m_name in filter(lambda m: hasattr(klass, m), ('do_create', 'do_update')):
            for d_name, decorator in filter(
                lambda d: not hasattr(getattr(klass, m_name), d[0]), (('returns', returns), ('accepts', accepts))
            ):
                new_name = f'{namespace}_{m_name.split("_")[-1]}'
                if d_name == 'returns':
                    new_name += '_returns'

                patch_entry = Patch(entry_key, new_name, register=True)
                schema = []
                if d_name == 'accepts':
                    patch_entry.patches.append(('rm', {
                        'name': config.datastore_primary_key,
                        'safe_delete': True,
                    }))
                    if m_name == 'do_update':
                        patch_entry.patches.append(('attr', {'update': True}))
                        schema.append(get_datastore_primary_key_schema(klass))

                schema.append(patch_entry)
                setattr(klass, m_name, decorator(*schema)(getattr(klass, m_name)))

        if hasattr(klass, 'do_delete'):
            if not hasattr(klass.do_delete, 'accepts'):
                klass.do_delete = accepts(get_datastore_primary_key_schema(klass))(klass.do_delete)
            if not hasattr(klass.do_delete, 'returns'):
                klass.do_delete = returns(Bool(
                    'deleted', description='Will return `true` if `id` is deleted successfully'
                ))(klass.do_delete)

        return klass


class CRUDService(ServiceChangeMixin, Service, metaclass=CRUDServiceMetabase):
    """
    CRUD service abstract class

    Meant for services in that a set of entries can be queried, new entry
    create, updated and/or deleted.

    CRUD stands for Create Retrieve Update Delete.
    """

    ENTRY = NotImplementedError

    def __init__(self, middleware):
        super().__init__(middleware)
        if self._config.event_register:
            if self._config.role_prefix:
                roles = [f'{self._config.role_prefix}_READ']
            else:
                roles = ['READONLY_ADMIN']

            if self._config.entry is not None:
                kwargs = dict(models={
                    'ADDED': added_event_model(self._config.entry),
                    'CHANGED': changed_event_model(self._config.entry),
                    'REMOVED': removed_event_model(self._config.entry),
                })
            else:
                kwargs = dict(returns=Ref(self.ENTRY.name))

            self.middleware.event_register(
                f'{self._config.namespace}.query',
                f'Sent on {self._config.namespace} changes.',
                private=self._config.private,
                roles=roles,
                **kwargs,
            )

    @private
    async def get_options(self, options):
        options = options or {}
        options['extend'] = self._config.datastore_extend
        options['extend_context'] = self._config.datastore_extend_context
        options['extend_fk'] = self._config.datastore_extend_fk
        options['prefix'] = self._config.datastore_prefix
        return options

    @filterable
    async def query(self, filters, options):
        if not self._config.datastore:
            raise NotImplementedError(
                f'{self._config.namespace}.query must be implemented or a '
                '`datastore` Config attribute provided.'
            )

        if not filters:
            filters = []

        options = await self.get_options(options)

        # In case we are extending which may transform the result in numerous ways
        # we can only filter the final result. Exception is when forced to use sql
        # for filters for performance reasons.
        if not options['force_sql_filters'] and options['extend']:
            datastore_options = options.copy()
            for option in PAGINATION_OPTS:
                datastore_options.pop(option, None)
            result = await self.middleware.call(
                'datastore.query', self._config.datastore, [], datastore_options
            )
            return await self.middleware.run_in_thread(
                filter_list, result, filters, options
            )
        else:
            return await self.middleware.call(
                'datastore.query', self._config.datastore, filters, options,
            )

    @pass_app(message_id=True, rest=True)
    async def create(self, app, audit_callback, message_id, data):
        return await self.middleware._call(
            f'{self._config.namespace}.create', self, await self._get_crud_wrapper_func(
                self.do_create, 'create', 'ADDED',
            ), [data], app=app, audit_callback=audit_callback, message_id=message_id,
        )

    create.audit_callback = True

    @pass_app(message_id=True, rest=True)
    async def update(self, app, audit_callback, message_id, id_, data):
        return await self.middleware._call(
            f'{self._config.namespace}.update', self, await self._get_crud_wrapper_func(
                self.do_update, 'update', 'CHANGED', id_,
            ), [id_, data], app=app, audit_callback=audit_callback, message_id=message_id,
        )

    update.audit_callback = True

    @pass_app(message_id=True, rest=True)
    async def delete(self, app, audit_callback, message_id, id_, *args):
        return await self.middleware._call(
            f'{self._config.namespace}.delete', self, await self._get_crud_wrapper_func(
                self.do_delete, 'delete', 'REMOVED', id_,
            ), [id_] + list(args), app=app, audit_callback=audit_callback, message_id=message_id,
        )

    delete.audit_callback = True

    async def _get_crud_wrapper_func(self, func, action, event_type, oid=None):
        def send_event(rv):
            if self._config.event_send and (action == 'delete' or isinstance(rv, dict) and 'id' in rv):
                kwargs = {'id': oid or rv['id']}
                if isinstance(rv, dict):
                    kwargs['fields'] = rv
                self.middleware.send_event(f'{self._config.namespace}.query', event_type, **kwargs)

        if asyncio.iscoroutinefunction(func):
            async def nf(*args, **kwargs):
                rv = await func(*args, **kwargs)
                await self.middleware.call_hook(f'{self._config.namespace}.post_{action}', rv)
                send_event(rv)
                return rv
        else:
            def nf(*args, **kwargs):
                rv = func(*args, **kwargs)
                self.middleware.call_hook_sync(f'{self._config.namespace}.post_{action}', rv)
                send_event(rv)
                return rv

        copy_function_metadata(func, nf)
        return nf

    @accepts(
        Any('id'),
        Patch(
            'query-options', 'query-options-get_instance',
            ('edit', {
                'name': 'force_sql_filters',
                'method': lambda x: setattr(x, 'default', True),
            }),
            register=True,
        ),
    )
    async def get_instance(self, id_, options):
        """
        Returns instance matching `id`. If `id` is not found, Validation error is raised.

        Please see `query` method documentation for `options`.
        """
        instance = await self.middleware.call(
            f'{self._config.namespace}.query',
            [[self._config.datastore_primary_key, '=', id_]],
            options
        )
        if not instance:
            raise InstanceNotFound(f'{self._config.verbose_name} {id_} does not exist')
        return instance[0]

    @private
    @accepts(Any('id'), Ref('query-options-get_instance'))
    def get_instance__sync(self, id_, options):
        """
        Synchronous implementation of `get_instance`.
        """
        instance = self.middleware.call_sync(
            f'{self._config.namespace}.query',
            [[self._config.datastore_primary_key, '=', id_]],
            options,
        )
        if not instance:
            raise InstanceNotFound(f'{self._config.verbose_name} {id_} does not exist')
        return instance[0]

    async def _ensure_unique(self, verrors, schema_name, field_name, value, id_=None, query_field_name=None):
        if query_field_name is None:
            query_field_name = field_name
        f = [(query_field_name, '=', value)]
        if id_ is not None:
            f.append(('id', '!=', id_))
        instance = await self.middleware.call(f'{self._config.namespace}.query', f)
        if instance:
            verrors.add(
                '.'.join(filter(None, [schema_name, field_name])),
                f'Object with this {field_name} already exists'
            )

    @private
    async def check_dependencies(self, id_, ignored=None):
        """
        Raises EBUSY CallError if some datastores/services (except for `ignored`) reference object specified by id.
        """
        dependencies = await self.get_dependencies(id_, ignored)
        if dependencies:
            dep_err = 'This object is being used by following service(s):\n'
            for index, dependency in enumerate(dependencies.values()):
                key = 'service' if dependency['service'] else 'datastore'
                dep_err += f'{index + 1}) {dependency[key]!r} {key.capitalize()}\n'

            raise CallError(dep_err, errno.EBUSY, {'dependencies': list(dependencies.values())})

    @private
    async def get_dependencies(self, id_, ignored=None):
        ignored = ignored or set()

        services = {
            service['config'].get('datastore'): (name, service)
            for name, service in (await self.middleware.call('core.get_services')).items()
            if service['config'].get('datastore')
        }

        dependencies = {}
        for datastore, fk in await self.middleware.call('datastore.get_backrefs', self._config.datastore):
            if datastore in ignored:
                continue

            if datastore in services:
                service = {
                    'name': services[datastore][0],
                    'type': services[datastore][1]['type'],
                }

                if service['name'] in ignored:
                    continue
            else:
                service = None

            objects = await self.middleware.call('datastore.query', datastore, [(fk, '=', id_)])
            if objects:
                data = {
                    'objects': objects,
                }
                if service is not None:
                    query_col = fk
                    prefix = services[datastore][1]['config'].get('datastore_prefix')
                    if prefix:
                        if query_col.startswith(prefix):
                            query_col = query_col[len(prefix):]

                    if service['type'] == 'config':
                        data = {
                            'key': query_col,
                        }

                    if service['type'] == 'crud':
                        data = {
                            'objects': await self.middleware.call(
                                f'{service["name"]}.query', [('id', 'in', [object_['id'] for object_ in objects])],
                            ),
                        }

                dependencies[datastore] = dict({
                    'datastore': datastore,
                    'service': service['name'] if service else None,
                }, **data)

        return dependencies
