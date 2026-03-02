from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from middlewared.main import Middleware


async def migrate(middleware: 'Middleware'):
    await middleware.call2(middleware.services.catalog.update_train_for_enterprise)
