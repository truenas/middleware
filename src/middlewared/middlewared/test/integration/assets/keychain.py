import contextlib
import uuid

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.utils import call


@contextlib.contextmanager
def ssh_keypair():
    keypair = call("keychaincredential.create", {
        "name": str(uuid.uuid4()),
        "type": "SSH_KEY_PAIR",
        "attributes": call("keychaincredential.generate_ssh_key_pair"),
    })

    try:
        yield keypair
    finally:
        with contextlib.suppress(InstanceNotFound):
            call("keychaincredential.delete", keypair["id"])


@contextlib.contextmanager
def localhost_ssh_credentials(**data):
    with ssh_keypair() as keypair:
        credentials = call("keychaincredential.remote_ssh_semiautomatic_setup", {
            "name": str(uuid.uuid4()),
            "url": "http://localhost",
            "token": call("auth.generate_token"),
            "private_key": keypair["id"],
            **data,
        })

        try:
            yield {
                "keypair": keypair,
                "credentials": credentials,
            }
        finally:
            with contextlib.suppress(InstanceNotFound):
                call("keychaincredential.delete", credentials["id"])
