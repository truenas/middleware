"""Guard against a sixth registry of middleware-managed datasets being grown somewhere else.

Five of them existed before ``middlewared.utils.zfs.managed_datasets``, each with its own membership
list and its own matching algorithm, and they had drifted apart from one another in ways nobody
noticed because nothing tied them together. What lets that happen again is that spelling a dataset
name inline is easy and invisible, so this module makes it visible.

Three scans, in decreasing order of how much they catch:

* every string literal that names a managed dataset,
* every symbol whose name is shaped like a registry,
* every reference to the registry's own names, which is how a sixth registry would most likely be
  built -- on top of the fifth rather than beside it, and without spelling a literal that the first
  scan could see.

Each scan carries a both-directions allowlist: an unexpected hit fails, and so does an allowlist
entry that no longer matches anything. Every reason is either "owns this dataset" -- the subsystem
that creates and maintains it, which necessarily knows its name -- or a marker for a spelling that
has not been converged onto the registry yet. The second kind is the backlog.

One shape is deliberately not caught: a symbol built out of the word "system", such as
``SYSTEM_DATASETS``. Adding ``system`` to :data:`SYMBOL_RE` flags 25 legitimate symbols across 15
files -- ``SystemDatasetService``, ``SystemDatasetEntry``, ``system_dataset_path`` and their
relatives -- so the scan would be noise rather than signal. It is a won't-fix, not an oversight.
"""

import ast
import pathlib
import re

import pytest

from middlewared.utils.zfs import managed_datasets
from middlewared.utils.zfs.managed_datasets import MANAGED_DATASET_NAMES

MIDDLEWARED_ROOT = pathlib.Path(__file__).resolve().parents[4]
"""The ``middlewared`` package directory."""

REGISTRY_MODULE = "utils/zfs/managed_datasets.py"

SKIPPED_TREES = ("pytest/", "alembic/")
"""``pytest/`` holds this file and the registry's own tests, both of which quote dataset names by
design. ``alembic/`` is generated migration history and is excluded from linting everywhere else."""


MANAGED_NAMES = tuple(sorted(set(MANAGED_DATASET_NAMES)))
"""Read out of the registry rather than copied, or the module whose job is preventing duplicated
membership lists would be guarded by one: a sixth managed dataset would be added to the registry
while this scan quietly kept looking for the first five."""

LITERAL_RE = re.compile(
    r"(?<![^/\\])(?:" + "|".join(re.escape(name) for name in MANAGED_NAMES) + r")(?![A-Za-z0-9_.-])"
)
"""Matches a managed dataset name as a whole path component inside a literal -- the old registries
spelled these as ``'/ix-applications/'``, ``f'{pool}/ix-apps/'`` and ``r'[^/]+/\\.system($|/)'``, so
an equality test would have missed every one of them.

Both boundaries carry weight, because a name that is merely adjacent to a managed one is a name the
registry answers *False* for, and flagging it turns this scan into a tax on rewording log lines.
On the left, only a separator or the start of the literal may precede the name, which is what keeps
``boot-pool-2`` and ``.ix-apps`` out; a backslash counts as a separator because the replication
registry spelled its needle as regex source, ``r"[^/]+/\\.system($|/)"``, where the name follows one.
On the right, ``-`` and ``.`` are excluded along with the identifier characters, which is what keeps
``tank/ix-apps-data``, ``.truenas_containers-old`` and dotted module paths such as
``system.system_dataset`` out."""

SYMBOL_RE = re.compile(
    r"(internal|invalid|excluded?|reserved|hidden|protected|forbidden|banned|skip(?:ped)?|"
    r"ignored?|restricted|blocked|managed|omit(?:ted)?)_?(path|dataset)s?",
    re.IGNORECASE,
)
"""Matches registry-shaped symbol names. Catches four of the five originals by name alone:
``INTERNAL_PATHS``, ``has_internal_path``, ``INTERNAL_DATASETS``, ``is_internal_dataset`` and
``INVALID_DATASETS``. The alternation is wider than what exists today because the cost of a name
nobody uses is nothing, while the cost of a miss is a sixth registry: ``skip``, in particular, has
to be spelled with an optional group, or ``skipped?`` reads as ``skippe`` plus an optional ``d`` and
never matches the bare ``skip_paths`` that a sixth registry is most likely to be called."""

REGISTRY_INTERNALS = (
    "MANAGED_DATASET_NAMES",
    "SYSTEM_DS_NAME",
    "APPS_DS_NAME",
    "LEGACY_APPS_DS_NAME",
    "CONTAINER_DS_NAME",
)
"""The registry's names, as opposed to its predicates. Callers ask a predicate; anyone reading the
list or a bare name out of the registry is deriving a second membership set from it, which is how
the five originals came to disagree -- and the literal scan cannot see it, because no name is
spelled."""


