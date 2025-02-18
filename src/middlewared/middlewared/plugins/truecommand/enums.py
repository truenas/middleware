import enum


class PortalResponseState(enum.Enum):
    ACTIVE = 'ACTIVE'
    FAILED = 'FAILED'  # This is not given by the API but is our internal check
    PENDING = 'PENDING'
    UNKNOWN = 'UNKNOWN'
