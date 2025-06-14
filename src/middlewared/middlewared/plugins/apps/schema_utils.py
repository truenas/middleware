import itertools

from middlewared.service import ValidationErrors
from middlewared.schema import (
    Attribute, Bool, Cron, Dict, Dir, File, HostPath, Int, IPAddr, List, NOT_PROVIDED, Path, Str, URI,
)
from middlewared.validators import Match, Range, validate_schema


SCHEMA_MAPPING = {
    'string': Str,
    'int': Int,
    'boolean': Bool,
    'path': Path,
    # to support large text / toml data of upto 1MiB
    'text': lambda *args, **kwargs: Str(*args, **kwargs, max_length=1024 * 1024),
    'hostpath': HostPath,
    'hostpathdirectory': Dir,
    'hostpathfile': File,
    'list': List,
    'dict': Dict,
    'ipaddr': IPAddr,
    'cron': Cron,
    'uri': URI,
}


def construct_schema(
    item_version_details: dict, new_values: dict, update: bool, old_values: dict | object = NOT_PROVIDED
) -> dict:
    schema_name = f'app_{"update" if update else "create"}'
    attrs = list(itertools.chain.from_iterable(
        get_schema(q, False, old_values) for q in item_version_details['schema']['questions']
    ))
    dict_obj = update_conditional_defaults(
        Dict(schema_name, *attrs, update=False, additional_attrs=True), {
            'schema': {'attrs': item_version_details['schema']['questions']}
        }
    )

    verrors = ValidationErrors()
    verrors.add_child('values', validate_schema(
        attrs, new_values, True, dict_kwargs={
            'conditional_defaults': dict_obj.conditional_defaults, 'update': False,
        }
    ))
    return {
        'verrors': verrors,
        'new_values': new_values,
        'dict_obj': dict_obj,
        'schema_name': schema_name,
    }


def update_conditional_defaults(dict_obj: Dict, variable_details: dict) -> Dict:
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

        dict_obj.conditional_defaults[var['variable']] = {'filters': filters, 'attrs': attrs}

    return dict_obj


def get_schema(variable_details: dict, update: bool, existing: dict | object = NOT_PROVIDED) -> list:
    schema_details = variable_details['schema']
    schema_class = SCHEMA_MAPPING[schema_details['type']]
    cur_val = existing.get(variable_details['variable'], NOT_PROVIDED) if isinstance(existing, dict) else NOT_PROVIDED

    # Validation is ensured at chart level to ensure that we don't have enum for say boolean
    obj_kwargs = {k: schema_details[k] for k in filter(
        lambda k: k in schema_details,
        ('required', 'default', 'private', 'ipv4', 'ipv6', 'cidr', 'null', 'additional_attrs', 'editable', 'empty')
    )}
    if schema_details.get('immutable') and cur_val is not NOT_PROVIDED:
        obj_kwargs['default'] = cur_val
        obj_kwargs['editable'] = False

    if schema_class not in (Cron, Dict):
        obj = schema_class(variable_details['variable'], **obj_kwargs)
    else:
        obj = schema_class(
            variable_details['variable'],
            *list(itertools.chain.from_iterable(
                get_schema(var, update, cur_val or NOT_PROVIDED) for var in schema_details.get('attrs', [])
            )),
            update=update, **obj_kwargs
        )
        if schema_class == Dict:
            obj = update_conditional_defaults(obj, variable_details)

    result = []

    obj.ref = schema_details.get('$ref', [])

    if schema_class in (Str, Int):
        range_vars = ['min', 'max'] if schema_class == Int else ['min_length', 'max_length']
        range_args = {f'{k}_': schema_details[v] for k, v in zip(['min', 'max'], range_vars) if schema_details.get(v)}
        if range_args:
            obj.validators.append(Range(**range_args))

        if 'enum' in schema_details:
            obj.enum = [v['value'] for v in schema_details['enum']]

        if schema_class == Str:
            if range_args.get('max_'):
                # This needs to be done as string schema has built in support for max length as
                # well apart from the range validator we add
                obj.max_length = range_args['max_']
            if 'valid_chars' in schema_details:
                obj.validators.append(Match(
                    schema_details['valid_chars'], explanation=schema_details.get('valid_chars_error')
                ))

    if schema_class == List:
        obj.items = list(itertools.chain.from_iterable(get_schema(i, update) for i in schema_details['items']))
    elif 'subquestions' in schema_details:
        result.extend(list(itertools.chain.from_iterable(
            get_schema(i, update, existing) for i in schema_details['subquestions']
        )))

    result.insert(0, obj)
    return result


def get_list_item_from_value(value: list, question_attr: List) -> tuple[int,  Attribute]:
    for index, attr in enumerate(question_attr.items):
        try:
            attr.validate(value)
        except ValidationErrors:
            pass
        else:
            return index, attr
