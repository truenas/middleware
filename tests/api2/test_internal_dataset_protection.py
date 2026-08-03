"""Public mutators must refuse the datasets middleware manages on the user's behalf.

Every guard is a pure check on the path, run before the resource is looked up, so none of the
protected paths named here has to exist -- which is what makes covering the whole matrix cheap, and
what lets the matrix aim at paths that deliberately do not exist. The user-dataset half of the file
is the control: it proves the guards reject what they are meant to and nothing else.
"""

import re

import pytest
from truenas_api_client import ClientException
from truenas_api_client import ValidationErrors as ClientValidationErrors

from middlewared import service_exception
from middlewared.plugins.zfs.exceptions import ZFSPathNotFoundException
from middlewared.service_exception import (
    CallError,
    MatchNotFound,
    ValidationError,
    ValidationErrors,
)
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, pool, ssh

PROTECTED_MESSAGE = "is a protected path."
SNAP = "protection-test"
CLONE_DST = f"{pool}/protection-test-clone"

# One representative of each shape the registry matches: the system dataset, the apps dataset,
# and the boot pool. A bare pool root is deliberately absent -- it is not protected.
PROTECTED_PREFIXES = [f"{pool}/.system", f"{pool}/ix-apps", "boot-pool/ROOT"]

ABSENT = "protection-test-absent/leaf"
"""A location under each managed dataset that nothing ever creates.

The matrix fires recursive destroys and renames, so aiming it at the managed datasets themselves
means a guard that regressed does not fail this file -- it wipes the boot environments and the
system dataset. Aiming one level down at something absent keeps every refusal meaning the same
thing while leaving a regressed guard nothing to act on: it gets ENOENT.

Two components rather than one, because with one a regressed rename would *succeed*, leaving a user
dataset parked inside the system dataset."""

PROTECTED_DATASETS = [f"{prefix}/{ABSENT}" for prefix in PROTECTED_PREFIXES]

LOOKALIKE = f"{pool}/ix-apps-data"
"""A user dataset whose name merely starts with a managed one.

Nothing about it is managed -- every rule here compares whole components one level under the pool
root -- so creation and every mutator alike have to treat it as the ordinary dataset it is."""

RESERVED_MESSAGE = "is using system internal managed dataset"

BOOT_POOL_NAMES = ("boot-pool", "freenas-boot")
"""Every name a boot pool may have. A pool merely named like one -- `boot-pool-2` -- is a user pool
and has to be listed."""

HIDDEN_TOP_LEVEL_CHILDREN = (
    ".system",
    "ix-apps",
    "ix-applications",
    ".truenas_containers",
)
"""The names that are hidden from the dataset listing when they sit one level under a pool root.

Compared as whole components, so a dataset whose name merely begins with one of these is listed, and
so is one that carries one of these names at any other depth."""

GRACEFUL_FAILURES = (
    CallError,
    MatchNotFound,
    ValidationError,
    ValidationErrors,
    ClientValidationErrors,
    ZFSPathNotFoundException,
)
"""Exception types that mean the service considered the call and declined it.

The raw ZFS exception is one of them because `pool.snapshot.rollback`, `hold`, `release` and
`clone` call the private implementation directly, past the public `zfs.resource.snapshot.*` method
that turns a missing path into an ENOENT `ValidationError` -- so an absent snapshot is refused with
the untranslated exception. That is still a refusal, and translating it is not this file's business.

Anything else -- an unhandled server-side exception surfacing as a bare `ClientException`, a
transport failure -- means the mutator broke rather than refused, and a control case that "passes"
on one of those has tested nothing."""

SCHEMA_REJECTION_RE = re.compile(
    r": (Field required"
    r"|Extra inputs are not permitted"
    r"|Input should "
    r"|Input tag "
    r"|Unable to extract tag"
    r"|Value error, "
    r"|Assertion failed, "
    r"|Too many arguments)"
)
"""Pydantic's own rejection messages, which are a closed set no service produces.

A request model that rejects the payload rejects it before the method body runs, so the guard under
test was never reached and the case proved nothing. This is the difference between "the mutator let
this path through" and "this payload was never valid in the first place"."""

