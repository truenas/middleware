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
        raise TypeError(f'{str_in}: not a string')

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
            # Each branch in the OR list must be a single filter: ['field', 'op', 'value']
            or_filter = []
            for branch in f[FL_OFFSET_OR_DATA]:
                # Branch is a single filter - wrap, process, unwrap
                new_filter = query_filters_json_path_parse([branch])
                or_filter.append(new_filter[0])

            out.append(['OR', or_filter])
            continue

        elif len(f) != FL_LEN_DEF:
            raise ValueError(f'{f}: invalid filter format')

        # format: [<left field>, <operator>, <right field>]
        try:
            new_filter = f.copy()
            op = f[FL_OFFSET_OP]
            # Handle reverse operators (those starting with r except rin)
            # rin is "reverse in" but used as contains, so treat it as normal operator
            field_offset = FL_OFFSET_R if (op.startswith('r') and op != 'rin') else FL_OFFSET_L
            to_convert = f[field_offset]
        except (ValueError, AttributeError):
            raise ValueError(f"{f}: invalid filter format")

        if isinstance(to_convert, str):
            new_filter[field_offset] = dot_notation_to_json_path(to_convert)

        out.append(new_filter)

    return out


def json_path_parse(str_in: str) -> tuple[str, str]:
    """Convert a JSONPath string for datastore query into column name and JSONPath relative
    to the column. This is required in datastore plugins FiltersMixin.

    Examples:
        '$.service_data.origin' -> ('service_data', '$.origin')
        '$.event_data.params[0].username' -> ('event_data', '$.params[0].username')
        '$.roles[0]' -> ('roles', '$[0]')
        '$.roles' -> ('roles', '$')
    """
    if not str_in.startswith(JSON_PATH_PREFIX):
        raise ValueError(f'{str_in}: not a JSONPath')

    remainder = str_in[len(JSON_PATH_PREFIX):]  # Remove "$."

    # Find the first delimiter (either '.' or '[')
    dot_pos = remainder.find(JSON_PATH_DOT_SEGMENT)
    bracket_pos = remainder.find('[')

    if dot_pos == -1 and bracket_pos == -1:
        # Just a column name like "$.roles" -> ('roles', '$')
        return remainder, JSON_PATH_ROOT_NODE_ID
    elif dot_pos == -1:
        # Only bracket found like "$.roles[0]" -> ('roles', '$[0]')
        column = remainder[:bracket_pos]
        relative_path = JSON_PATH_ROOT_NODE_ID + remainder[bracket_pos:]
        return column, relative_path
    elif bracket_pos == -1 or dot_pos < bracket_pos:
        # Dot comes first like "$.service_data.origin" -> ('service_data', '$.origin')
        column, rest = remainder.split(JSON_PATH_DOT_SEGMENT, 1)
        return column, JSON_PATH_PREFIX + rest
    else:
        # Bracket comes first like "$.foo[0].bar" -> ('foo', '$[0].bar')
        column = remainder[:bracket_pos]
        relative_path = JSON_PATH_ROOT_NODE_ID + remainder[bracket_pos:]
        return column, relative_path


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
                    f'{parsed}: SELECT cannot be a JSONPath. If you want to extract '
                    'JSON data from a field, it must be done in a way to assign a new '
                    'label to the extracted data rather than building a new JSON object.'
                    'For example: {"select": [["user.email", "email"]]}'
                )

            out.append(parsed)

    return out
