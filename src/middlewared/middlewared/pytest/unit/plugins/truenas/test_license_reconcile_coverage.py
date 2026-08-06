"""
Guard against a license-sensitive `etc` group with no `LicenseReconcileDelegate` behind it.

A group whose rendered output depends on the license, but which nothing re-renders when the
license changes, leaves stale config on disk indefinitely -- until some unrelated event happens
to regenerate the group, or the machine reboots. That failure is invisible: the config is
syntactically fine, the service is up, and only the behaviour is wrong. It is the exact bug the
reconcile mechanism was built to close, and nothing about the mechanism stops the next renderer
from reintroducing it.

Be clear about what this file does and does not catch.

Half one reads the renderers under `etc_files/` and the helper modules under `utils/` that they
call, and finds *direct* license reads: `render_ctx['failover.licensed']` and friends, and
in-template `middleware.call_sync('failover.status')`. Each hit is mapped back to the `EtcGroup`
that owns the file and that group is required to be covered. A new template that reads the
license this way cannot be added without this test failing.

Half one is blind to the far more common shape: a ctx method that reads the license *inside its
own implementation*. `smb.generate_smb_configuration` checks an entitlement in its own body;
`nfs.config` masks a stored column against one in its `datastore_extend`. Nothing in the renderer
text mentions the license, so no amount of scanning `etc_files/` will see it. There is no
mechanical way to find those short of resolving every ctx method's full call graph, which is why
half two is a hand-maintained inventory carrying written prose rather than a bare list of names:
the prose is the only place the indirect route is recorded, and it is what tells the next person
whether a group they are changing is license-derived.

So: this test proves that every group anyone has *noticed* is license-sensitive is covered, and
that new direct reads cannot slip in unnoticed. It does not prove that the set of license-
sensitive groups is complete. Adding an entitlement check inside an existing ctx method still
requires a human to come back here and write it down.
"""

import importlib
import re
from pathlib import Path
from types import MappingProxyType
from typing import NamedTuple

import middlewared
from middlewared.common.license_reconcile import LicenseReconcileDelegate
from middlewared.plugins.etc import EtcService, RendererType


MIDDLEWARED_ROOT = Path(middlewared.__file__).resolve().parent
ETC_FILES_DIR = MIDDLEWARED_ROOT / "etc_files"
UTILS_DIR = MIDDLEWARED_ROOT / "utils"
PLUGINS_DIR = MIDDLEWARED_ROOT / "plugins"

# `utils/license` and `utils/entitlements` are the license machinery itself. Every line in them
# is a license read by construction, and none of them renders anything.
UTILS_EXCLUDED = ("license", "entitlements")

# `utils/` modules cannot be attributed to an `etc` group by path -- they are libraries, and the
# only thing tying them to a group is that some entry's renderer imports them. Keyed by path
# relative to `utils/`.
UTILS_MODULE_GROUPS = MappingProxyType(
    {
        # imported by `etc_files/lio.py`, the sole entry of the `lio` group
        "lio/config.py": "lio",
        # imported by `etc_files/nvmet_kernel.py` and `etc_files/nvmet_spdk.py`, the two entries of
        # the `nvmet` group; `render_common` is the half they share
        "nvmet/kernel.py": "nvmet",
        "nvmet/spdk.py": "nvmet",
        "nvmet/render_common.py": "nvmet",
    }
)

# The render context keys whose value is derived from the license. `failover.licensed` is the
# license read itself; `failover.status` returns SINGLE unconditionally while it is false; and
# `truenas.entitlements.check` is the general entitlement query.
LICENSE_CTX_KEYS = ("failover.licensed", "failover.status", "truenas.entitlements.check")
_KEY_ALTERNATION = "|".join(re.escape(key) for key in LICENSE_CTX_KEYS)

# `render_ctx['failover.licensed']` and `render_ctx.get("failover.status", "SINGLE")` alike
RENDER_CTX_READ = re.compile(rf"""render_ctx(?:\[|\.get\()\s*(['"])({_KEY_ALTERNATION})\1""")
# `middleware.call_sync('failover.licensed')` from inside a template, and the async form
DIRECT_CALL = re.compile(rf"""\.call(?:_sync)?\(\s*(['"])({_KEY_ALTERNATION})\1""")

# `... 'truenas.license.register_reconcile_delegate', SomeDelegate())`
REGISTRATION = re.compile(r"""register_reconcile_delegate['"]\s*,\s*(\w+)\s*\(\s*\)""")


