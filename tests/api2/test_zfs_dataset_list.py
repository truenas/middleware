from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh


def test__unlocked_zvols_fast__volmode():
    with dataset("container") as container:
        ssh(f"zfs set volmode=full {container}")

        with dataset(
            "container/zvol", {"type": "VOLUME", "volsize": 100 * 1024 * 1024}
        ) as zvol:
            ssh(f"sgdisk -n 1:1MiB:2MiB /dev/zvol/{zvol}")

            call(
                "zfs.resource.unlocked_zvols_fast",
                [["name", "=", zvol]],
                {},
                ["SIZE", "RO", "DEVID", "ATTACHMENT"],
            )
