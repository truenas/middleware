import os

from typing import Annotated

from pydantic.functional_validators import AfterValidator
from .string import NonEmptyString

__all__ = ["UnixPerm", "NormalPath"]


def validate_unix_perm(value: str) -> str:
    try:
        mode = int(value, 8)
    except ValueError:
        raise ValueError('Not a valid integer. Must be between 000 and 777')

    if mode & 0o777 != mode:
        raise ValueError('Please supply a value between 000 and 777')

    return value


def normalize_path(value) -> str:
    return os.path.normpath(value)


UnixPerm = Annotated[str, AfterValidator(validate_unix_perm)]
NormalPath = Annotated[NonEmptyString, AfterValidator(normalize_path)]
