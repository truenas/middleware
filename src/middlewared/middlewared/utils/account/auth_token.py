from dataclasses import dataclass
from enum import StrEnum
from middlewared.auth import SessionManagerCredentials, TokenSessionManagerCredentials
from middlewared.utils.crypto import generate_token
from middlewared.utils.origin import ConnectionOrigin
from time import monotonic


class Token:
    def __init__(
        self,
        manager: 'TokenManager',
        token: str,
        ttl: int,
        attributes: dict,
        match_origin: ConnectionOrigin,
        parent_credentials: SessionManagerCredentials,
        session_id: str,
        single_use: bool
    ):
        self.manager = manager
        self.token = token
        self.ttl = ttl
        self.attributes = attributes
        self.match_origin = match_origin
        self.parent_credentials = parent_credentials
        self.session_ids = {session_id}
        self.single_use = single_use

        self.last_used_at = monotonic()

    def is_valid(self) -> bool:
        """ Returns boolean value indicating whether token has expired """
        return monotonic() < self.last_used_at + self.ttl

    def notify_used(self) -> None:
        """ Bump up last used time for the token so that ot prolongs lifespan """
        self.last_used_at = monotonic()

    def root_credentials(self) -> SessionManagerCredentials | None:
        """ Get the root credentials for the token. This root credentials are used
        for method call authorization. """
        credentials = self.parent_credentials
        while True:
            if isinstance(credentials, TokenSessionManagerCredentials):
                credentials = credentials.token.parent_credentials
            elif credentials is None:
                return None
            else:
                return credentials


class TokenResult(StrEnum):
    SUCCESS = 'SUCCESS'
    EXPIRED = 'EXPIRED'
    NO_ENTRY = 'NO_ENTRY'
    ORIGIN_MATCH_FAILED = 'ORIGIN_MATCH_FAILED'


@dataclass(slots=True, frozen=True)
class TokenManagerResponse:
    result: TokenResult
    token: Token | None


class TokenManager:
    def __init__(self):
        self.tokens = {}

    def create(
        self,
        ttl: int,
        attributes: dict,
        match_origin: ConnectionOrigin | None,
        parent_credentials: SessionManagerCredentials,
        session_id: str,
        single_use: bool
    ) -> TokenManagerResponse:
        """ Create a new authentication token based on the specific credentials

        Params:
        -------
        ttl: inactivity ttl for the auth token. After this number of seconds of inactivity the token expires.

        attributes: dictionary containing token-related attributes. Used by backend for tokens generated for
        specific single purposes.

        match_origin: ConnectionOrigin object to be used for origin matching on subsequent token usage. If
        None then origin matching will not be performed.

        parent_credentials: SessionManagerCredentials specifying the account details to tie in to the token

        session_id: the middleware session ID to which the authentication token is linked. This is used
        to allow destroying tokens by session ID during cleanup on session teardown.

        single_use: specifies whether the token can be reused. For security purposes to prevent replay attacks
        most tokens are single-use.

        Returns:
        --------
        TokenManagerResponse
        """
        credentials = parent_credentials
        if isinstance(credentials, TokenSessionManagerCredentials):
            if root_credentials := credentials.token.root_credentials():
                credentials = root_credentials

        token = generate_token(48, url_safe=True)
        self.tokens[token] = Token(self, token, ttl, attributes, match_origin, credentials, session_id, single_use)
        return TokenManagerResponse(TokenResult.SUCCESS, self.tokens[token])

    def get(self, token: str, origin: ConnectionOrigin) -> TokenManagerResponse:
        """ Retrieve a token from the token manager by string identifier that is returned to API consumers. """
        token = self.tokens.get(token)
        if token is None:
            return TokenManagerResponse(TokenResult.NO_ENTRY, None)

        if not token.is_valid():
            self.tokens.pop(token.token)
            return TokenManagerResponse(TokenResult.EXPIRED, None)

        if token.match_origin:
            if not isinstance(origin, type(token.match_origin)):
                return TokenManagerResponse(TokenResult.ORIGIN_MATCH_FAILED, None)
            if not token.match_origin.match(origin):
                return TokenManagerResponse(TokenResult.ORIGIN_MATCH_FAILED, None)

        return TokenManagerResponse(TokenResult.SUCCESS, token)

    def destroy(self, token: Token) -> TokenManagerResponse:
        self.tokens.pop(token.token, None)
        return TokenManagerResponse(TokenResult.SUCCESS, None)

    def destroy_by_session_id(self, session_id: str) -> TokenManagerResponse:
        self.tokens = {k: v for k, v in self.tokens.items() if session_id not in v.session_ids}
        return TokenManagerResponse(TokenResult.SUCCESS, None)
