"""
Basic parsing functions related to JSONPath specification (RFC9535)

This is a very minor subset of the functionality located there as supported by json_extract() function in sqlite3.
Currently the conversion from middleware dot notation is trivial, but there may be requirement in future to
implement more functionality
"""
import re
from json import dumps

JSON_PATH_ROOT_NODE_ID = '$'
JSON_PATH_DOT_SEGMENT = '.'
JSON_PATH_PREFIX = JSON_PATH_ROOT_NODE_ID + JSON_PATH_DOT_SEGMENT
JSON_PATH_DESCENDENT_SEGMENT = '..'
JSON_PATH_WILDCARD_SELECTOR = '*'

FL_LEN_OR = 2
FL_LEN_DEF = 3
FL_OFFSET_OR_DATA = 1
FL_OFFSET_L = 0
FL_OFFSET_OP = 1
FL_OFFSET_R = 2
FL_ESCAPE_CHAR = '\\'

RE_JSON_PATH_FIELD = re.compile(r'\["([^"]+)"\](.*)')


def __escape_field_name(str_in: str) -> str:
    # use json.dumps to escape the quotes / backslashes
    s = dumps(str_in)[1:-1]
    # manually escape brackets
    s = s.replace('[', '\\[').replace(']', '\\]')

    return s


def dot_notation_to_json_path(str_in: str) -> str:
    """ Convert middleware filter dot-notation to a JSONPath string.
    For example: 'foo.bar' -> '$.foo.bar' """

    if not JSON_PATH_DOT_SEGMENT in str_in:
        # No dot notation and so short-circuit
        return str_in

    return JSON_PATH_PREFIX + str_in


def query_filters_json_path_parse(filters_in: list) -> list:
    """ This function validates the query-filters passed in and converts the filter_list style
    dot notation for dictionary elements into JSONPath notation to be used for SQL Alchemy
    query """
    out = []

    for f in filters_in:
        if len(f) == FL_LEN_OR:
            # format: ["OR", [<filter>, <filter>, ...]]
            or_filter = []
            for branch in f[FL_OFFSET_OR_DATA]:
                new_filter = query_filters_json_path_parse(branch)
                or_filter.append(new_filter)

            out.append(['OR', or_filter])
            continue

        elif len(f) != FL_LEN_DEF:
            raise ValueError(f'{f}: invalid filter format')

        # format: [<left field>, <operator>, <right field>]
        new_filter = f.copy()
        op = f[FL_OFFSET_OP]
        field_offset = FL_OFFSET_R if op.startswith('r') else FL_OFFSET_L
        to_convert = f[field_offset]

        if isinstance(to_convert, str):
            new_filter[field_offset] = dot_notation_to_json_path(to_convert)

        out.append(new_filter)

    return out


def json_path_parse(str_in: str) -> tuple[str, str]:
    """Convert a JSONPath string for datastore query into column name and JSONPath relative
    to the column. This is required in datastore plugins FiltersMixing.
    Example: '$.service_data.origin' -> ('service_data', '$.origin')"""

    if not str_in.startswith(JSON_PATH_PREFIX):
        raise ValueError(f'{str_in}: not a JSONPath')


    column, relative_path = str_in[len(JSON_PATH_PREFIX):].split('.', 1)
    return (column, JSON_PATH_PREFIX + relative_path)