LITERAL_ALLOWLIST = {
    "plugins/boot/pool_ops.py": "boot: owns the boot pool",
    "plugins/catalog/utils.py": "apps: owns the ix-apps dataset",
    "plugins/cloud_sync/rclone.py": "not converged: rclone filter lines, not a membership test",
    "plugins/docker/state_utils.py": "apps: owns the ix-apps and ix-applications datasets",
    "plugins/docker/utils.py": "apps: owns the ix-apps and ix-applications datasets",
    "plugins/pool_/export.py": "not converged: post-export leftover-directory cleanup, should use the registry",
    "plugins/pool_/import_pool.py": "not converged: names one dataset to skip, should use the registry",
    "plugins/sysdataset.py": "sysdataset: owns the .system dataset",
    "plugins/system_dataset/hierarchy.py": "sysdataset: owns the .system dataset",
    "plugins/system_dataset/mount.py": "sysdataset: owns the .system dataset",
    "plugins/zettarepl.py": "not converged: builds a zettarepl exclusion string, not a membership test",
    "utils/boot/pool.py": "boot: owns the boot pool, and defines the names the registry imports",
}

SYMBOL_ALLOWLIST = {
    "exclude_internal_datasets": "flag on pool.dataset.query_impl, selects the dataset-listing view",
    "exclude_internal_paths": "flag on zfs.resource.query, selects the ZFS-listing view",
    "__should_exclude_internal_paths": (
        "the auto-opt-out: naming a managed path explicitly turns the filter off for that query"
    ),
    "deny_protected_path": "the mutation guard, which asks the registry rather than answering itself",
}
"""Symbols that consume a view rather than define one. These are flags and guards, not registries."""

REGISTRY_INTERNALS_ALLOWLIST = {
    "plugins/container/dataset.py": "containers: owns the container dataset",
    "plugins/container/utils.py": "containers: owns the container dataset",
    "plugins/pool_/dataset.py": (
        "not converged: the post-create mount branch compares a full dataset path against the bare "
        "component, so it never fires and the container dataset takes the plain-mount path instead"
    ),
}


def _iter_source_files() -> list[tuple[str, ast.Module]]:
    """Every parsed module under ``middlewared/`` that a registry could hide in."""
    found = []
    for path in sorted(MIDDLEWARED_ROOT.rglob("*.py")):
        relative = path.relative_to(MIDDLEWARED_ROOT).as_posix()
        if relative.startswith(SKIPPED_TREES):
            continue
        found.append((relative, ast.parse(path.read_text())))
    return found


SOURCE_FILES = _iter_source_files()


def _docstring_nodes(tree: ast.Module) -> set[int]:
    """Identity of every docstring constant, so prose does not count as a spelling."""
    nodes = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) or not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            nodes.add(id(first.value))
    return nodes


def _string_literals(tree: ast.Module) -> list[str]:
    """Every non-docstring string constant, including the pieces of an f-string.

    ``ast.walk`` descends into :class:`ast.JoinedStr`, so the literal halves of ``f"{pool}/ix-apps"``
    arrive here as ordinary constants -- which is how a registry written with f-strings gets caught.
    """
    docstrings = _docstring_nodes(tree)
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings
    ]


def _symbol_names(tree: ast.Module) -> list[str]:
    """Every name a module defines or refers to."""
    names = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
        elif isinstance(node, ast.arg):
            names.append(node.arg)
        elif isinstance(node, ast.keyword) and node.arg is not None:
            names.append(node.arg)
    return names


def test_managed_dataset_names_are_only_spelled_by_their_owners():
    """No module outside the registry names a managed dataset unless it owns it."""
    offenders = {}
    for relative, tree in SOURCE_FILES:
        if relative == REGISTRY_MODULE:
            continue
        hits = sorted({literal for literal in _string_literals(tree) if LITERAL_RE.search(literal)})
        if hits:
            offenders[relative] = hits

    unexpected = {path: hits for path, hits in offenders.items() if path not in LITERAL_ALLOWLIST}
    assert not unexpected, (
        "these modules spell a managed dataset name inline; use a predicate from "
        f"middlewared.utils.zfs.managed_datasets, or add the module to LITERAL_ALLOWLIST with the "
        f"reason it owns the dataset: {unexpected}"
    )

    stale = sorted(set(LITERAL_ALLOWLIST) - set(offenders))
    assert not stale, f"LITERAL_ALLOWLIST entries no longer match anything and should be dropped: {stale}"


