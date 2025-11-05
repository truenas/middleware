"""
Basic parsing functions related to JSONPath specification (RFC9535)

This is a very minor subset of the functionality located there as supported by json_extract() function in sqlite3.
Currently the conversion from middleware dot notation is trivial, but there may be requirement in future to
implement more functionality

NOTE: although the JSONPath RFC describes multiple notation formats such as $.["foo"]["bar"]' and $.foo.bar,
we are limited here by what is supported by JSON1 in sqlite. Any changes or expansion of functionality here
will need to be validated against what is supported by the library: https://sqlite.org/json1.html
"""
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

FL_SELECT_AS_SRC_OFF = 0
FL_SELECT_AS_DST_OFF = 1


def __escape_field_name(str_in: str) -> str:
    # use json.dumps to escape the quotes / backslashes
    s = dumps(str_in)[1:-1]
    # manually escape brackets
    s = s.replace('[', f'{FL_ESCAPE_CHAR}[').replace(']', f'{FL_ESCAPE_CHAR}]')

    return s


def dot_notation_to_json_path(str_in: str) -> str:
    """ Convert middleware filter dot-notation to a JSONPath string.
    For example: 'foo.bar' -> '$.foo.bar' """
    if not isinstance(str_in, str):
        raise TypeError(f'{str_in}: not a stirng')

    if JSON_PATH_DOT_SEGMENT not in str_in:
        # No dot notation and so short-circuit
        return str_in

    if str_in.startswith(JSON_PATH_DOT_SEGMENT):
        # This is already a JSONPath (possibly provided by API user) and so
        # we'll just pass it along.
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


def query_select_json_path_parse(select_in: list) -> list:
    """ Convert select query-options into JSONPath syntax. This allows picking out
    fields from JSON data returned and assigning them as new fields. E.g.:

    SELECT
      data.id,
      json_extract(data.payload, '$.user.name') AS username,
      json_extract(data.payload, '$.user.email') AS email,
      json_extract(data.payload, '$.metadata.last_login') AS last_login
    FROM data;
    """
    out = []
    if not select_in:
        return out

    for sel in select_in:
        if isinstance(sel, (list, tuple)):
            if len(sel) != 2:
                raise ValueError(f'{sel}: unexpected select option')

            parsed_src = dot_notation_to_json_path(sel[FL_SELECT_AS_SRC_OFF])
            parsed_dst = dot_notation_to_json_path(sel[FL_SELECT_AS_DST_OFF])
            if parsed_dst.startswith(JSON_PATH_PREFIX):
                raise ValueError(f'{parsed_dst}: SELECT AS label cannot be a JSONPath')

            out.append([parsed_src, parsed_dst])

        else:
            parsed = dot_notation_to_json_path(sel)
            if parsed.startswith(JSON_PATH_PREFIX):
                # Although there's possibly a legitimate use case for pruning out
                # unnecessary JSON from complex nested JSON objects, dynamically building
                # out the syntax for this (which involves directing JSON1 to create new
                # JSON objects) would be quite error-prone. So raise a ValueError here.
                raise ValueError(
                    f'{parsed_dst}: SELECT cannot be a JSONPath. If you want to extract '
                    'JSON data from a field, it must be done in a way to assign a new '
                    'label to the extracted data rather than building a new JSON object.'
                    'For example: {"select": [["user.email", "email"]]}'
                )

            out.append(parsed)

    return out
