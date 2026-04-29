from typing import Any, TextIO, TypeVar, overload

import yaml

T = TypeVar("T")


@overload
def safe_yaml_load(stream: str | TextIO) -> Any: ...
@overload
def safe_yaml_load(stream: str | TextIO, expected_type: type[T]) -> T: ...


def safe_yaml_load(stream: str | TextIO, expected_type: type | None = None) -> Any:
    """
    Helper function to safely load YAML data using CSafeLoader.

    CSafeLoader is functionally identical to SafeLoader but uses a C implementation
    which is significantly faster and releases the GIL during parsing. This is
    particularly important in multi-threaded environments where python-native YAML
    parsing can cause GIL contention and starve the asyncio event loop.

    Args:
        stream: A string or file-like object containing YAML data
        expected_type: Optional type that the loaded value must be an instance of.
            When supplied, ``ValueError`` is raised if the parsed value is not an
            instance of ``expected_type``. Note that an empty YAML stream yields
            ``None``, so callers that want to tolerate empty input must either
            leave ``expected_type`` unset or catch ``ValueError``.

    Returns:
        The parsed YAML data structure (dict, list, str, etc.)
    """
    data = yaml.load(stream, Loader=yaml.CSafeLoader)
    if expected_type is not None and not isinstance(data, expected_type):
        raise ValueError(
            f"Expected {expected_type.__name__} from YAML, got {type(data).__name__}"
        )
    return data
