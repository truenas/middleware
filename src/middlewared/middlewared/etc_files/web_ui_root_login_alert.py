from typing import TYPE_CHECKING

from middlewared.alert.source.web_ui_root_login import WebUiRootLoginAlert
if TYPE_CHECKING:
    from middlewared.main import Middleware


async def render(service, middleware: 'Middleware', render_ctx):
    root_user = next(u for u in render_ctx['user.query'] if u['username'] == 'root')

    if root_user['password_disabled'] and await middleware.call(
        'privilege.always_has_root_password_enabled',
        render_ctx['user.query'],
        render_ctx['group.query'],
    ):
        await middleware.call2(middleware.services.alert.oneshot_create, WebUiRootLoginAlert())
    else:
        await middleware.call2(middleware.services.alert.oneshot_delete, 'WebUiRootLogin', None)