# `(method, args)` for every guarded public mutator that takes a dataset path.
DATASET_MUTATORS = [
    ("pool.dataset.promote", lambda ds: (ds,)),
    (
        "pool.dataset.rename",
        lambda ds: (ds, {"new_name": f"{pool}/renamed", "force": True}),
    ),
    ("pool.dataset.update", lambda ds: (ds, {})),
    ("pool.dataset.delete", lambda ds: (ds, {"recursive": True})),
    ("pool.dataset.get_quota", lambda ds: (ds, "DATASET")),
    (
        # A real size rather than 0: 0 means "remove" only for a user or group quota, and libzfs
        # refuses it as a dataset quota, so the control half would fail on the value before the
        # guard it is here to exercise had said anything.
        "pool.dataset.set_quota",
        lambda ds: (
            ds,
            [{"quota_type": "DATASET", "id": "QUOTA", "quota_value": 1024**3}],
        ),
    ),
    ("pool.dataset.inherit_parent_encryption_properties", lambda ds: (ds,)),
    ("pool.snapshot.create", lambda ds: ({"dataset": ds, "name": SNAP},)),
    ("zfs.resource.destroy", lambda ds: ({"path": ds, "recursive": True},)),
    ("zfs.resource.snapshot.create", lambda ds: ({"dataset": ds, "name": SNAP},)),
]

# The same, for mutators that run as jobs: their guard raises inside the job, so the refusal only
# reaches the caller once the job is waited on.
JOB_DATASET_MUTATORS = [
    ("pool.dataset.lock", lambda ds: (ds, {"force_umount": True})),
    ("pool.dataset.change_key", lambda ds: (ds, {"generate_key": True})),
]

# `(method, args)` for every guarded public mutator that takes a snapshot path.
SNAPSHOT_MUTATORS = [
    ("pool.snapshot.delete", lambda s: (s, {})),
    ("pool.snapshot.rollback", lambda s: (s, {})),
    ("pool.snapshot.hold", lambda s: (s, {})),
    ("pool.snapshot.release", lambda s: (s, {})),
    ("pool.snapshot.rename", lambda s: (s, {"new_name": f"{s}-new", "force": True})),
    ("pool.snapshot.clone", lambda s: ({"snapshot": s, "dataset_dst": CLONE_DST},)),
    ("zfs.resource.snapshot.destroy", lambda s: ({"path": s},)),
    (
        "zfs.resource.snapshot.rename",
        lambda s: ({"current_name": s, "new_name": f"{s}-new"},),
    ),
    ("zfs.resource.snapshot.clone", lambda s: ({"snapshot": s, "dataset": CLONE_DST},)),
    ("zfs.resource.snapshot.hold", lambda s: ({"path": s},)),
    ("zfs.resource.snapshot.release", lambda s: ({"path": s},)),
    ("zfs.resource.snapshot.rollback", lambda s: ({"path": s},)),
]

# Mutators whose *destination* is guarded as well as their source, so that a protected dataset
# cannot be brought into existence by renaming or cloning onto it.
DESTINATION_MUTATORS = [
    (
        "zfs.resource.snapshot.clone",
        lambda src, dst: ({"snapshot": src, "dataset": dst},),
    ),
    ("pool.snapshot.clone", lambda src, dst: ({"snapshot": src, "dataset_dst": dst},)),
]

# The methods whose request models carry the `bypass` escape hatch, with payloads that are
# otherwise valid.
BYPASS_PAYLOADS = [
    ("zfs.resource.snapshot.create", {"dataset": f"{pool}/x", "name": "a"}),
    ("zfs.resource.snapshot.destroy", {"path": f"{pool}/x@a"}),
    (
        "zfs.resource.snapshot.rename",
        {"current_name": f"{pool}/x@a", "new_name": f"{pool}/x@b"},
    ),
    ("zfs.resource.snapshot.clone", {"snapshot": f"{pool}/x@a", "dataset": CLONE_DST}),
    ("zfs.resource.snapshot.hold", {"path": f"{pool}/x@a"}),
    ("zfs.resource.snapshot.release", {"path": f"{pool}/x@a"}),
    ("zfs.resource.snapshot.rollback", {"path": f"{pool}/x@a"}),
]

DATASET_IDS = [m for m, _ in DATASET_MUTATORS]
JOB_DATASET_IDS = [m for m, _ in JOB_DATASET_MUTATORS]
SNAPSHOT_IDS = [m for m, _ in SNAPSHOT_MUTATORS]
DESTINATION_IDS = [m for m, _ in DESTINATION_MUTATORS]
BYPASS_IDS = [m for m, _ in BYPASS_PAYLOADS]

