import pytest

from middlewared.utils.boot.pool import BOOT_POOL_NAME_VALID
from middlewared.utils.zfs.managed_datasets import (
    APPS_DS_NAME,
    CONTAINER_DS_NAME,
    LEGACY_APPS_DS_NAME,
    MANAGED_DATASET_NAMES,
    blocked_from_mutation,
    excluded_from_replication,
    excluded_from_zfs_events,
    hidden_from_dataset_listing,
    hidden_from_snapshot_listing,
    hidden_from_zfs_listing,
    is_boot_pool_path,
)

PREDICATES = (
    hidden_from_zfs_listing,
    hidden_from_dataset_listing,
    blocked_from_mutation,
    excluded_from_zfs_events,
    excluded_from_replication,
)
"""The five predicates, in TRUTH_TABLE column order."""

# path, then one column per predicate, in the order of PREDICATES and of the parametrize below.
#
# Disagreements between the columns are real: every predicate matches the same way, so a column
# that differs from its neighbour differs because the two callers manage a different set of names.
# A column changing here means a caller's behaviour changed, so a change to this table is only ever
# deliberate.
TRUTH_TABLE = [
    # Boot pools: the pool itself and everything under it, in every view.
    ("boot-pool", True, True, True, True, True),
    ("boot-pool/ROOT/default", True, True, True, True, True),
    ("freenas-boot", True, True, True, True, True),
    ("freenas-boot/grub", True, True, True, True, True),
    # The boot pool test compares the first component only, so a snapshot suffix matters exactly
    # when it lands on that component: "boot-pool@snap" is not a boot pool, while a snapshot
    # anywhere below the pool root still is. The other views compare the second component instead,
    # which is why the ".system" rows further down come out the other way round.
    ("boot-pool@snap", False, False, False, False, False),
    ("boot-pool/ROOT@snap", True, True, True, True, True),
    ("freenas-boot@snap", False, False, False, False, False),
    ("freenas-boot/grub@snap", True, True, True, True, True),
    # A boot pool name below the pool root is an ordinary dataset -- the boot pool test is anchored
    # to the first component, and the boot pool names are in no other membership.
    ("tank/boot-pool", False, False, False, False, False),
    # A pool whose name merely starts with a boot pool name is an ordinary pool.
    ("boot-pool-2", False, False, False, False, False),
    ("boot-pool-2/data", False, False, False, False, False),
    ("freenas-boot-2", False, False, False, False, False),
    # Ordinary paths.
    ("tank", False, False, False, False, False),
    ("tank/data", False, False, False, False, False),
    # The system dataset directly under a pool: matched by every view.
    ("tank/.system", True, True, True, True, True),
    ("tank/.system/cores", True, True, True, True, True),
    # A snapshot suffix on the matched component defeats every view, because the component being
    # compared is then ".system@snap". One position deeper it does not, because the component being
    # compared is still ".system". The asymmetry is real; it is pinned, not endorsed.
    ("tank/.system@snap", False, False, False, False, False),
    ("tank/.system/cores@snap", True, True, True, True, True),
    # Nested deeper than a pool's top level: a managed name is only managed where the subsystem that
    # owns it puts it, which is always one level under a pool root.
    ("tank/foo/.system", False, False, False, False, False),
    # A name that merely starts with a managed one is a user's dataset, in every view.
    ("tank/.systembackup", False, False, False, False, False),
    # The current apps dataset.
    ("tank/ix-apps", True, True, True, True, False),
    ("tank/ix-apps/docker", True, True, True, True, False),
    ("tank/data/ix-apps", False, False, False, False, False),
    ("tank/ix-apps-data", False, False, False, False, False),
    ("tank/ix-appsdata", False, False, False, False, False),
    ("tank/myix-apps", False, False, False, False, False),
    # The legacy apps dataset, which every view but replication matches, exactly as it matches the
    # current one.
    ("tank/ix-applications", True, True, True, True, False),
    ("tank/ix-applications/releases", True, True, True, True, False),
    ("tank/a/b/ix-applications", False, False, False, False, False),
    ("tank/ix-applications-old", False, False, False, False, False),
    # The container dataset is hidden from the product's dataset listing and nothing else. The event
    # view in particular has to keep answering False, or destroying one out of band would skip the
    # encryption-key cleanup that follows a REMOVED event.
    (f"tank/{CONTAINER_DS_NAME}", False, True, False, False, False),
    (f"tank/{CONTAINER_DS_NAME}/containers", False, True, False, False, False),
    (f"tank/a/{CONTAINER_DS_NAME}", False, False, False, False, False),
    # The container look-alike and a snapshot of the container dataset itself. The look-alike is the
    # one shape the container name had no row for: the old listing matched "/.truenas_containers"
    # as a substring, so it hid this user dataset too and left it neither visible nor deletable.
    (f"tank/{CONTAINER_DS_NAME}-old", False, False, False, False, False),
    (f"tank/{CONTAINER_DS_NAME}@snap", False, False, False, False, False),
    # A pool literally named after an entry is not itself managed -- the separator is required.
    ("ix-apps", False, False, False, False, False),
    ("ix-apps/child", False, False, False, False, False),
    ("ix-apps/ix-apps", True, True, True, True, False),
    # A leading slash makes the first component empty, so what the rest of the table calls the
    # second component is the first one here and a managed name lands where it is matched. ZFS
    # rejects these names, so nothing can reach a predicate holding one; they are pinned because the
    # replication view used to be a regex anchored with "[^/]+", which answered the other way round.
    ("/.system", True, True, True, True, True),
    ("/ix-apps", True, True, True, True, False),
    ("/boot-pool", False, False, False, False, False),
    # A trailing slash adds an empty component, which changes nothing about the component that gets
    # compared -- so "tank/" is still a bare data pool root and "tank/.system/" is still matched.
    ("tank/.system/", True, True, True, True, True),
    ("tank/", False, False, False, False, False),
    # Degenerate input must be answered, not raised on.
    ("", False, False, False, False, False),
]


