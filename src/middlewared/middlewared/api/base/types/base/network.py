from typing import Annotated, Any, Type

from pydantic import BeforeValidator, GetCoreSchemaHandler, IPvAnyNetwork as PydanticIPvAnyNetwork, PlainSerializer
from pydantic_core import CoreSchema, core_schema

from middlewared.schema.processor import clean_and_validate_arg
from middlewared.schema.string_schema import IPAddr as IPAddrSchema
from middlewared.service_exception import ValidationErrors


def IPAddr(
    cidr: bool = False, network: bool = False, v4: bool = True, v6: bool = True,
    network_strict: bool = False, excluded_address_types: list[str] | None = None,
    allow_zone_index: bool = False,
) -> Type:
    class CustomIPAddr:
        def __init__(self, value: str):
            if not isinstance(value, str):
                raise ValueError('The input must be a string.')
            self.attr = IPAddrSchema(
                cidr=cidr, network=network, v4=v4, v6=v6, network_strict=network_strict,
                excluded_address_types=excluded_address_types, allow_zone_index=allow_zone_index,
            )
            verrors = ValidationErrors()
            self.value = clean_and_validate_arg(verrors, self.attr, value)
            if verrors:
                raise ValueError(str(verrors))

        def __str__(self):
            return str(self.value)

        def __repr__(self):
            return f'IPAddr({str(self.value)})'

        @classmethod
        def __get_pydantic_core_schema__(
                cls, source_type: Any, handler: GetCoreSchemaHandler
        ) -> CoreSchema:
            schema = core_schema.no_info_after_validator_function(
                cls,
                core_schema.str_schema(),
            )
            schema['serialization'] = core_schema.plain_serializer_function_ser_schema(
                lambda x: str(x),
                info_arg=False,
            )
            return schema

    CustomIPAddr.__name__ = f'IPAddr(cidr={cidr}, network={network}, v4={v4}, v6={v6})'
    return CustomIPAddr


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
