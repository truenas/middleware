"""What the mutation guard refuses, and what it lets through.

The guard is the only thing standing between a caller and a dataset middleware manages, so the
cases that matter are the ones where it could quietly stop refusing: the boot pool root, which is
the one single-component path that is protected, and the asymmetry between the two guards over a
snapshot name -- one drops the suffix before asking and the other deliberately does not.

One case runs the other way and is asserted just as hard: the container dataset is let through by
both guards on purpose, so a well-meant tidy-up that adds it to the mutation membership fails here
rather than changing product behaviour unnoticed.
"""

import errno

import pytest

from middlewared.service_exception import ValidationError
from middlewared.utils.boot.pool import BOOT_POOL_NAME_VALID
from middlewared.utils.zfs.managed_datasets import (
    CONTAINER_DS_NAME,
    deny_protected_path,
    deny_protected_snapshot,
)

SCHEMA = "zfs.resource.snapshot.destroy"

PROTECTED = "tank/.system"
"""A dataset the system dataset plugin owns."""

USER = "tank/data"
"""An ordinary dataset."""

MANAGED = ["tank/.system", "tank/ix-apps", "tank/ix-applications"]
"""Every dataset the guards refuse below a data pool root, one level down where each is created."""

MANAGED_CHILDREN = ["tank/.system/cores", "tank/ix-apps/docker", "tank/ix-applications/releases"]
"""One level below each of MANAGED, where the data a managed dataset holds actually lives. The
guards are anchored to the second component, so nothing about being deeper makes a path safe."""


@pytest.mark.parametrize("guard", [deny_protected_path, deny_protected_snapshot])
def test_protected_path_is_refused_by_default(guard):
    """The refusal is the default, so a caller that says nothing gets it."""
    with pytest.raises(ValidationError) as exc:
        guard(SCHEMA, PROTECTED)

    assert exc.value.attribute == SCHEMA
    assert exc.value.errmsg == "'tank/.system' is a protected path."
    assert exc.value.errno == errno.EACCES


@pytest.mark.parametrize("guard", [deny_protected_path, deny_protected_snapshot])
def test_protected_path_is_refused_when_bypass_is_false(guard):
    with pytest.raises(ValidationError):
        guard(SCHEMA, PROTECTED, False)


@pytest.mark.parametrize("guard", [deny_protected_path, deny_protected_snapshot])
def test_owner_may_touch_a_protected_path(guard):
    guard(SCHEMA, PROTECTED, True)


@pytest.mark.parametrize("guard", [deny_protected_path, deny_protected_snapshot])
@pytest.mark.parametrize("bypass", [False, True])
def test_user_path_passes_either_way(guard, bypass):
    guard(SCHEMA, USER, bypass)


@pytest.mark.parametrize("guard", [deny_protected_path, deny_protected_snapshot])
def test_data_pool_root_is_not_protected(guard):
    """Users have to be able to destroy a pool that happens to host the system dataset."""
    guard(SCHEMA, "tank", False)


@pytest.mark.parametrize("guard", [deny_protected_path, deny_protected_snapshot])
@pytest.mark.parametrize("boot_pool", BOOT_POOL_NAME_VALID)
def test_boot_pool_root_is_protected(guard, boot_pool):
    """The counterpart to the data pool root: a single-component path is not automatically safe.

    A guard that returned early when the path has no "/" -- the obvious reading of "a pool root is
    never protected" -- would still pass every other case here while opening the boot pool up.
    Parametrized over the boot pool names rather than naming one, so that a system upgraded from a
    FreeNAS-era install is covered by the same assertion as a fresh one.
    """
    with pytest.raises(ValidationError) as exc:
        guard(SCHEMA, boot_pool, False)

    assert exc.value.errmsg == f"'{boot_pool}' is a protected path."
    assert exc.value.errno == errno.EACCES


@pytest.mark.parametrize("guard", [deny_protected_path, deny_protected_snapshot])
@pytest.mark.parametrize("path", MANAGED)
def test_managed_dataset_is_refused(guard, path):
    """Every name the guards refuse below a data pool root, not just the system dataset."""
    with pytest.raises(ValidationError) as exc:
        guard(SCHEMA, path, False)

    assert exc.value.errmsg == f"'{path}' is a protected path."
    assert exc.value.errno == errno.EACCES


@pytest.mark.parametrize("guard", [deny_protected_path, deny_protected_snapshot])
@pytest.mark.parametrize("path", MANAGED_CHILDREN + ["boot-pool/ROOT/default"])
def test_a_dataset_below_a_managed_one_is_refused(guard, path):
    """Depth does not earn a path its way out.

    The refusal is what keeps a caller from destroying, renaming or promoting the pieces a managed
    dataset is actually made of -- which is where the damage is, since the managed dataset itself is
    usually an empty container.
    """
    with pytest.raises(ValidationError) as exc:
        guard(SCHEMA, path, False)

    assert exc.value.errmsg == f"'{path}' is a protected path."
    assert exc.value.errno == errno.EACCES