# Mutators that would really change a user's dataset, so the control test skips them; they get
# their own round trip further down instead.
DESTRUCTIVE = {"pool.dataset.rename", "pool.dataset.delete", "zfs.resource.destroy"}


def assert_protected(method, args, job=False):
    with pytest.raises(Exception) as exc_info:
        call(method, *args, job=job)

    text = str(exc_info.value)
    assert PROTECTED_MESSAGE in text, text
    assert "[EACCES]" in text, text


def is_a_refusal_that_lost_its_class(exc):
    """Whether a bare `ClientException` is carrying a refusal rather than a mutator that broke.

    A job's exception does not reach the caller as itself: validation errors are rebuilt, and
    everything else -- a `CallError` declining the call included -- arrives flattened into a
    `ClientException` with only the server-side class name left behind in the trace. Reading that
    back is the one way left to tell the two apart.
    """
    raised = getattr(service_exception, (exc.trace or {}).get("class", ""), None)
    return raised is not None and issubclass(raised, GRACEFUL_FAILURES)


def assert_not_protected(method, args, job=False):
    """The call may fail for its own reasons, but never because the path looked protected -- and it
    has to have reached the guard at all for its silence to mean anything.

    `ClientValidationErrors` subclasses `ClientException`, so it has to be handled by the first
    clause or the second one would swallow it.
    """

    def assert_the_guard_was_not_what_refused(text):
        assert PROTECTED_MESSAGE not in text, text
        assert "[EACCES]" not in text, text
        assert not SCHEMA_REJECTION_RE.search(text), (
            f"{method}: the request model rejected this payload: {text}"
        )

    try:
        call(method, *args, job=job)
    except GRACEFUL_FAILURES as e:
        assert_the_guard_was_not_what_refused(str(e))
    except ClientException as e:
        if not is_a_refusal_that_lost_its_class(e):
            raise AssertionError(
                f"{method}: failed server-side rather than refusing gracefully: {e!r}"
            ) from e
        assert_the_guard_was_not_what_refused(str(e))
    except Exception as e:
        raise AssertionError(
            f"{method}: raised {type(e).__name__}, which is not a graceful refusal: {e}"
        ) from e


@pytest.fixture(scope="module", autouse=True)
def protected_targets_are_absent():
    """The matrix only stays harmless while its targets do not exist, so check rather than assume.

    The listing filter has to be turned off for this query, or it answers "absent" for every path
    under a managed dataset and the check is vacuous -- which is also why the prefixes are asserted
    to be visible first. Turning it off is the private implementation's privilege rather than
    something a request can ask for, so this goes through `query_impl`.
    """
    visible = [
        ds
        for ds in PROTECTED_PREFIXES
        if call("pool.dataset.query_impl", [["id", "=", ds]], {}, False)
    ]
    assert visible, (
        f"none of {PROTECTED_PREFIXES} is visible, so nothing below can be shown to be absent"
    )

    existing = [
        ds
        for ds in PROTECTED_DATASETS
        if call("pool.dataset.query_impl", [["id", "=", ds]], {}, False)
    ]
    assert not existing, (
        f"the matrix is about to fire destroys and renames at real datasets: {existing}"
    )


@pytest.mark.parametrize("ds", PROTECTED_DATASETS)
@pytest.mark.parametrize("method,build_args", DATASET_MUTATORS, ids=DATASET_IDS)
def test_dataset_mutator_refuses_protected_dataset(method, build_args, ds):
    assert_protected(method, build_args(ds))


@pytest.mark.parametrize("ds", PROTECTED_DATASETS)
@pytest.mark.parametrize("method,build_args", JOB_DATASET_MUTATORS, ids=JOB_DATASET_IDS)
def test_job_mutator_refuses_protected_dataset(method, build_args, ds):
    assert_protected(method, build_args(ds), job=True)


@pytest.mark.parametrize("ds", PROTECTED_DATASETS)
@pytest.mark.parametrize("method,build_args", SNAPSHOT_MUTATORS, ids=SNAPSHOT_IDS)
def test_snapshot_mutator_refuses_protected_dataset(method, build_args, ds):
    assert_protected(method, build_args(f"{ds}@{SNAP}"))


