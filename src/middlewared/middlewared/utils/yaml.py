from typing import Any, TextIO

import yaml


def safe_yaml_load(stream: str | TextIO) -> Any:
    """
    Helper function to safely load YAML data using CSafeLoader.

    CSafeLoader is functionally identical to SafeLoader but uses a C implementation
    which is significantly faster and releases the GIL during parsing. This is
    particularly important in multi-threaded environments where python-native YAML
    parsing can cause GIL contention and starve the asyncio event loop.

    Args:
        stream: A string or file-like object containing YAML data

    Returns:
        The parsed YAML data structure (dict, list, str, etc.)
    """
    return yaml.load(stream, Loader=yaml.CSafeLoader)