@pytest.mark.parametrize("path,zfs_listing,dataset_listing,mutation,zfs_events,replication", TRUTH_TABLE)
def test_predicates(path, zfs_listing, dataset_listing, mutation, zfs_events, replication):
    assert hidden_from_zfs_listing(path) is zfs_listing
    assert hidden_from_dataset_listing(path) is dataset_listing
    assert blocked_from_mutation(path) is mutation
    assert excluded_from_zfs_events(path) is zfs_events
    assert excluded_from_replication(path) is replication


DATASET_ROWS = [(row[0], row[1]) for row in TRUTH_TABLE if "@" not in row[0]]
"""TRUTH_TABLE's path and ZFS-listing column, for the rows whose path is a dataset name."""


@pytest.mark.parametrize("path,zfs_listing", DATASET_ROWS)
def test_snapshot_listing_answers_for_the_dataset(path, zfs_listing):
    """A snapshot is hidden exactly when its dataset is, and never otherwise.

    Derived from TRUTH_TABLE rather than restated, so a row added there is covered here too. The
    second assertion is the point of the predicate, and the reason it cannot simply be
    ``hidden_from_zfs_listing``: appending a suffix changes that one's answer for some of these
    names and not others, so callers handed a name of either shape need a predicate that does not
    care which they got.
    """
    assert hidden_from_snapshot_listing(path) is zfs_listing
    assert hidden_from_snapshot_listing(f"{path}@snap") is zfs_listing


SUFFIX_ON_THE_COMPARED_COMPONENT = [
    "boot-pool",
    "freenas-boot",
    "tank/.system",
    "tank/ix-apps",
    "tank/ix-applications",
    "ix-apps/ix-apps",
]
"""Hidden datasets whose managed name is the last component, so a suffix lands on it."""

SUFFIX_BELOW_THE_COMPARED_COMPONENT = [
    "boot-pool/ROOT/default",
    "freenas-boot/grub",
    "tank/.system/cores",
    "tank/ix-apps/docker",
    "tank/ix-applications/releases",
]
"""Hidden datasets with something below the managed name, so a suffix lands past it."""


@pytest.mark.parametrize("path", SUFFIX_ON_THE_COMPARED_COMPONENT)
def test_zfs_listing_loses_a_hidden_dataset_once_a_suffix_is_appended(path):
    """Half of why ``hidden_from_snapshot_listing`` exists, named rather than left implicit.

    Most of TRUTH_TABLE answers False before a suffix is appended and False after, so a scan of the
    rows would suggest "a suffix always defeats the match" while most of the evidence for it is
    vacuous. It does not always; these are the names where it does.
    """
    assert hidden_from_zfs_listing(path) is True
    assert hidden_from_zfs_listing(f"{path}@snap") is False


