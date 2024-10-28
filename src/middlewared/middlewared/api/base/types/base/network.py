from typing import Annotated

from pydantic import BeforeValidator, IPvAnyNetwork as PydanticIPvAnyNetwork, PlainSerializer


def validate_ip_subnet(value: str) -> str:
    # Ensure the input is a string
    if not isinstance(value, str):
        raise TypeError('Value must be a string in IP/subnet format, e.g., "192.168.0.0/24"')
    # Check if the input contains a '/'
    if '/' not in value:
        raise ValueError('Value must include a subnet mask in IP/subnet format, e.g., "192.168.0.0/24"')
    return value


IPvAnyNetwork = Annotated[
    PydanticIPvAnyNetwork,
    BeforeValidator(validate_ip_subnet),
    PlainSerializer(lambda x: str(x), when_used='always')
]
