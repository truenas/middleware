NOT_PROVIDED = object()
REDACTED_VALUE = "********"

MS_RESERVED_WORDS = {
    'ANONYMOUS'.casefold(),
    'AUTHENTICATED USER'.casefold(),
    'BATCH'.casefold(),
    'BUILTIN'.casefold(),
    'DIALUP'.casefold(),
    'DOMAIN'.casefold(),
    'ENTERPRISE'.casefold(),
    'INTERACTIVE'.casefold(),
    'INTERNET'.casefold(),
    'LOCAL'.casefold(),
    'NETWORK'.casefold(),
    'NULL'.casefold(),
    'PROXY'.casefold(),
    'RESTRICTED'.casefold(),
    'SELF'.casefold(),
    'SERVER'.casefold(),
    'USERS'.casefold(),
    'WORLD'.casefold()
}

RFC_852_RESERVED_WORDS = {
    'GATEWAY'.casefold(),
    'GW'.casefold(),
    'TAC'.casefold(),
}

RESERVED_WORDS = MS_RESERVED_WORDS | RFC_852_RESERVED_WORDS