@pytest.mark.parametrize("path", SUFFIX_BELOW_THE_COMPARED_COMPONENT)
def test_zfs_listing_keeps_a_hidden_dataset_when_the_suffix_lands_deeper(path):
    """The other half: the compared component is untouched, so the answer does not move."""
    assert hidden_from_zfs_listing(path) is True
    assert hidden_from_zfs_listing(f"{path}@snap") is True


@pytest.mark.parametrize(
    "path,boot_pool",
    [
        ("boot-pool", True),
        ("freenas-boot", True),
        ("boot-pool/ROOT", True),
        # A suffix below the pool root leaves the compared component alone, so it still matches.
        ("freenas-boot/grub@snap", True),
        # A suffix on the pool root does not: the component being compared is "boot-pool@snap".
        ("boot-pool@snap", False),
        ("freenas-boot@snap", False),
        ("tank/boot-pool", False),
        ("/boot-pool", False),
        ("boot-pool-2", False),
        ("", False),
    ],
)
def test_is_boot_pool_path(path, boot_pool):
    """The disjunct every predicate carries, and the sole gate on docker's apps-mountpoint check.

    That call site asks this predicate directly rather than through a view, so it is the one place
    where a regression here would not show up as a changed column in TRUTH_TABLE.
    """
    assert is_boot_pool_path(path) is boot_pool


ALL_PATHS = [row[0] for row in TRUTH_TABLE]
"""TRUTH_TABLE's paths, for the laws that relate two columns rather than pin one."""


@pytest.mark.parametrize("path", ALL_PATHS)
def test_event_suppression_is_a_subset_of_the_product_listing(path):
    """Whatever the ZFS event channel drops, the product's dataset listing must already be hiding.

    Derived from TRUTH_TABLE rather than restated, so a row added there is covered here too. Dropping
    the event for a path the listing shows means an out-of-band ``zfs destroy`` publishes no REMOVED
    event, leaves the destroyed dataset's encryption key in the database and leaves a copy of it on
    the other HA node. The other direction costs nothing -- publishing REMOVED for a name the listing
    never showed is a no-op -- which is why the relation runs this way round and not both.
    """
    if excluded_from_zfs_events(path):
        assert hidden_from_dataset_listing(path) is True, path


@pytest.mark.parametrize("path", ALL_PATHS)
def test_mutation_refusal_is_a_subset_of_the_zfs_listing(path):
    """Whatever the mutation guard refuses, ``zfs.resource`` must already be hiding.

    Derived from TRUTH_TABLE rather than restated, so a row added there is covered here too. A name
    that is listed and then refused is a name the user can see, is told is theirs, and cannot touch;
    the way that arises in practice is a membership tuple handed to the wrong predicate. The
    converse is deliberately not asserted -- the container dataset is hidden from the product
    listing while staying fully mutable.
    """
    if blocked_from_mutation(path):
        assert hidden_from_zfs_listing(path) is True, path


@pytest.mark.parametrize("path", ALL_PATHS)
def test_replication_exclusion_is_a_subset_of_the_mutation_refusal(path):
    """Whatever replication withholds, the mutation guard must already be refusing.

    Derived from TRUTH_TABLE rather than restated, so a row added there is covered here too.
    Withholding a mutable dataset from the replication source list is just a dataset the user cannot
    back up. The converse is deliberately not asserted -- the apps datasets are refused every
    mutation and still offered to replication, because replication is how they are backed up.
    """
    if excluded_from_replication(path):
        assert blocked_from_mutation(path) is True, path


@pytest.mark.parametrize("path", ["tank/.system@snap", "boot-pool@snap", "tank/ix-apps@snap"])
def test_snapshot_listing_diverges_from_the_zfs_listing_on_a_snapshot_name(path):
    """The bug this predicate exists to close, pinned from the other direction.

    Three snapshot query and count call sites asked hidden_from_zfs_listing these names and got
    False for all of them, so the filter and its request-wide opt-out were both inert there.
    """
    assert hidden_from_zfs_listing(path) is False
    assert hidden_from_snapshot_listing(path) is True


@pytest.mark.parametrize(
    "path,hidden",
    [
        ("tank/.system@", True),
        ("tank/.system@a@b", True),
        ("@snap", False),
        ("", False),
        ("tank/data@snap", False),
    ],
)
def test_snapshot_listing_answers_degenerate_input(path, hidden):
    """ZFS rejects most of these, but a predicate that raises is a predicate a caller has to guard."""
    assert hidden_from_snapshot_listing(path) is hidden


