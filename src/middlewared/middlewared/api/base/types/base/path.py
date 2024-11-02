from pathlib import Path
from typing import Any

from pydantic_core import core_schema, CoreSchema


__all__ = ['FilePath', 'HostPath']


class HostPath(str):

    @classmethod
    def __get_validators__(cls):
        yield cls.validate_path

    @classmethod
    def validate_path(cls, value):
        path = Path(value)
        if not path.exists():
            raise ValueError(f'Path does not exist (underlying dataset may be locked or the path is just missing).')
        return str(value)

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> CoreSchema:
        # Define a core schema that treats this as a string in JSON while applying validation
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.no_info_after_validator_function(
                cls.validate_path,
                core_schema.str_schema(),
            ),
        )


class FilePath(HostPath):

    @classmethod
    def validate_path(cls, value):
        path = Path(value)
        if not path.is_file():
            raise ValueError('This path is not a file.')
        return str(value)
