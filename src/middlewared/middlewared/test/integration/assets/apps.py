import contextlib

from middlewared.test.integration.utils import call


@contextlib.contextmanager
def app(app_name: str, create_payload: dict, delete_payload: dict | None = None):
    create_payload = create_payload | {'app_name': app_name}
    app_info = call('app.create', create_payload, job=True)
    try:
        yield app_info
    finally:
        call('app.delete', app_name, delete_payload or {}, job=True)