#
# Half two: the hand-maintained inventory. One entry per license-sensitive `etc` group, each
# carrying prose explaining what the license actually changes about that group's output. Adding
# an entry here without a delegate to match, or a delegate without an entry, fails the test.
#
LICENSE_SENSITIVE_ETC_GROUPS = MappingProxyType(
    {
        "rc": (
            "`etc_files/systemd.py:13` reads `failover.licensed` directly, and line 25 uses it to "
            "force the `scst` unit disabled on a licensed system regardless of what the services "
            "table says. Which units come up at boot therefore changes with the license. The "
            "renderer returns None and applies the unit state over systemd's dbus API rather than "
            "writing a file, so nothing downstream notices that it is out of date."
        ),
        "ctdb": (
            "Neither entry exists at all unless the system is failover licensed: "
            "`etc_files/ctdb/nodes.mako:4` and `etc_files/ctdb/ctdb.conf.mako:3` both raise "
            "`FileShouldNotExist` when `render_ctx['failover.licensed']` is false, which makes "
            "`etc.generate` unlink the output file rather than write it. The presence of the nodes "
            "file is what decides whether ctdb will start, so the license gates the daemon rather "
            "than merely tuning its config."
        ),
        "keepalived": (
            "`etc_files/keepalived.conf.mako:2` calls `failover.licensed` itself -- the group "
            "declares no ctx at all -- and the template returns without emitting anything when the "
            "answer is no. An unlicensed system ends up with an empty keepalived config and a "
            "licensed one with a full VRRP instance per interface."
        ),
        "user": (
            "`etc_files/local/sudoers.mako:36` emits `Defaults log_subcmds` and "
            "`Defaults log_format=json` only when `render_ctx['truenas.entitlements.check'].entitled` "
            "is true; the check is bound against `LicenseFeature.SUPPORT` in `plugins/etc.py:252`. "
            "Installing a license has to turn sudo command auditing on, and nothing else in the "
            "group -- passwd, group, shadow, subuid/subgid, aliases -- varies with the license. A "
            "security control that silently is not applied is the worst way for this to fail."
        ),
        "cron": (
            "`etc_files/cron.d/middlewared.mako:19` calls `failover.status` itself rather than "
            "taking it from ctx, and unless the answer is SINGLE or MASTER the file loses every "
            "user cronjob, rsync task, cloud sync, cloud backup, scrub schedule, the resilver "
            "priority window and the automatic update download. `failover.status` reaches the "
            "license through `plugins/failover_/status.py:17`, which returns SINGLE the moment "
            "`failover.licensed` is false, so a node that renders the standby version of this file "
            "silently stops running every scheduled task on the system."
        ),
        "discovery": (
            "Every one of the six entries opens by raising `FileShouldNotExist` when "
            "`render_ctx['failover.status']` is neither SINGLE nor MASTER -- see "
            "`etc_files/local/truenas-discovery/truenas-discoveryd.conf.py:9` and the five "
            "`services.d` fragments -- so the whole service announcement config is removed from disk "
            "on a standby node, and `truenas-discoveryd.conf.py:18` picks the advertised hostname "
            "off the same value. The license is one step back: `plugins/failover_/status.py:17` "
            "returns SINGLE unconditionally while `failover.licensed` is false."
        ),
        "nfsd": (
            "Indirect, and invisible to half one. `etc_files/nfs.conf.mako:66` emits `rdma = y` and "
            "`rdma-port = 20049` off `config['rdma']`, which comes from the `nfs.config` ctx method. "
            "`nfs.config` runs `nfs_extend` as its `datastore_extend`, and `plugins/nfs.py:194` "
            "masks the stored `rdma` column against `nfs.rdma_capable` (`plugins/nfs.py:173`), which "
            "asks `rdma.capable_protocols` (`plugins/rdma/rdma.py:148`), which returns nothing at "
            "all unless the `RDMA` entitlement is held. So a system whose stored config asks for NFS "
            "over RDMA renders it off while unlicensed and has to have it rendered back on when the "
            "license arrives. The group's other entries do not vary with the license."
        ),
        "smb": (
            "Indirect, and invisible to half one. The group's single ctx method, "
            "`smb.generate_smb_configuration`, reads the license twice inside its own body and "
            "neither read appears anywhere in `local/smb4.conf.mako`. At `plugins/smb.py:237` it "
            "checks the `SMB_FASTPATH` entitlement, which becomes the values of "
            "`zfs_core:zfs_integrity_streams` and `zfs_core:zfs_block_cloning`. At "
            "`plugins/smb.py:236` it calls `smb.bindip_choices`, which at `plugins/smb.py:291` "
            "returns failover virtual IPs on a licensed HA system and ordinary in-use addresses "
            "otherwise -- so gaining or losing the license can leave smbd bound to the wrong "
            "addresses."
        ),
        "scst": (
            "Part direct, part not. `etc_files/scst.conf.mako:162` and `:164` read "
            "`failover.licensed` and `failover.status` out of ctx to decide whether the ALUA device "
            "group and target group sections are written at all. The part half one cannot see is "
            "`fc.capable`, ctx on this group at `plugins/etc.py:421`, which is an entitlement check "
            "on `FIBRECHANNEL` (`plugins/fc/fc.py:40`) and'd with the presence of a QLogic HBA -- so "
            "on an appliance that has the card it flips purely with the license, and when it is "
            "false the template emits no `TARGET_DRIVER qla2x00t` section, which is to say every "
            "Fibre Channel target on the box vanishes from the rendered config."
        ),
        "lio": (
            "Part direct, part not. The group's single entry is a python renderer that hands off to "
            "`utils/lio/config.py`, which reads `failover.status` at line 379 and `failover.licensed` "
            "at line 1014, the latter deciding whether Fibre Channel WWPNs are emitted at all. Two "
            "further routes are indirect: `fc.capable` is ctx at `plugins/etc.py:444` and gates "
            "Fibre Channel targets on the `FIBRECHANNEL` entitlement (`plugins/fc/fc.py:40`), and "
            "`iscsi.global.iser_enabled` is ctx at `plugins/etc.py:449` and resolves through "
            "`iser_capable` (`plugins/iscsi_/iscsi_global.py:302`) to `rdma.capable_protocols`, "
            "which is empty without the `RDMA` entitlement -- so losing the license turns iSER off "
            "on every portal."
        ),
        "nvmet": (
            "Part direct, part not. The group's two python renderers read the license out of ctx in "
            "several places, among them `utils/nvmet/kernel.py:198`, "
            "`utils/nvmet/render_common.py:66` and `utils/nvmet/spdk.py:174`. What half one cannot "
            "see is that three of the group's ctx methods are themselves license derived. "
            "`nvmet.global.ana_enabled` and `nvmet.global.ana_active` both return False outright "
            "when `failover.licensed` is false (`plugins/nvmet/global.py:72`), which decides which "
            "ports exist and whether each carries a per-node ANA group. "
            "`nvmet.global.rdma_enabled`, ctx at `plugins/etc.py:348`, resolves through "
            "`rdma_capable` (`plugins/nvmet/global.py:134`) to `rdma.capable_protocols` and so to "
            "the `RDMA` entitlement, and `NvmetPortSubsysConfig.create_links` refuses to link a "
            "subsystem to an RDMA port when it is false."
        ),
    }
)


