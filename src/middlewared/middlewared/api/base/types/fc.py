from pydantic import StringConstraints
from typing_extensions import Annotated

__all__ = ["FibreChannelHostAlias", "FibreChannelPortAlias", "WWPN"]

# Port alias will have a optional "/<number>" postfix vs host alias, where number > 0
FC_HOST_ALIAS_PATTERN = r"^[a-zA-Z0-9,\-_:]+$"
FC_PORT_ALIAS_PATTERN = r"^[a-zA-Z0-9,\-_:]+(/[1-9][0-9]*)?$"
NAA_PATTERN = r"^naa.[0-9a-fA-F]{16}$"


FibreChannelHostAlias = Annotated[str, StringConstraints(min_length=1, max_length=32, pattern=FC_HOST_ALIAS_PATTERN)]
FibreChannelPortAlias = Annotated[str, StringConstraints(min_length=1, max_length=40, pattern=FC_PORT_ALIAS_PATTERN)]
WWPN = Annotated[str, StringConstraints(pattern=NAA_PATTERN)]
