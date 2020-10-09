import os

from copy import deepcopy
from itertools import chain

from middlewared.schema import Bool, Cron, Dict, HostPath, Int, IPAddr, List, Path, Str
from middlewared.service import ValidationErrors
from middlewared.utils import run as _run
from middlewared.validators import Match, Range


mapping = {
    'string': Str,
    'int': Int,
    'boolean': Bool,
    'path': Path,
    'hostpath': HostPath,
    'list': List,
    'dict': Dict,
    'ipaddr': IPAddr,
    'cron': Cron,
}

CHART_NAMESPACE_PREFIX = 'ix-'
RESERVED_NAMES = [
    ('ixExternalInterfacesConfiguration', list),
    ('ixExternalInterfacesConfigurationNames', list),
    ('ixVolumes', list),
]


def get_namespace(release_name):
    return f'{CHART_NAMESPACE_PREFIX}{release_name}'


async def run(*args, **kwargs):
    kwargs['env'] = dict(os.environ, KUBECONFIG='/etc/rancher/k3s/k3s.yaml')
    return await _run(*args, **kwargs)


async def get_storage_class_name(release):
    return f'ix-storage-class-{release}'


def update_conditional_validation(dict_obj, variable_details):
    schema = variable_details['schema']
    for var in filter(lambda k: any(c in k['schema'] for c in ('show_subquestions_if', 'show_if')), schema['attrs']):
        var_schema = var['schema']
        attrs = []
        filters = []
        if 'show_subquestions_if' in var_schema:
            filters.append([var['variable'], '=', var_schema['show_subquestions_if']])
            attrs.extend([a['variable'] for a in var_schema['subquestions']])

        if 'show_if' in var_schema:
            filters.extend(var_schema['show_if'])
            attrs.append(var['variable'])

        dict_obj.conditional_validation[var['variable']] = {'filters': filters, 'attrs': attrs}

    return dict_obj


def get_schema(variable_details):
    schema_details = variable_details['schema']
    schema_class = mapping[schema_details['type']]

    # Validation is ensured at chart level to ensure that we don't have enum for say boolean
    obj_kwargs = {k: schema_details[k] for k in filter(
        lambda k: k in schema_details,
        ('required', 'default', 'private', 'enum', 'ipv4', 'ipv6', 'cidr', 'null')
    )}

    if schema_class not in (Cron, Dict):
        obj = schema_class(variable_details['variable'], **obj_kwargs)
    else:
        obj = schema_class(
            variable_details['variable'],
            *list(chain.from_iterable(get_schema(var) for var in schema_details.get('attrs', []))), **obj_kwargs
        )
        if schema_class == Dict:
            obj = update_conditional_validation(obj, variable_details)

    result = []

    obj.ref = schema_details.get('$ref', [])

    if schema_class in (Str, Int):
        range_vars = ['min', 'max'] if schema_class == Int else ['min_length', 'max_length']
        range_args = {k: schema_details[v] for k, v in zip(['min', 'max'], range_vars) if schema_details.get(v)}
        if range_args:
            obj.validators.append(Range(**range_args))

        if schema_class == Str:
            if 'valid_chars' in schema_details:
                obj.validators.append(Match(schema_details['valid_chars']))

    if schema_class == List:
        obj.items = list(chain.from_iterable(get_schema(i) for i in schema_details['items']))
        # To make sure that subquestions are added correctly for list, we would have to iterate over the schema
        # again as we can't judge in the first go which value of the list maps to which item
    elif 'subquestions' in schema_details:
        result.extend(list(chain.from_iterable(get_schema(i) for i in schema_details['subquestions'])))

    result.insert(0, obj)
    return result


def clean_value_of_attr_for_upgrade(orig_value, variable):
    value = deepcopy(orig_value)
    valid_attrs = {v['variable']: v for v in variable['schema']['attrs']}
    for k, v in orig_value.items():
        if k not in valid_attrs:
            value.pop(k)
        if isinstance(v, dict) and valid_attrs[k]['schema']['type'] == 'dict':
            value[k] = clean_value_of_attr_for_upgrade(v, valid_attrs[k])

    return value


def clean_values_for_upgrade(original_values, questions_details):
    return clean_value_of_attr_for_upgrade(
        original_values, {
            'schema': {
                'type': 'dict',
                'attrs': questions_details,
            }
        }
    )


def get_network_attachment_definition_name(release, count):
    return f'ix-{release}-{count}'


def get_list_item_from_value(value, question_attr):
    for index, attr in enumerate(question_attr.items):
        try:
            attr.validate(value)
        except ValidationErrors:
            pass
        else:
            return index, attr
