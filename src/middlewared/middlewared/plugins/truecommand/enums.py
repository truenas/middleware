import enum


class Status(enum.Enum):
    CONNECTED = 'CONNECTED'
    CONNECTING = 'CONNECTING'
    DISABLED = 'DISABLED'
    FAILED = 'FAILED'


class StatusReason(enum.Enum):
    CONNECTED = 'Truecommand service is connected.'
    CONNECTING = 'Pending Confirmation From iX Portal for Truecommand API Key.'
    DISABLED = 'Truecommand service is disabled.'
    FAILED = 'Truecommand API Key Disabled by iX Portal.'


class PortalResponseState(enum.Enum):
    ACTIVE = 'ACTIVE'
    FAILED = 'FAILED'  # This is not given by the API but is our internal check
    PENDING = 'PENDING'
    UNKNOWN = 'UNKNOWN'
