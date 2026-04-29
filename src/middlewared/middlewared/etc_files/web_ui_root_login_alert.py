from middlewared.alert.source.web_ui_root_login import WebUiRootLoginAlert
from middlewared.utils.filter_list import filter_list


async def render(service, middleware, render_ctx):
    root_user = filter_list(render_ctx["user.query"], [("username", "=", "root")], {"get": True})

    if root_user["password_disabled"] and await middleware.call(
        "privilege.always_has_root_password_enabled",
        render_ctx["user.query"],
        render_ctx["group.query"],
    ):
        await middleware.call2(middleware.services.alert.oneshot_create, WebUiRootLoginAlert())
    else:
        await middleware.call2(middleware.services.alert.oneshot_delete, "WebUiRootLogin", None)
