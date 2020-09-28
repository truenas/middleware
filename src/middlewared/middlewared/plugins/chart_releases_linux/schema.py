from middlewared.schema import Bool, Dict, HostPath, Int, List, Str
from middlewared.validators import Match, Range


mapping = {
    'string': Str,
    'int': Int,
    'boolean': Bool,
    'hostpath': HostPath,
    'list': List,
    'dict': Dict,
}


def get_schema(variable_details):
    schema_details = variable_details['schema']
    schema_class = mapping[schema_details['type']]
    if schema_class != Dict:
        obj = schema_class(variable_details['variable'])
    else:
        obj = schema_class(variable_details['variable'], *[get_schema(var) for var in schema_details['attrs']])

    # Validation is ensured at chart level to ensure that we don't have enum for say boolean
    for k in filter(lambda k: k in schema_details, ('required', 'default', 'private', 'enum')):
        setattr(obj, k, schema_details[k])

    if schema_class in (Str, Int):
        range_vars = ['min', 'max'] if schema_class == Int else ['min_length', 'max_length']
        range_args = {k: schema_details[v] for k, v in zip(['min', 'max'], range_vars) if schema_details.get(v)}
        if range_args:
            obj.validators.append(Range(**range_args))

        if schema_class == Str:
            if 'valid_chars' in schema_details:
                obj.validators.append(Match(schema_details['valid_chars']))

    if schema_class == List:
        obj.items = [get_schema(i) for i in schema_details['items']]

    return obj
