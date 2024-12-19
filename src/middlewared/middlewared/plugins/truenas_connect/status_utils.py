import enum


class Status(enum.Enum):
    DISABLED = 'TrueNAS Connect is disabled'
    CLAIM_TOKEN_MISSING = 'Waiting for claim token to be generated'
    REGISTRATION_FINALIZATION_WAITING = 'Waiting for registration with TrueNAS Connect to complete'
    REGISTRATION_FINALIZATION_FAILED = 'Registration finalization failed'
    REGISTRATION_FINALIZATION_TIMEOUT = 'Registration finalization timed out'
    REGISTRATION_FINALIZATION_SUCCESS = 'Registration finalization successful'
    CERT_GENERATION_IN_PROGRESS = 'Certificate generation is in progress'
    CERT_GENERATION_FAILED = 'Certificate generation failed'
    CERT_GENERATION_SUCCESS = 'Certificate generation was successful'
    CERT_CONFIGURATION_FAILURE = 'Failed to configure certificate in system UI'
    CERT_RENEWAL_IN_PROGRESS = 'Certificate renewal is in progress'
    CERT_RENEWAL_FAILURE = 'Failed to renew certificate'
    CERT_RENEWAL_SUCCESS = 'Certificate renewal was successful'
    CONFIGURED = 'TrueNAS Connect is configured'
