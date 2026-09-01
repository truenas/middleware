import contextlib

from middlewared.test.integration.utils import mock

_DECLARATION = """
    def mock(self, feature):
        from middlewared.api.current import EntitlementEntry
        from middlewared.utils.entitlements import Reason
        from middlewared.utils.entitlements.engine import _format_message

        reason = Reason.{reason}
        return EntitlementEntry(
            entitled={entitled},
            reason=reason,
            message="" if {entitled} else _format_message(reason, feature),
        )
"""


@contextlib.contextmanager
def entitled(feature, value=True, reason=None):
    """Make `truenas.entitlements.check(feature)` answer `value` for the duration.

    Gates ask whether the system is entitled to one named feature, not what product it is.
    Reaches `call2` gates as well as `middleware.call` ones, because `get_method_by_callable`
    consults the mock registry too.
    """
    if reason is None:
        reason = "ENTITLED" if value else "NO_LICENSE"
    with mock(
        "truenas.entitlements.check",
        args=[str(feature)],
        declaration=_DECLARATION.format(entitled=value, reason=reason),
    ):
        yield
