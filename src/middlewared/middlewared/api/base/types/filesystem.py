from pydantic.functional_validators import AfterValidator
from typing_extensions import Annotated

__all__ = ["UnixPerm", ]


def validate_unix_perm(value: str) -> str:
    try:
        mode = int(value, 8)
    except ValueError:
        raise ValueError('Not a valid integer. Must be between 000 and 777')

    if mode & 0o777 != mode:
        raise ValueError('Please supply a value between 000 and 777')

    return value


UnixPerm = Annotated[str, AfterValidator(validate_unix_perm)]
