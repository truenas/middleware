import fnmatch
import re

from middlewared.api.current import HttpVerb, NonEmptyString

ALLOW_LIST_FULL_ADMIN = {'method': '*', 'resource': '*'}


class Allowlist:
    def __init__(self, allowlist: list[dict]):
        self.exact: dict[HttpVerb, set[NonEmptyString]] = {}
        self.full_admin = ALLOW_LIST_FULL_ADMIN in allowlist
        self.patterns: dict[HttpVerb, list[re.Pattern]] = {}
        for entry in allowlist:
            method = entry["method"]
            resource = entry["resource"]
            if "*" in resource:
                self.patterns.setdefault(method, [])
                self.patterns[method].append(re.compile(fnmatch.translate(resource)))
            else:
                self.exact.setdefault(method, set())
                self.exact[method].add(resource)

    def authorize(self, method: HttpVerb, resource: NonEmptyString):
        return self._authorize_internal("*", resource) or self._authorize_internal(method, resource)

    def _authorize_internal(self, method: HttpVerb, resource: NonEmptyString):
        if (exact := self.exact.get(method)) and resource in exact:
            return True

        if patterns := self.patterns.get(method):
            if any(pattern.match(resource) for pattern in patterns):
                return True

        return False
