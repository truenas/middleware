import asyncio
import copy
import errno

from middlewared.service_exception import CallError, InstanceNotFound
from middlewared.schema import accepts, Any, Bool, convert_schema, Dict, Int, List, OROperator, Patch, Ref, returns
from middlewared.utils import filter_list
from middlewared.utils.type import copy_function_metadata

from .base import ServiceBase
from .decorators import filterable, pass_app, private
from .service import Service
from .service_mixin import ServiceChangeMixin


def get_datastore_primary_key_schema(klass):
    return convert_schema({
        'type': klass._config.datastore_primary_key_type,
        'name': klass._config.datastore_primary_key,
    })


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
                ('TDBWrapCRUDService', ('CRUDService',)),
            )
        ):
            return klass

        namespace = klass._config.namespace.replace('.', '_')
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
                        'name': klass._config.datastore_primary_key,
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
            self.middleware.event_register(
                f'{self._config.namespace}.query',
                f'Sent on {self._config.namespace} changes.',
                private=self._config.private,
                returns=Ref(self.ENTRY.name),
            )

    @private
    async def get_options(self, options):
        options = options or {}
        options['extend'] = self._config.datastore_extend
        options['extend_context'] = self._config.datastore_extend_context
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
            datastore_options.pop('count', None)
            datastore_options.pop('get', None)
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

    @pass_app(rest=True)
    async def create(self, app, data):
        return await self.middleware._call(
            f'{self._config.namespace}.create', self, await self._get_crud_wrapper_func(
                self.do_create, 'create', 'ADDED',
            ), [data], app=app,
        )

    @pass_app(rest=True)
    async def update(self, app, id, data):
        return await self.middleware._call(
            f'{self._config.namespace}.update', self, await self._get_crud_wrapper_func(
                self.do_update, 'update', 'CHANGED', id,
            ), [id, data], app=app,
        )

    @pass_app(rest=True)
    async def delete(self, app, id, *args):
        return await self.middleware._call(
            f'{self._config.namespace}.delete', self, await self._get_crud_wrapper_func(
                self.do_delete, 'delete', 'REMOVED', id,
            ), [id] + list(args), app=app,
        )

    async def _get_crud_wrapper_func(self, func, action, event_type, oid=None):
        if asyncio.iscoroutinefunction(func):
            async def nf(*args, **kwargs):
                rv = await func(*args, **kwargs)
                await self.middleware.call_hook(f'{self._config.namespace}.post_{action}', rv)
                if self._config.event_send and (action == 'delete' or isinstance(rv, dict) and 'id' in rv):
                    self.middleware.send_event(f'{self._config.namespace}.query', event_type, id=oid or rv['id'])
                return rv
        else:
            def nf(*args, **kwargs):
                rv = func(*args, **kwargs)
                self.middleware.call_hook_sync(f'{self._config.namespace}.post_{action}', rv)
                if self._config.event_send and (action == 'delete' or isinstance(rv, dict) and 'id' in rv):
                    self.middleware.send_event(f'{self._config.namespace}.query', event_type, id=oid or rv['id'])
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
    async def get_instance(self, id, options):
        """
        Returns instance matching `id`. If `id` is not found, Validation error is raised.

        Please see `query` method documentation for `options`.
        """
        instance = await self.middleware.call(
            f'{self._config.namespace}.query',
            [[self._config.datastore_primary_key, '=', id]],
            options
        )
        if not instance:
            raise InstanceNotFound(f'{self._config.verbose_name} {id} does not exist')
        return instance[0]

    @private
    @accepts(Any('id'), Ref('query-options-get_instance'))
    def get_instance__sync(self, id, options):
        """
        Synchronous implementation of `get_instance`.
        """
        instance = self.middleware.call_sync(
            f'{self._config.namespace}.query',
            [[self._config.datastore_primary_key, '=', id]],
            options,
        )
        if not instance:
            raise InstanceNotFound(f'{self._config.verbose_name} {id} does not exist')
        return instance[0]

    async def _ensure_unique(self, verrors, schema_name, field_name, value, id=None):
        f = [(field_name, '=', value)]
        if id is not None:
            f.append(('id', '!=', id))
        instance = await self.middleware.call(f'{self._config.namespace}.query', f)
        if instance:
            verrors.add(
                '.'.join(filter(None, [schema_name, field_name])),
                f'Object with this {field_name} already exists'
            )

    @private
    async def check_dependencies(self, id, ignored=None):
        """
        Raises EBUSY CallError if some datastores/services (except for `ignored`) reference object specified by id.
        """
        dependencies = await self.get_dependencies(id, ignored)
        if dependencies:
            dep_err = 'This object is being used by following service(s):\n'
            for index, dependency in enumerate(dependencies.values()):
                key = 'service' if dependency['service'] else 'datastore'
                dep_err += f'{index + 1}) {dependency[key]!r} {key.capitalize()}\n'

            raise CallError(dep_err, errno.EBUSY, {'dependencies': list(dependencies.values())})

    @private
    async def get_dependencies(self, id, ignored=None):
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

            objects = await self.middleware.call('datastore.query', datastore, [(fk, '=', id)])
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
                                f'{service["name"]}.query', [('id', 'in', [object['id'] for object in objects])],
                            ),
                        }

                dependencies[datastore] = dict({
                    'datastore': datastore,
                    'service': service['name'] if service else None,
                }, **data)

        return dependencies
