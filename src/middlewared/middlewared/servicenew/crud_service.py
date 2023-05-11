import copy

from middlewared.schema import accepts, Bool, convert_schema, Dict, Int, List, OROperator, Patch, Ref, returns

from .base import ServiceBase


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