def _module_name(path: Path) -> str:
    """`.../middlewared/plugins/cron/__init__.py` -> `middlewared.plugins.cron`."""
    parts = list(path.relative_to(MIDDLEWARED_ROOT.parent).parts)
    parts[-1] = parts[-1].removesuffix(".py")
    if parts[-1] == "__init__":
        parts.pop()

    return ".".join(parts)


def registered_delegates() -> list[LicenseReconcileDelegate]:
    """
    Every delegate class that some plugin's `setup()` hands to `register_reconcile_delegate`.

    Found by scanning the plugin sources for the registration call rather than by importing every
    plugin, so that a delegate added in a module this test has never heard of is still picked up.
    Only the modules that do register something get imported.
    """
    delegates = []
    for path in sorted(PLUGINS_DIR.rglob("*.py")):
        names = sorted(set(REGISTRATION.findall(path.read_text())))
        if not names:
            continue

        module = importlib.import_module(_module_name(path))
        for name in names:
            delegate = getattr(module, name)
            assert issubclass(delegate, LicenseReconcileDelegate), f"{name} in {path}"
            delegates.append(delegate())

    return delegates


def etc_group_sources() -> dict[str, set[str]]:
    """
    Map every renderer source file, relative to `etc_files/`, to the groups that render it.

    A handful of files (`shadow.mako`, `subuid.mako`, `subgid.mako`) are rendered by more than one
    group, hence the set.
    """
    sources: dict[str, set[str]] = {}
    for group_name, group in EtcService.GROUPS.items():
        for entry in group.entries:
            suffix = ".mako" if entry.renderer_type is RendererType.MAKO else ".py"
            sources.setdefault((entry.local_path or entry.path) + suffix, set()).add(group_name)

    return sources


class LicenseRead(NamedTuple):
    # path relative to `middlewared/`, e.g. `etc_files/ctdb/nodes.mako`
    source: str
    line: int
    # one of LICENSE_CTX_KEYS
    key: str

    def __str__(self) -> str:
        return f"{self.source}:{self.line} {self.key}"


