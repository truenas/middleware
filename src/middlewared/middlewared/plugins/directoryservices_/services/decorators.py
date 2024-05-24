# Decorators for directory services methods
from collections import namedtuple, defaultdict
from copy import deepcopy
from time import monotonic

cache_entry = namedtuple('TtlCacheEntry', ['value', 'timeout'])


class GenCache:
    CACHE = defaultdict(dict)

    def clean(self, ns, now):
        if (next_check := ns.get('ns_next_check')) is None:
            # remove expired keys every 5 minutes
            ns['ns_next_check'] = now + 300
            return

        if next_check > now:
            return

        for key in list(ns.keys()):
            if not isinstance((entry := ns[key]), cache_entry):
                continue

            if now > entry.timeout:
                ns.pop(key)

    def get(self, namespace, key):
        ns = self.CACHE[namespace]
        now = monotonic()
        self.clean(ns, now)

        if (entry := ns.get(key)) is None:
            return None

        if now > entry.timeout:
            return None

        return entry

    def put(self, namespace, key, entry):
        if not isinstance(entry, cache_entry):
            raise ValueError(f'{type(entry)}: Invalid type')

        ns = self.CACHE[namespace]
        ns[key] = entry


def ttl_cache(*, ttl=60, namespace='DEFAULT_NAMESPACE'):
    CACHE = GenCache()

    def get_value(fn):
        def get_value_inner(*args, **kwargs):
            nonlocal CACHE

            self = args[0]
            refresh = kwargs.pop('ttl_cache_refresh', False)
            key = f'{fn.__name__}_{hex(id(self))}'

            if not refresh:
                if (entry := CACHE.get(namespace, key)) is not None:
                    return deepcopy(entry.value)

            value = fn(*args, **kwargs)
            entry = cache_entry(value=value, timeout=monotonic() + ttl)
            CACHE.put(namespace, key, entry)
            return deepcopy(value)

        return get_value_inner

    return get_value


def active_controller(fn):
    """
    Decorator to raise a CallError if we're
    not active controller on HA (single is OK).

    _assert_is_active() is provided by the base
    directory service class.
    """
    def check_is_active(*args, **kwargs):
        self = args[0]
        self._assert_is_active()
        return fn(*args, **kwargs)

    return check_is_active


def kerberos_ticket(fn):
    """
    Decorator to raise a CallError if no ccache
    or if ticket in ccache is expired

    _assert_has_krb5_tkt() is provided by the
    kerberos mixin.
    """
    def check_ticket(*args, **kwargs):
        self = args[0]
        self._assert_has_krb5_tkt()
        return fn(*args, **kwargs)

    return check_ticket
