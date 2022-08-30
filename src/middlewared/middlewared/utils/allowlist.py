import fnmatch
import re


class Allowlist:
    def __init__(self, allowlist):
        self.exact = {}
        self.patterns = {}
        for entry in allowlist:
            method = entry["method"]
            resource = entry["resource"]
            if "*" in resource:
                self.patterns.setdefault(method, [])
                self.patterns[method].append(re.compile(fnmatch.translate(resource)))
            else:
                self.exact.setdefault(method, set())
                self.exact[method].add(resource)

    def authorize(self, method, resource):
        return self._authorize_internal("*", resource) or self._authorize_internal(method, resource)

    def _authorize_internal(self, method, resource):
        if (exact := self.exact.get(method)) and resource in exact:
            return True

        if patterns := self.patterns.get(method):
            if any(pattern.match(resource) for pattern in patterns):
                return True

        return False