def license_reads(path: Path, source: str) -> list[LicenseRead]:
    """Return every direct license read in `path`."""
    text = path.read_text()
    hits = []
    for regex in (RENDER_CTX_READ, DIRECT_CALL):
        for match in regex.finditer(text):
            hits.append(LicenseRead(source, text.count("\n", 0, match.start()) + 1, match.group(2)))

    return sorted(hits)


def direct_license_reads() -> dict[str, list[LicenseRead]]:
    """
    Map each `etc` group to the direct license reads found in the code that renders it.

    Fails outright on a hit that cannot be attributed to a group, because an unattributable hit is
    a coverage hole this test cannot reason about, not something to quietly drop.
    """
    sources = etc_group_sources()
    found: dict[str, list[LicenseRead]] = {}

    for path in sorted(ETC_FILES_DIR.rglob("*")):
        if not path.is_file() or path.suffix not in (".mako", ".py"):
            continue

        relative = str(path.relative_to(ETC_FILES_DIR))
        if hits := license_reads(path, f"etc_files/{relative}"):
            owners = sources.get(relative)
            assert owners, (
                f"{relative} reads the license but is not registered as an entry of any EtcGroup "
                f"in plugins/etc.py, so there is no group to hold responsible for re-rendering it"
            )
            for group in owners:
                found.setdefault(group, []).extend(hits)

    for path in sorted(UTILS_DIR.rglob("*.py")):
        relative = str(path.relative_to(UTILS_DIR))
        if relative.split("/")[0] in UTILS_EXCLUDED:
            continue

        if hits := license_reads(path, f"utils/{relative}"):
            owner = UTILS_MODULE_GROUPS.get(relative)
            assert owner, (
                f"utils/{relative} reads the license out of a render context but is not in "
                f"UTILS_MODULE_GROUPS, so this test cannot tell which etc group renders through "
                f"it. Add it there."
            )
            found.setdefault(owner, []).extend(hits)

    return found


def test_inventory_matches_the_registered_delegates():
    """
    The inventory and the delegates are two statements of the same fact, so they have to agree.

    A group in one and not the other means either a subsystem declared itself license sensitive
    and nobody wrote down why, or somebody documented a group that nothing actually reconciles.
    """
    claimed = {group for delegate in registered_delegates() for group in delegate.etc_groups}

    assert set(LICENSE_SENSITIVE_ETC_GROUPS) == claimed


def test_every_group_with_a_direct_license_read_is_in_the_inventory():
    """
    The half that bites on its own: a renderer that reads the license and whose group nobody has
    claimed fails here, without anyone having to remember this file exists.
    """
    found = direct_license_reads()

    uncovered = {
        group: [str(read) for read in reads]
        for group, reads in found.items()
        if group not in LICENSE_SENSITIVE_ETC_GROUPS
    }
    assert not uncovered, (
        f"these etc groups render code that reads the license but have no "
        f"LicenseReconcileDelegate, so their config goes stale after a license change: {uncovered}"
    )


def test_the_matcher_still_matches():
    """
    Guard the guard. A matcher that has stopped matching makes every other assertion in this file
    pass vacuously, so pin one live example of each syntax it has to recognise. Deliberately
    checked by file and key rather than by line, so that editing any of these templates does not
    fail this test for no reason.
    """
    found = {read for reads in direct_license_reads().values() for read in reads}
    seen = {(read.source, read.key) for read in found}

    for expected in (
        # `render_ctx['failover.licensed']`
        ("etc_files/ctdb/nodes.mako", "failover.licensed"),
        # `render_ctx['truenas.entitlements.check'].entitled`
        ("etc_files/local/sudoers.mako", "truenas.entitlements.check"),
        # `render_ctx['failover.status']` from a python renderer
        ("etc_files/local/truenas-discovery/truenas-discoveryd.conf.py", "failover.status"),
        # `render_ctx.get("failover.status", "SINGLE")`, double quoted
        ("utils/lio/config.py", "failover.status"),
        # in-template `middleware.call_sync('failover.licensed')`
        ("etc_files/keepalived.conf.mako", "failover.licensed"),
        # in-template `middleware.call_sync("failover.status")`, double quoted
        ("etc_files/cron.d/middlewared.mako", "failover.status"),
        # `await middleware.call('failover.licensed')` from a python renderer
        ("etc_files/systemd.py", "failover.licensed"),
    ):
        assert expected in seen, expected


def test_every_inventory_entry_explains_itself():
    """
    The prose is the entire point of half two -- it is the only record of the indirect reads that
    no scan can find. An entry without one is a name in a list.
    """
    for group, reason in LICENSE_SENSITIVE_ETC_GROUPS.items():
        assert reason.strip(), group
