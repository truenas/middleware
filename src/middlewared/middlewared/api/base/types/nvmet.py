import re
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, Field

__all__ = [
    "NQN"
]

MIN_NQN_LEN = 11
MAX_NQN_LEN = 223

NVMET_NQN_UUID_PREFIX = "nqn.2014-08.org.nvmexpress:uuid:"
NVMET_NQN_UUID_PREFIX_LEN = 32
NVMET_DISCOVERY_NQN = "nqn.2014-08.org.nvmexpress.discovery"
UUID_STRING_LEN = 36
NVMET_NQN_UUID_LEN = NVMET_NQN_UUID_PREFIX_LEN + UUID_STRING_LEN

NQN_DATE_PATTERN = re.compile(r"^nqn.\d{4}-\d{2}\..*")
DOMAIN_PATTERN = re.compile(r'^((?!-)[A-Za-z0-9-]{1,63}(?<!-)\.)+[A-Za-z]{2,}$')


def _validate_nqn(nqn: str):
    if nqn == NVMET_DISCOVERY_NQN:
        return nqn
    elif nqn.startswith(NVMET_NQN_UUID_PREFIX):
        # Check for "nqn.2014-08.org.nvmexpress:uuid:11111111-2222-3333-4444-555555555555"
        if len(nqn) != NVMET_NQN_UUID_LEN:
            raise ValueError(f'{nqn}: uuid is incorrect length')
        UUID(nqn[NVMET_NQN_UUID_PREFIX_LEN:])
    elif nqn.startswith("nqn."):
        # Check for "nqn.yyyy-mm.reverse.domain:user-string"
        if not NQN_DATE_PATTERN.match(nqn):
            raise ValueError(f'{nqn}: must start with "nqn.YYYY-MM.<reverse.domain>"')
        # Now check the domain
        if not nqn[12:] or '.' not in nqn[12:]:
            raise ValueError(f'{nqn}: must start with "nqn.YYYY-MM.<reverse.domain>" - domain missing')
        reverse_domain = nqn[12:].split(':', 1)[0]
        domain_parts = reverse_domain.split('.')
        domain_parts.reverse()
        if not DOMAIN_PATTERN.match('.'.join(domain_parts)):
            raise ValueError(f'{nqn}: domain does not appear to be valid')
    else:
        raise ValueError(f'{nqn}: must start with "nqn"')
    return nqn


NQN = Annotated[str, Field(min_length=MIN_NQN_LEN, max_length=MAX_NQN_LEN), AfterValidator(_validate_nqn)]