@pytest.mark.parametrize("ds", PROTECTED_DATASETS)
def test_unload_key_refuses_protected_dataset(ds):
    """Its own case rather than a row in the matrix, because the matrix has a control half.

    Every other mutator there is aimed at a real user dataset to prove it is let through, and the
    payload that would need is `force_unmount` against something mounted -- a real unmount of a real
    dataset, which is not what this file is for.
    """
    assert_protected("zfs.resource.unload_key", (ds,))


@pytest.mark.parametrize("ds", PROTECTED_DATASETS)
def test_update_impl_refuses_protected_dataset(ds):
    """`pool.dataset.update` carries a guard of its own, so the matrix passes without this one.

    The private implementation is what every in-tree caller that sets a property actually reaches,
    and it is reachable without going through the public method at all, so its guard needs a case
    that fails when only it is removed.
    """
    assert_protected("pool.dataset.update_impl", ({"name": ds},))


@pytest.mark.parametrize("ds", PROTECTED_PREFIXES)
def test_the_managed_datasets_themselves_are_refused(ds):
    """The matrix aims one level down, so a shape that narrowed to "descendants only" would leave it
    entirely green while the managed datasets became mutable. This is the case that would fail.

    Only two mutators, chosen because neither could do damage even with no guard at all: `get_quota`
    reads, and a managed dataset is never a clone, so `promote` has nothing to promote.
    """
    assert_protected("pool.dataset.get_quota", (ds, "DATASET"))
    assert_protected("pool.dataset.promote", (ds,))


@pytest.mark.parametrize("ds", PROTECTED_DATASETS)
def test_rename_refuses_a_protected_destination(ds):
    """Renaming *into* a protected path is how one would otherwise be created."""
    with dataset("rename-src") as src:
        assert_protected("pool.dataset.rename", (src, {"new_name": ds, "force": True}))


@pytest.mark.parametrize("ds", PROTECTED_DATASETS)
@pytest.mark.parametrize("method,build_args", DESTINATION_MUTATORS, ids=DESTINATION_IDS)
def test_clone_refuses_a_protected_destination(method, build_args, ds):
    assert_protected(method, build_args(f"{pool}/x@a", ds))


@pytest.mark.parametrize("method,payload", BYPASS_PAYLOADS, ids=BYPASS_IDS)
def test_bypass_is_rejected(method, payload):
    """`bypass` is how the subsystem that owns a dataset reaches past these guards, and it is a
    `Private` field, so a request that supplies it at all is rejected before the guard is reached.
    """
    with pytest.raises(Exception) as exc_info:
        call(method, payload | {"bypass": True})

    text = str(exc_info.value)
    assert "bypass" in text, text
    assert "not permitted" in text.lower(), text


def test_exclude_internal_paths_is_rejected():
    """The listing filter is `Private` too, so a caller cannot turn it off over the wire."""
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.query", {"exclude_internal_paths": False})

    text = str(exc_info.value)
    assert "exclude_internal_paths" in text, text
    assert "not permitted" in text.lower(), text


def test_pool_root_is_not_protected():
    """A pool root hosting the system dataset stays the user's to manage.

    The read and the promote can be aimed at the real pool because neither can change it. Destroy
    cannot, so it is aimed at a pool that does not exist: the guard runs before the path is looked
    up, and the root-filesystem rejection sits after the guard, so reaching that specific message is
    the proof that the guard let a pool root through.
    """
    assert_not_protected("pool.dataset.get_quota", (pool, "DATASET"))
    assert_not_protected("pool.dataset.promote", (pool,))

    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.destroy", {"path": "protection-test-absent-pool"})

    assert "Destroying the root filesystem is not allowed." in str(exc_info.value), str(
        exc_info.value
    )


def test_user_dataset_is_not_protected():
    """Nothing a user owns is caught by the guards."""
    with dataset("not-protected") as ds:
        for method, build_args in DATASET_MUTATORS:
            if method not in DESTRUCTIVE:
                assert_not_protected(method, build_args(ds))

        for method, build_args in JOB_DATASET_MUTATORS:
            assert_not_protected(method, build_args(ds), job=True)

        # A snapshot that does not exist: every one of these fails with ENOENT, which is exactly
        # what we want -- the call got past the guard without mutating anything.
        for method, build_args in SNAPSHOT_MUTATORS:
            assert_not_protected(method, build_args(f"{ds}@no-such-snapshot"))


