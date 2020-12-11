import enum


class Status(enum.Enum):
    CONNECTED = 'CONNECTED'
    CONNECTING = 'CONNECTING'
    DISABLED = 'DISABLED'
    FAILED = 'FAILED'

# In the database we save 3 states, CONNECTED/DISABLED/FAILED
# Connected is saved when portal has approved an api key
# Disabled is saved when TC service is disabled
# Failed is saved when portal revokes an api key
#
# We report CONNECTED to the user when we have an active wireguard
# connection with TC which is not failing a health check.
# If portal has not approved the api key yet but has registered it
# we report CONNECTING to the user.
# Connecting is also reported when wireguard connection fails health
# check


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
