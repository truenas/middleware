"""`zfs.tier` must refuse the datasets middleware manages on the user's behalf.

This lives at the top level of `tests/api2/` rather than alongside the other tier tests in
`tests/api2/zfs_tier/`, whose conftest skips the whole directory unless the system is licensed and
has a SPECIAL vdev with spare disks. The refusals here are pure path checks that run before
`zfs.tier` looks at its own configuration, so they are reachable -- and worth asserting -- on any
system, and none of the paths named below has to exist.
"""

import re

import pytest

from middlewared.test.integration.utils import call, pool

PROTECTED_MESSAGE = "is a protected path."

# One representative of each shape the registry matches: the system dataset, the apps dataset, and
# a dataset in the boot pool.
PROTECTED_PREFIXES = [f"{pool}/.system", f"{pool}/ix-apps", "boot-pool/ROOT"]

ABSENT = "tier-test-absent/leaf"
"""A location under each managed dataset that nothing ever creates.

`dataset_set_tier` and `rewrite_job_create` queue a full block rewrite of everything they are aimed
at, so naming the managed datasets themselves means a guard that regressed does not fail this file
-- it rewrites the boot environments and the system dataset. Aiming one level down at something
absent keeps every refusal meaning the same thing while leaving a regressed guard nothing to act on:
it gets ENOENT."""

PROTECTED_DATASETS = [f"{prefix}/{ABSENT}" for prefix in PROTECTED_PREFIXES]

UNMANAGED_ABSENT_DATASET = f"{pool}/no-such-dataset-for-tiering"

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
test was never reached and the case proved nothing."""

# A well-formed `dataset_name@job_uuid` needs a uuid half, but no job by this id exists anywhere --
# the refusal happens before the daemon is ever asked about it.
JOB_UUID = "00000000-0000-0000-0000-000000000000"

TIER_MUTATORS = [
    (
        "zfs.tier.dataset_set_tier",
        lambda ds: ({"dataset_name": ds, "tier_type": "PERFORMANCE"},),
    ),
    ("zfs.tier.rewrite_job_create", lambda ds: ({"dataset_name": ds},)),
    (
        "zfs.tier.rewrite_job_recover",
        lambda ds: ({"tier_job_id": f"{ds}@{JOB_UUID}"},),
    ),
]

TIER_IDS = [m for m, _ in TIER_MUTATORS]


def assert_protected(method, args):
    with pytest.raises(Exception) as exc_info:
        call(method, *args)

    text = str(exc_info.value)
    assert PROTECTED_MESSAGE in text, text
    assert "[EACCES]" in text, text


@pytest.fixture(scope="module", autouse=True)
def protected_targets_are_absent():
    """The targets below only stay harmless while they do not exist, so check rather than assume.

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
        f"these tier calls are about to be aimed at real datasets: {existing}"
    )

    assert not call(
        "pool.dataset.query_impl", [["id", "=", UNMANAGED_ABSENT_DATASET]], {}, False
    ), f"{UNMANAGED_ABSENT_DATASET} exists, so the control below would act on it"


@pytest.mark.parametrize("ds", PROTECTED_DATASETS)
@pytest.mark.parametrize("method,build_args", TIER_MUTATORS, ids=TIER_IDS)
def test_tier_mutator_refuses_protected_dataset(method, build_args, ds):
    assert_protected(method, build_args(ds))


@pytest.mark.parametrize("method,build_args", TIER_MUTATORS, ids=TIER_IDS)
def test_ordinary_dataset_is_not_refused(method, build_args):
    """The control: an unmanaged path gets past the check and fails for its own reasons.

    Paired with the test above this is also what proves the check runs first. On a system with
    tiering switched off -- which is every system the tier suite itself skips on -- these calls
    stop at "ZFS tiering is globally disabled", while a managed dataset is refused before that.

    Requiring a raise is safe because the target does not exist: every one of these methods either
    stops at "globally disabled" or at ENOENT from its own dataset lookup. A call that succeeds
    means the target was real after all, and a request-model rejection means the method body was
    never entered -- both leave the guard unexercised, which is what this case exists to check.
    """
    with pytest.raises(Exception) as exc_info:
        call(method, *build_args(UNMANAGED_ABSENT_DATASET))

    text = str(exc_info.value)
    assert PROTECTED_MESSAGE not in text, text
    assert "[EACCES]" not in text, text
    assert not SCHEMA_REJECTION_RE.search(text), (
        f"{method}: the request model rejected this payload: {text}"
    )