def test_user_dataset_can_still_be_renamed():
    with dataset("rename-me") as ds:
        renamed = f"{ds}-renamed"
        call("pool.dataset.rename", ds, {"new_name": renamed, "force": True})
        try:
            assert call("pool.dataset.query", [["id", "=", renamed]])
        finally:
            call("pool.dataset.rename", renamed, {"new_name": ds, "force": True})


def test_user_dataset_can_still_be_destroyed():
    ds = f"{pool}/destroy-me"
    call("pool.dataset.create", {"name": ds})
    try:
        call("zfs.resource.destroy", {"path": ds})
        assert not call("pool.dataset.query", [["id", "=", ds]])
    finally:
        # Out of band, because the failure this test exists to catch is `zfs.resource.destroy`
        # refusing the dataset -- a teardown through it would leak the dataset on exactly that
        # failure, and every later run would then fail on the name already existing.
        ssh(f"zfs destroy -r {ds}", check=False)


@pytest.fixture
def lookalike_dataset():
    """Made out of band so the cases below do not lean on `pool.dataset.create` accepting the name.

    Whether creation accepts it is its own case further down; these ones are about what a user may do
    to such a dataset once it exists, which has to hold either way -- including on a system where the
    name was created back when creation refused it.
    """
    ssh(f"zfs create {LOOKALIKE}")
    try:
        yield LOOKALIKE
    finally:
        ssh(f"zfs destroy -r {LOOKALIKE}", check=False)


def test_lookalike_dataset_is_listed(lookalike_dataset):
    assert call("pool.dataset.query", [["id", "=", lookalike_dataset]])
    assert call("pool.dataset.get_instance", lookalike_dataset)["id"] == LOOKALIKE


def test_lookalike_dataset_can_be_updated(lookalike_dataset):
    updated = call("pool.dataset.update", lookalike_dataset, {"atime": "OFF"})
    assert updated["atime"]["value"] == "OFF", updated["atime"]


def test_lookalike_dataset_can_be_deleted(lookalike_dataset):
    call("pool.dataset.delete", lookalike_dataset, {"recursive": True})
    assert not call("pool.dataset.query", [["id", "=", lookalike_dataset]])


def test_lookalike_dataset_can_be_created():
    """Creation asks the same question as every mutator above, so it has to give the same answer.

    Creation used to refuse any component merely starting with a managed name, at any depth. That
    left a user who asked for this dataset refused outright, while a user who already had one could
    list, update and delete it freely -- the tests above. One rule now, so the refusal a user gets is
    exactly the set of datasets a user cannot manage.
    """
    call("pool.dataset.create", {"name": LOOKALIKE})
    try:
        assert call("pool.dataset.query", [["id", "=", LOOKALIKE]])
    finally:
        call("pool.dataset.delete", LOOKALIKE, {"recursive": True})


@pytest.mark.parametrize(
    "name",
    [
        f"{pool}/ix-apps/child",
        f"{pool}/ix-applications",
    ],
)
def test_creation_is_refused_at_and_under_a_managed_dataset(name):
    """A managed dataset itself, and anything below one, are both off limits to create.

    The child case is the one that matters: refusing only the managed name would let a user park a
    dataset inside the apps dataset.
    """
    with pytest.raises(Exception) as exc_info:
        call("pool.dataset.create", {"name": name, "create_ancestors": True})

    assert RESERVED_MESSAGE in str(exc_info.value), str(exc_info.value)


def test_internal_datasets_stay_out_of_the_dataset_listing(lookalike_dataset):
    """The listing hides whole components, not substrings, so it has to hide no more than it must.

    The look-alike is created for this case rather than only asserted against, because "nothing
    resembling a managed name is listed" and "a user's own dataset is listed" are the same
    assertion pulling in opposite directions, and only one of them can be right.
    """
    listed = [entry["id"] for entry in call("pool.dataset.query")]

    for name in listed:
        components = name.split("/")
        assert components[0] not in BOOT_POOL_NAMES, name
        assert len(components) < 2 or components[1] not in HIDDEN_TOP_LEVEL_CHILDREN, (
            name
        )

    assert lookalike_dataset in listed, listed