def test_no_module_defines_a_registry_shaped_symbol():
    """No module grows a symbol named like an internal-path list."""
    offenders = {}
    for relative, tree in SOURCE_FILES:
        if relative == REGISTRY_MODULE:
            continue
        hits = sorted({name for name in _symbol_names(tree) if SYMBOL_RE.search(name) and name not in SYMBOL_ALLOWLIST})
        if hits:
            offenders[relative] = hits

    assert not offenders, (
        "these symbols look like a second registry of managed datasets; ask "
        f"middlewared.utils.zfs.managed_datasets instead: {offenders}"
    )

    seen = {name for _, tree in SOURCE_FILES for name in _symbol_names(tree)}
    stale = sorted(set(SYMBOL_ALLOWLIST) - seen)
    assert not stale, f"SYMBOL_ALLOWLIST entries no longer match anything and should be dropped: {stale}"


def test_registry_internals_stay_inside_the_registry():
    """Nobody derives their own membership set from the registry's names."""
    stale = [name for name in REGISTRY_INTERNALS if not hasattr(managed_datasets, name)]
    assert not stale, (
        "REGISTRY_INTERNALS names things the registry no longer has, so this scan is guarding "
        f"nothing where it thinks it is guarding something: {stale}"
    )

    offenders = {}
    for relative, tree in SOURCE_FILES:
        if relative == REGISTRY_MODULE:
            continue
        hits = sorted(set(_symbol_names(tree)).intersection(REGISTRY_INTERNALS))
        if hits:
            offenders[relative] = hits

    unexpected = {path: hits for path, hits in offenders.items() if path not in REGISTRY_INTERNALS_ALLOWLIST}
    assert not unexpected, (
        "these modules read the registry's names rather than calling one of its predicates, which "
        "is how a second registry gets built on top of the first; use a predicate, or add the "
        f"module to REGISTRY_INTERNALS_ALLOWLIST with the reason it owns the dataset: {unexpected}"
    )

    stale = sorted(set(REGISTRY_INTERNALS_ALLOWLIST) - set(offenders))
    assert not stale, f"REGISTRY_INTERNALS_ALLOWLIST entries no longer match anything and should be dropped: {stale}"


# The old registries, spelled the way they were spelled, so that a scan which has stopped catching
# them fails here rather than staying silently green. Every entry below was copied off one of the
# five before they were consolidated.
ORIGINAL_REGISTRY_SYMBOLS = (
    "INTERNAL_PATHS",
    "has_internal_path",
    "INTERNAL_DATASETS",
    "is_internal_dataset",
    "INVALID_DATASETS",
)

ORIGINAL_REGISTRY_LITERALS = (
    ".system",
    "ix-apps",
    "ix-applications",
    ".truenas_containers",
    "/.system",
    "/ix-apps",
    "/ix-applications/",
    "boot-pool/",
    r"boot-pool($|/)",
    r"freenas-boot($|/)",
    r"[^/]+/\.system($|/)",
)
"""The last of these is why the lookbehind treats a backslash as a separator: the replication
registry held a compiled regex, so the name it needed follows an escape rather than a slash."""

UNMANAGED_LOOKALIKES = (
    "boot-pool-2",
    "freenas-boot-2",
    "tank/ix-apps-data",
    "tank/ix-appsdata",
    "tank/myix-apps",
    "tank/ix-applications-old",
    "tank/.truenas_containers-old",
    "tank/.systembackup",
    ".ix-apps",
    "ix-apps-backup-",
    "middlewared.plugins.system.system_dataset",
    "org.freedesktop.systemd1",
)


@pytest.mark.parametrize("name", ORIGINAL_REGISTRY_SYMBOLS)
def test_symbol_scan_still_catches_the_names_the_originals_used(name):
    """The regex is only as good as the spellings it matches, and it has been wrong before.

    ``skipped?`` reads as ``skippe`` plus an optional ``d``, so for a while the scan matched neither
    ``skip_paths`` nor ``SKIP_DATASETS`` -- the two most natural names for a sixth registry -- and
    nothing said so, because no module happened to be named either.
    """
    assert SYMBOL_RE.search(name)


@pytest.mark.parametrize("literal", ORIGINAL_REGISTRY_LITERALS)
def test_literal_scan_still_catches_the_spellings_the_originals_used(literal):
    assert LITERAL_RE.search(literal)


@pytest.mark.parametrize("literal", UNMANAGED_LOOKALIKES)
def test_literal_scan_ignores_names_the_registry_answers_false_for(literal):
    """A name adjacent to a managed one belongs to a user, so flagging it is a false positive that
    makes rewording a log line fail a test about registries."""
    assert not LITERAL_RE.search(literal)