@pytest.mark.parametrize("guard", [deny_protected_path, deny_protected_snapshot])
@pytest.mark.parametrize(
    "path",
    [f"tank/{CONTAINER_DS_NAME}", f"tank/{CONTAINER_DS_NAME}/containers", f"tank/{CONTAINER_DS_NAME}@snap"],
)
def test_container_dataset_is_not_protected_from_mutation(guard, path):
    """The one managed dataset the guards let through, which is deliberate and easy to mistake for a
    hole.

    It is hidden from ``pool.dataset`` and from nothing else, so ``zfs.resource.destroy`` will
    destroy it on request while ``pool.dataset.delete`` answers ENOENT -- the lookup behind that one
    runs through the listing this name is filtered out of. Closing that asymmetry means changing the
    mutation membership in the registry, deliberately; a guard that quietly starts refusing this
    name has changed product behaviour instead, and fails here.
    """
    guard(SCHEMA, path, False)


@pytest.mark.parametrize("boot_pool", BOOT_POOL_NAME_VALID)
def test_boot_pool_snapshot_is_refused_only_by_the_stripping_guard(boot_pool):
    """The suffix on "boot-pool@snap" sits on the one component a boot pool is matched by, so the
    dataset name has to be recovered before the registry recognises it."""
    deny_protected_path(SCHEMA, f"{boot_pool}@snap", False)

    with pytest.raises(ValidationError) as exc:
        deny_protected_snapshot(SCHEMA, f"{boot_pool}@snap", False)

    assert exc.value.errmsg == f"'{boot_pool}@snap' is a protected path."
    assert exc.value.errno == errno.EACCES


def test_snapshot_guard_decides_on_the_dataset():
    """A snapshot of a protected dataset is refused: the suffix is dropped before asking."""
    with pytest.raises(ValidationError) as exc:
        deny_protected_snapshot(SCHEMA, "tank/.system@snap")

    assert exc.value.errmsg == "'tank/.system@snap' is a protected path."
    assert exc.value.errno == errno.EACCES


def test_path_guard_lets_a_snapshot_through_when_the_suffix_defeats_the_match():
    """``zfs.resource.destroy`` has to keep telling the caller to use the snapshot endpoint, so the
    non-stripping guard must let a snapshot name fall through to that message.

    This is not "the path guard never refuses a snapshot name" -- it refuses plenty; see below. It
    holds for "tank/.system@snap" because the suffix lands on the very component being compared.
    """
    deny_protected_path(SCHEMA, "tank/.system@snap", False)


@pytest.mark.parametrize("path", ["boot-pool/ROOT@snap", "freenas-boot/grub@snap", "tank/.system/cores@snap"])
def test_path_guard_still_refuses_a_snapshot_whose_dataset_it_matches(path):
    """Not stripping the suffix is not the same as ignoring snapshot names.

    Wherever the compared component sits above the suffix -- the first component for a boot pool,
    the second for anything below a managed dataset -- the guard matches the name as written and
    refuses it, so the caller never reaches the "use the snapshot endpoint" hint.
    """
    with pytest.raises(ValidationError) as exc:
        deny_protected_path(SCHEMA, path, False)

    assert exc.value.errmsg == f"'{path}' is a protected path."
    assert exc.value.errno == errno.EACCES


def test_snapshot_guard_still_refuses_a_bare_dataset():
    with pytest.raises(ValidationError):
        deny_protected_snapshot(SCHEMA, PROTECTED, False)


@pytest.mark.parametrize("guard", [deny_protected_path, deny_protected_snapshot])
@pytest.mark.parametrize("bypass", [1, "yes", ["anything"]])
def test_any_truthy_bypass_is_permission(guard, bypass):
    """The guard asks for truth and nothing more, so a stray value permits rather than raising.

    That is deliberate rather than an oversight: reaching any of these entry points already
    requires an unrestricted credential, so the only thing a stricter reading would catch is a
    middleware typo, at the cost of a refusal that behaves differently depending on how the value
    happened to be spelled.
    """
    guard(SCHEMA, PROTECTED, bypass)


@pytest.mark.parametrize("guard", [deny_protected_path, deny_protected_snapshot])
@pytest.mark.parametrize("bypass", [0, None, "", []])
def test_any_falsy_bypass_is_still_a_refusal(guard, bypass):
    """The other half of the truthiness contract, and the half that has to fail closed.

    A caller that reads its opt-in out of a config dict and gets None back, or that threads an empty
    collection through, must be refused rather than quietly permitted.
    """
    with pytest.raises(ValidationError):
        guard(SCHEMA, PROTECTED, bypass)
