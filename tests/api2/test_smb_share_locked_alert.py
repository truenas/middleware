from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.alert import (
    wait_for_share_locked_alert,
    wait_for_share_locked_alert_cleared,
)


PASSPHRASE = "12345678"


def encryption_props():
    return {
        "encryption_options": {"generate_key": False, "passphrase": PASSPHRASE},
        "encryption": True,
        "inherit_encryption": False,
    }


def test_share_locked_alert_lifecycle():
    """Locking the dataset behind an SMB share raises a ShareLocked alert; the normal
    interactive unlock (toggle_attachments=True) clears it via the attachment-delegate
    start() -> remove_alert path."""
    with dataset("encrypted_smb", encryption_props()) as ds:
        with smb_share(f"/mnt/{ds}", "enc_smb_share") as share:
            share_id = share["id"]

            assert call("sharing.smb.get_instance", share_id)["locked"] is False

            # Lock the dataset -> share becomes locked and the alert is raised.
            call("pool.dataset.lock", ds, job=True)
            assert call("sharing.smb.get_instance", share_id)["locked"] is True

            alert = wait_for_share_locked_alert("SMB", share_id)
            assert alert is not None, (
                "ShareLocked alert was not created after locking dataset"
            )
            assert alert["level"] == "WARNING"

            # Interactive unlock clears the alert through the attachment-delegate path.
            call(
                "pool.dataset.unlock",
                ds,
                {
                    "datasets": [{"name": ds, "passphrase": PASSPHRASE}],
                    "recursive": True,
                },
                job=True,
            )
            assert call("sharing.smb.get_instance", share_id)["locked"] is False

            assert wait_for_share_locked_alert_cleared("SMB", share_id), (
                "ShareLocked alert was not cleared after unlocking dataset"
            )


def test_stale_locked_alert_cleared_on_smb_regen():
    """Regression guard for the boot path (the generate_smb_configuration fix).

    At boot the encrypted pool is unlocked with toggle_attachments=False, so the
    attachment-delegate path that normally clears a ShareLocked alert never runs.
    The stale alert must instead be cleared when smb.conf is regenerated (the
    post-unlock pool.post_import -> etc.generate('smb')) now that the share is no
    longer locked.

    The leftover boot state is reproduced directly: raise a ShareLocked alert for a
    share whose dataset is NOT locked, then regenerate smb.conf and assert the alert
    is gone. Reverting the generate_smb_configuration change fails this test (the
    lifecycle test above still passes because it clears via a different path)."""
    with dataset("smb_locked_alert") as ds:
        with smb_share(f"/mnt/{ds}", "smb_locked_alert_share") as share:
            share_id = share["id"]

            # Share sits on a normal, unlocked dataset.
            assert call("sharing.smb.get_instance", share_id)["locked"] is False

            # Simulate the leftover boot alert (attachment-toggle clear path bypassed).
            call("sharing.smb.generate_locked_alert", share_id)
            assert wait_for_share_locked_alert("SMB", share_id) is not None

            # Regenerating smb.conf must clear the stale alert for the unlocked share.
            call("etc.generate", "smb")

            assert wait_for_share_locked_alert_cleared("SMB", share_id), (
                "stale ShareLocked alert was not cleared on smb.conf regeneration"
            )
