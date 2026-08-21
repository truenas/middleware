from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from middlewared.api.base.handler.full_admin import full_admin_fields, full_admin_payload_fields
from middlewared.service_exception import ValidationErrors
from middlewared.utils.privilege import app_needs_full_admin_check, check_full_admin_fields

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App

__all__ = ["check_full_admin_model", "check_full_admin_payload"]


async def check_full_admin_payload(
    app: "App | None",
    methodobj: Any,
    data: Any,
    get_old: Callable[[], Awaitable[Any]] | None,
) -> None:
    """Reject any `FullAdmin` field that `data` mutates, unless `app` holds `FULL_ADMIN`.

    This is the single enforcement point for `FullAdmin`. `CRUDService` and `ConfigService` funnel every public
    create and update through it before the plugin's own `do_create` / `do_update` runs, so marking a field in the
    API model is all a plugin has to do. A method that does not route through those wrappers has to call this
    itself; `middlewared.pytest.unit.api.test_full_admin_coverage` fails if one forgets.

    :param app: the calling application, or `None` for an internal call.
    :param methodobj: the `do_create` / `do_update` that will receive `data`.
    :param data: the payload as the caller supplied it.
    :param get_old: returns the currently stored entry. Only called when there is something to check, since it
        usually costs a query. `None` when nothing is stored yet (i.e. on create).
    """
    if not app_needs_full_admin_check(app):
        return

    if (accepts := getattr(methodobj, "new_style_accepts", None)) is None:
        return

    schema_name, fields = full_admin_payload_fields(accepts)
    if not fields:
        return

    old = await get_old() if get_old is not None else None
    if old is not None and hasattr(old, "model_dump"):
        # A `generic` service hands back the entry model rather than a dict. Dump it so that its values compare
        # equal to the raw ones in `data` (in particular, so that `Secret` fields yield what they wrap).
        old = old.model_dump(context={"expose_secrets": True}, warnings=False, by_alias=True)

    verrors = ValidationErrors()
    check_full_admin_fields(schema_name, fields, data, old, verrors)
    verrors.check()


def check_full_admin_model(app: "App | None", schema_name: str, model: Any, data: Any) -> None:
    """Reject any `FullAdmin` field of `model` that `data` sets to something other than its default.

    For a method that accepts an entry-shaped payload without storing one, so that there is no previous value to
    compare against and any non-default value is a change. `check_full_admin_payload` covers the CRUD and config
    methods that do store one.

    :param app: the calling application, or `None` for an internal call.
    :param schema_name: name of the payload parameter, prefixed to the attribute of each error.
    :param model: the payload's API model.
    :param data: the payload, as a mapping or as a validated model instance.
    """
    if not app_needs_full_admin_check(app):
        return

    if not (fields := full_admin_fields(model)):
        return

    verrors = ValidationErrors()
    check_full_admin_fields(schema_name, fields, data, None, verrors)
    verrors.check()
