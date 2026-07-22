import base64
import contextlib
import time

from middlewared.test.integration.assets.crypto import generate_self_signed_pem
from middlewared.test.integration.utils import call, ssh

__all__ = ["KMIP_HOST", "KMIP_PORT", "kmip_server", "kmip_enabled"]

# We launch PyKMIP's built-in KMIP server on the TrueNAS host itself so that the
# middleware (which always dials the server from localhost) can reach it at
# 127.0.0.1. PyKMIP ships with the middleware, so no extra packages are needed.
KMIP_HOST = "127.0.0.1"
KMIP_PORT = 5696
# Each server instance gets its own directory (keyed by port) so that several can
# run side by side, e.g. when testing a migration from one server to another.
_REMOTE_DIR = "/tmp/pykmip-test-{port}"

# PyKMIP's TLS handshake requires a client certificate (the server always sets
# ``ssl.CERT_REQUIRED``). A single self-signed certificate is used for every
# role: the KMIP server certificate/key, the CA that the middleware uses to
# verify the server, and the client certificate the middleware presents. A
# self-signed certificate validates against itself as its own chain, which keeps
# the setup simple.
_SERVER_LAUNCHER = """\
import sys
from kmip.services.server import KmipServer

d = sys.argv[1]
server = KmipServer(
    hostname="{host}",
    port={port},
    # PyKMIP's KmipServer.start() passes these to ssl.load_cert_chain swapped
    # (certfile=key_path, keyfile=certificate_path), so they are swapped here.
    certificate_path=f"{{d}}/server.key",
    key_path=f"{{d}}/server.pem",
    ca_path=f"{{d}}/ca.pem",
    # "Basic" pins TLSv1.0 with legacy ciphers that modern OpenSSL rejects; the
    # middleware defaults to PROTOCOL_TLSv1_2, so use the matching suite.
    auth_suite="TLS1.2",
    config_path=None,
    log_path=f"{{d}}/server.log",
    policy_path=None,
    enable_tls_client_auth=False,
    database_path=f"{{d}}/pykmip.db",
)
with server:
    server.serve()
"""


def _write_remote_file(path, contents):
    encoded = base64.b64encode(contents.encode()).decode()
    call("filesystem.file_receive", path, encoded, {})


@contextlib.contextmanager
def kmip_server(port=KMIP_PORT, certificate=None):
    """Launch PyKMIP's built-in KMIP server on the TrueNAS host.

    Yields a dict with the ``cert`` and ``key`` PEMs the server uses. The same
    certificate can be imported into the middleware (e.g. via
    ``middlewared.test.integration.assets.crypto.imported_certificate``) and used as
    both the KMIP client certificate and certificate authority. Pass ``certificate``
    as a ``(cert_pem, key_pem)`` tuple to reuse existing material, which is what lets
    two servers share the certificate authority the middleware is configured with.
    """
    # The pykmip client does not verify the server hostname, so a plain self-signed
    # certificate works for every role here.
    cert_pem, key_pem = certificate or generate_self_signed_pem(common_name=KMIP_HOST)
    launcher = _SERVER_LAUNCHER.format(host=KMIP_HOST, port=port)
    remote_dir = _REMOTE_DIR.format(port=port)

    ssh(f"rm -rf {remote_dir}")
    _write_remote_file(f"{remote_dir}/ca.pem", cert_pem)
    _write_remote_file(f"{remote_dir}/server.pem", cert_pem)
    _write_remote_file(f"{remote_dir}/server.key", key_pem)
    _write_remote_file(f"{remote_dir}/launch.py", launcher)

    # nohup exec's into python, so ``$!`` is the server's PID. Detach stdin so the
    # ssh channel closes immediately instead of waiting on the backgrounded process.
    pid = ssh(
        f"nohup python3 {remote_dir}/launch.py {remote_dir} < /dev/null > {remote_dir}/nohup.out 2>&1 & echo $!"
    ).strip()
    try:
        # Wait for the server to start listening on the KMIP port.
        for _ in range(30):
            listening = ssh(f"ss -tlnH 'sport = :{port}' || true", check=False)
            if f":{port}" in listening:
                break
            time.sleep(1)
        else:
            log = ssh(f"cat {remote_dir}/server.log {remote_dir}/nohup.out || true", check=False)
            raise AssertionError(f"PyKMIP server did not start listening on port {port}:\n{log}")

        yield {"cert": cert_pem, "key": key_pem, "port": port}
    finally:
        ssh(f"kill {pid} 2>/dev/null || true", check=False)
        ssh(f"rm -rf {remote_dir}", check=False)


def _wait_for_sync_settled(timeout=60):
    """Best-effort wait until no KMIP keys are pending sync.

    ``kmip.update`` starts the per-key-type sync jobs without waiting for them, so a key
    can still be pending for a short while after an update returns. ``kmip.update`` also
    refuses to flip ``enabled`` while any key is pending sync, so the teardown below has
    to let those background jobs drain first. This never raises: leftover pending state is
    a caller problem the test's own assertions should have caught, and the teardown clears
    whatever remains with ``force_clear`` regardless.
    """
    deadline = time.monotonic() + timeout
    while call("kmip.kmip_sync_pending"):
        if time.monotonic() >= deadline:
            return False
        time.sleep(1)
    return True


@contextlib.contextmanager
def kmip_enabled(cert_id, *, server=KMIP_HOST, port=KMIP_PORT, **overrides):
    """Enable the KMIP service pointed at ``server``:``port`` and disable it on exit.

    ``cert_id`` is used as both the client certificate and the certificate authority.
    Extra keyword arguments override individual ``kmip.update`` fields.
    """
    payload = {
        "enabled": True,
        "server": server,
        "port": port,
        "certificate": cert_id,
        "certificate_authority": cert_id,
        "manage_zfs_keys": False,
        "manage_sed_disks": False,
        **overrides,
    }
    try:
        yield call("kmip.update", payload, job=True)
    finally:
        # Let any in-flight sync jobs started inside the block settle before flipping
        # `enabled`, which is otherwise rejected while keys are pending sync. `force_clear`
        # is a safety net for the small window between this drain and the update.
        _wait_for_sync_settled()
        call(
            "kmip.update",
            {
                "enabled": False,
                "server": None,
                "certificate": None,
                "certificate_authority": None,
                "manage_zfs_keys": False,
                "manage_sed_disks": False,
                "force_clear": True,
                "validate": False,
            },
            job=True,
        )
        # Disabling triggers a final pull back into the database; drain it too so the next
        # test starts from a clean, fully-synced slate.
        _wait_for_sync_settled()
