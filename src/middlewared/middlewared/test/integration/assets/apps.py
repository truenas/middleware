import contextlib

from middlewared.test.integration.utils import call


@contextlib.contextmanager
def create_app(app_name: str, create_payload: dict, delete_payload: dict | None = None):
    create_payload = create_payload | {'app_name': app_name}
    app = call('app.create', create_payload, job=True)
    try:
        yield app
    finally:
        call('app.delete', app_name, delete_payload or {}, job=True)
