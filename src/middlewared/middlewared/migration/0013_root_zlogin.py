import os


def migrate(middleware):
    try:
        os.unlink("/root/.zlogin")
    except FileNotFoundError:
        pass
    except Exception:
        middleware.logger.warning("Unexpected error removing .zlogin", exc_info=True)
