from typing import Iterable

MAX_LIMIT = 10000  # Sanity check for rows requested by auditing

_SelectList = Iterable[str | list[str]]


def validate_select(select: _SelectList) -> None:
    """Validate that select parameters are properly formatted strings or field mapping lists."""
    for s in select:
        if isinstance(s, str):
            continue

        if isinstance(s, list):
            if len(s) != 2:
                raise ValueError(
                    f'{s}: A select as list may only contain two parameters: the name '
                    'of the parameter being selected, and the name to which to assign it '
                    'in resulting data.'
                )

            for idx, selector in enumerate(s):
                if isinstance(selector, str):
                    continue

                raise ValueError(
                    f'{s}: {"first" if idx == 0 else "second"} item must be a string.'
                )

            continue

        raise ValueError(
            f'{s}: selectors must be either a parameter name as a string or '
            'a list containing two items [<parameter name>, <as name>] to emulate '
            'SELECT <parameter name> AS <as name>.'
        )


def validate_order_by(order_by: Iterable[str]) -> None:
    """Validate that order_by parameters are all strings."""
    for idx, o in enumerate(order_by):
        if isinstance(o, str):
            continue

        raise ValueError(
            f'{order_by}: parameter at index {idx} [{o}] is not a string.'
        )


def validate_options(options: dict | None) -> tuple[dict, _SelectList, Iterable[str]]:
    """Validate and extract query options including select fields and ordering."""
    if options is None:
        return {}, [], []

    if options.get('get') and options.get('limit', 0) > 1:
        raise ValueError(
            'Invalid options combination. `get` implies a single result.'
        )

    if options.get('get') and options.get('offset'):
        raise ValueError(
            'Invalid options combination. `get` implies a single result.'
        )

    if options.get('limit', 0) > MAX_LIMIT:
        raise ValueError(f'Options limit must be between 1 and {MAX_LIMIT}')

    select = options.get('select', [])
    validate_select(select)
    order_by = options.get('order_by', [])
    validate_order_by(order_by)

    return options, select, order_by