def test_leading_slash_diverges_from_the_replication_regex():
    """The one known divergence from the behaviour this registry reproduces.

    The replication view used to be a regular expression anchored with ``[^/]+``, which cannot
    match a path whose first component is empty, so it answered False for "/.system" where the
    whole-component test answers True. This is unreachable -- ZFS rejects a leading slash in a
    dataset name,
    so no such path can exist -- and True is the more defensible of the two answers. It is pinned
    here so that nobody "corrects" it back on the strength of a diff against the old regex.
    """
    assert excluded_from_replication("/.system") is True


def test_pool_roots_are_not_blocked_from_mutation():
    """A *data* pool root must stay mutable even when it hosts the system dataset.

    Boot pool roots are deliberately the other way round; TRUTH_TABLE pins that.
    """
    for path in ("tank", "tank/"):
        assert blocked_from_mutation(path) is False


@pytest.mark.parametrize("name", BOOT_POOL_NAME_VALID)
def test_boot_pools_are_matched_by_every_predicate(name):
    """No caller may treat a boot pool as an ordinary dataset.

    TRUTH_TABLE pins the two names that exist today; this asserts the same thing for whatever
    BOOT_POOL_NAME_VALID holds, so a third boot pool name cannot arrive uncovered.
    """
    for predicate in PREDICATES:
        assert predicate(name) is True, predicate.__name__
        assert predicate(f"{name}/ROOT/default") is True, predicate.__name__


@pytest.mark.parametrize("name", MANAGED_DATASET_NAMES)
def test_every_managed_name_is_matched_by_some_predicate(name):
    """A name listed as managed but wired into no predicate is managed in name only."""
    path = name if name in BOOT_POOL_NAME_VALID else f"tank/{name}"
    assert any(predicate(path) for predicate in PREDICATES), path


def test_legacy_apps_dataset_is_matched_by_every_view_that_manages_it():
    """``<pool>/ix-applications`` used to be creatable and then invisible.

    The creation and event needles carried a trailing slash, so they reached only its descendants
    while every listing matched the dataset itself -- a user could create it and then neither see
    nor delete it. The views agree now, so what a user is refused is what a user cannot see.
    Replication still offers it, because replication is the supported way to back the apps datasets
    up.
    """
    path = f"tank/{LEGACY_APPS_DS_NAME}"
    assert hidden_from_zfs_listing(path) is True
    assert hidden_from_dataset_listing(path) is True
    assert blocked_from_mutation(path) is True
    assert excluded_from_zfs_events(path) is True
    assert excluded_from_replication(path) is False


def test_container_dataset_is_hidden_from_the_product_listing_only():
    """A deliberate asymmetry, and the consequences that are easy to trip over.

    The container dataset is hidden from the UI but is an ordinary dataset to every other predicate,
    so ``zfs.resource.destroy`` will destroy it on request while ``pool.dataset.delete`` answers
    ENOENT -- the lookup behind that one goes through the listing this name is filtered out of.
    The event column is the one that must not be "tidied up" to match the listing: destroying a
    container dataset out of band has to publish REMOVED, or its encryption key is never cleared
    from the database or from the other HA node.
    """
    path = f"tank/{CONTAINER_DS_NAME}"
    assert hidden_from_dataset_listing(path) is True
    for predicate in PREDICATES:
        if predicate is hidden_from_dataset_listing:
            continue
        assert predicate(path) is False, predicate.__name__


def test_apps_datasets_are_offered_to_replication():
    """Replication is the supported way to back the apps datasets up, so they must stay listed."""
    for name in (APPS_DS_NAME, LEGACY_APPS_DS_NAME):
        assert excluded_from_replication(f"tank/{name}") is False


@pytest.mark.parametrize("pool", ["tank", "dozer", "ix-apps"])
@pytest.mark.parametrize("name", ["ix-apps", "ix-applications"])
@pytest.mark.parametrize("suffix", ["", "/", "/child", "/a/b"])
def test_dataset_listing_subsumes_the_apps_alert_skip(pool, name, suffix):
    """The unencrypted-datasets alert skips the apps datasets by hand while iterating children of
    an already-filtered dataset listing. Every path that skip covers is one the dataset listing has
    already removed, so the skip can never fire -- which is what makes it safe to delete rather
    than convert.
    """
    assert hidden_from_dataset_listing(f"{pool}/{name}{suffix}") is True
