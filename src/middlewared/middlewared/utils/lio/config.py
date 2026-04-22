"""
LIO (Linux I/O target) configfs reconciler.

Computes the desired state from render_ctx, then adds what is missing, updates
what has changed, and deletes what is stale.  All operations are direct pathlib
writes to /sys/kernel/config/target/; no rtslib-fb dependency.

Configfs tree
-------------
/sys/kernel/config/target/
+-- core/
|   +-- iblock_0/
|   |   +-- {extent}/             storage object (block device)
|   |       +-- udev_path         write device path to open
|   |       +-- enable            write "1" to activate
|   |       +-- wwn/vpd_unit_serial
|   |       +-- alua/
|   |           +-- default_tg_pt_gp/          auto-created; non-HA only
|   |           |   +-- alua_access_state      write ALUA_STATE value
|   |           +-- controller_A/              HA only (mkdir to create)
|   |           |   +-- tg_pt_gp_id            write 101
|   |           |   +-- alua_access_state      write ALUA_STATE value
|   |           +-- controller_B/              HA only (mkdir to create)
|   |               +-- tg_pt_gp_id            write 102
|   |               +-- alua_access_state      write ALUA_STATE value
|   +-- fileio_0/
|       +-- {extent}/             storage object (file/zvol via file I/O)
|           +-- fd_dev_name
|           +-- enable
|           +-- wwn/vpd_unit_serial
|           +-- alua/             same structure as iblock_0 above
+-- iscsi/
|   +-- {iqn}/                    iSCSI target
|       +-- tpgt_{tag}/           TPG; tag = portal["tag"], NOT hardcoded to 1
|           +-- enable
|           +-- param/            negotiation parameters
|           +-- portals/
|           |   +-- {ip}:{port}/  listen address
|           +-- lun/
|           |   +-- lun_{id}/
|           |       +-- {alias}          symlink -> core/{backstore}/{extent}/
|           |       +-- alua_tg_pt_gp   HA only: write controller_A or controller_B
|           +-- acls/
|               +-- {initiator}/  one dir per allowed initiator IQN
|                   +-- auth/     CHAP credentials
|                   +-- lun_{id}/
|                       +-- default  symlink -> ../../lun/lun_{id}/
+-- qla2xxx/                      FC fabric (tcm_qla2xxx)
    +-- {wwpn}/                   FC target; WWPN in colon-hex
        +-- tpgt_1/               always tag 1 -- FC has exactly one TPG
            +-- enable
            +-- lun/
            |   +-- lun_{id}/
            |       +-- {alias}          symlink -> core/{backstore}/{extent}/
            |       +-- alua_tg_pt_gp   HA only: write controller_A or controller_B
            +-- acls/
                +-- {initiator}/  one dir per allowed initiator WWPN
                    +-- lun_{id}/
                        +-- default  symlink -> ../../lun/lun_{id}/
"""

import os
import pathlib
import subprocess
import time
from collections import defaultdict
from contextlib import contextmanager

from middlewared.plugins.fc.utils import wwn_as_colon_hex
from middlewared.utils.iscsi.constants import (
    ALUA_GROUP_A,
    ALUA_GROUP_B,
    ALUA_GROUP_ID_A,
    ALUA_GROUP_ID_B,
    ALUA_STATE,
)


LIO_CONFIG_DIR = pathlib.Path("/sys/kernel/config/target")

# Storage backstores
IBLOCK_DIR = LIO_CONFIG_DIR / "core" / "iblock_0"
FILEIO_DIR = LIO_CONFIG_DIR / "core" / "fileio_0"


def sanitize_lio_extent(name: str) -> str:
    """Sanitize an extent name for use as a LIO configfs directory name.

    LIO configfs directory names cannot contain '/' (interpreted as a path
    separator by the VFS).  Replace with '-', mirroring what SCST does.
    """
    return name.replace("/", "-")


# Fabric directories (created on demand via configfs mkdir, not at module load)
ISCSI_DIR = LIO_CONFIG_DIR / "iscsi"
FC_DIR = LIO_CONFIG_DIR / "qla2xxx"

# Kernel module presence paths
_SYSMOD = pathlib.Path("/sys/module")
MOD_ISCSI_TARGET = _SYSMOD / "iscsi_target_mod"
MOD_TCM_QLA2XXX = _SYSMOD / "tcm_qla2xxx"
MOD_IB_ISERT = _SYSMOD / "ib_isert"
MOD_TARGET_CORE = _SYSMOD / "target_core_mod"
MOD_TCM_IBLOCK = _SYSMOD / "target_core_iblock"
MOD_TCM_FILE = _SYSMOD / "target_core_file"
MOD_TCM_PSCSI = _SYSMOD / "target_core_pscsi"
MOD_TCM_USER = _SYSMOD / "target_core_user"
MOD_LIO_HA = _SYSMOD / "lio_ha"

# lio_ha TCP port (matches LIO_HA_DEFAULT_PORT in lio_ha.h)
LIO_HA_PORT = 999

# lio_ha configfs subsystem directory (present when the lio_ha module is loaded)
LIO_HA_DIR = pathlib.Path("/sys/kernel/config/lio_ha")

# ALUA default group name (always present, created by kernel on SO creation)
ALUA_DEFAULT_GROUP = "default_tg_pt_gp"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: pathlib.Path, value: str):
    """Write a value to a configfs attribute, creating the path as needed."""
    path.write_text(f"{value}\n")


def _read(path: pathlib.Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def _wait_for(path: pathlib.Path, retries: int = 10) -> bool:
    """Wait for a configfs file to appear after creating a directory."""
    while not path.exists() and retries > 0:
        time.sleep(0.5)
        retries -= 1
    return path.exists()


def _write_if_changed(path: pathlib.Path, value: str):
    """Write value only if it differs from the current content."""
    current = _read(path)
    if current != str(value):
        _write(path, value)


def _write_auth_cred(path: pathlib.Path, value: str):
    r"""Write a CHAP credential without appending a newline.

    LIO's auth store functions (userid, password, etc.) do not strip the
    trailing newline that _write() appends.  The kernel would then store
    "user\n" and the subsequent CHAP_N strlen comparison would fail.

    A read-compare guard cannot be used here: _read() calls .strip(), so
    a stored "user\n" reads back as "user" -- identical to the correct
    "user" -- and the write would be skipped, leaving the broken value in
    place.  Always write unconditionally for these attributes.
    """
    path.write_text((value or "").rstrip())


def _write_vpd_serial(path: pathlib.Path, value: str):
    """Write vpd_unit_serial, accounting for the kernel's read-back prefix.

    The kernel show function returns "T10 VPD Unit Serial Number: <serial>",
    so a plain string comparison would always mismatch.  Strip the prefix
    before comparing to avoid a spurious write that would return EINVAL once
    the storage object is exported (export_count > 0).
    """
    current = _read(path)
    _VPD_SERIAL_PREFIX = "T10 VPD Unit Serial Number: "
    if current.startswith(_VPD_SERIAL_PREFIX):
        current = current[len(_VPD_SERIAL_PREFIX):]
    if current != value:
        _write(path, value)


def _extent_device_path(extent: dict) -> str | None:
    """Return the actual device/file path for an extent, or None if unavailable."""
    if extent["type"] == "DISK":
        disk = extent.get("disk") or extent.get("path", "")
        if disk:
            return os.path.join("/dev", disk)
    elif extent["type"] == "FILE":
        return extent.get("path")
    return None


def _so_dir(extent: dict) -> pathlib.Path:
    """Return the storage object directory for an extent."""
    if extent["type"] == "DISK":
        return IBLOCK_DIR / sanitize_lio_extent(extent["name"])
    else:
        return FILEIO_DIR / sanitize_lio_extent(extent["name"])


def _so_path(extent: dict) -> pathlib.Path:
    """Return the absolute configfs path for the storage object (same as _so_dir)."""
    return _so_dir(extent)


def _naa_to_vpd_components(naa: str) -> tuple[str, str] | None:
    """
    Derive LIO vpd_unit_serial and company_id from a stored TrueNAS NAA.

    TrueNAS NAA format: '0x6589cfc000000' + sha256[0:19]
    = '0x' + 32 hex chars (NAA type nibble + 6-char OUI + 25-char vendor-specific)

    LIO's spc_gen_naa_6h_vendor_specific() builds VPD page 0x83 NAA type 6 from:
      - company_id (24-bit OUI): nibbles 1-6 of the NAA
      - vpd_unit_serial hex chars: nibbles 7-31 (vendor-specific field)

    Reverse-engineering: set company_id = int(naa_hex[1:7], 16) and
    vpd_unit_serial = naa_hex[7:32] so that LIO reconstructs the exact same NAA.

    Returns (vpd_unit_serial, company_id_hex_str) or None if naa is invalid.
    """
    if not naa:
        return None
    h = naa.lower()
    if h.startswith("0x"):
        h = h[2:]
    if len(h) != 32 or h[0] != "6":
        return None
    company_id = h[1:7]  # 6 hex chars = 24-bit OUI
    vpd_serial = h[7:32]  # 25 vendor-specific nibbles
    return vpd_serial, f"0x{company_id}"


def _fc_wwpn(fcport: dict, node: str, licensed: bool) -> str | None:
    """
    Return the WWPN (colon-hex) to use for this node.
    Non-HA: always use wwpn.
    HA: node A -> wwpn, node B -> wwpn_b.
    """
    if not licensed:
        return wwn_as_colon_hex(fcport["wwpn"])
    if node == "B":
        return wwn_as_colon_hex(fcport["wwpn_b"])
    return wwn_as_colon_hex(fcport["wwpn"])


# ---------------------------------------------------------------------------
# Storage objects
# ---------------------------------------------------------------------------


@contextmanager
def _storage_objects(render_ctx: dict):
    """
    Reconcile iblock and fileio storage objects.

    Creates before yield, deletes after yield (so LUN symlinks referencing
    these objects are removed first by inner context managers).
    """
    # Compute desired state: name -> extent
    desired = {}
    for extent in render_ctx["iscsi.extent.query"]:
        if extent.get("locked"):
            continue
        device_path = _extent_device_path(extent)
        if not device_path or not os.path.exists(device_path):
            continue
        desired[sanitize_lio_extent(extent["name"])] = extent

    # Compute live state across both backstores
    live_iblock = set(os.listdir(IBLOCK_DIR)) if IBLOCK_DIR.exists() else set()
    live_fileio = set(os.listdir(FILEIO_DIR)) if FILEIO_DIR.exists() else set()
    live = live_iblock | live_fileio

    add_names = set(desired) - live
    remove_names = live - set(desired)

    # Create new storage objects
    for name in add_names:
        extent = desired[name]
        so_dir = _so_dir(extent)
        so_dir.mkdir(parents=True, exist_ok=True)
        _configure_storage_object(so_dir, extent, render_ctx)

    # Update existing storage objects (identity or ALUA state may have changed)
    for name in set(desired) & live:
        extent = desired[name]
        so_dir = _so_dir(extent)
        _update_storage_object_attrs(so_dir, extent, render_ctx)

    yield

    # Delete stale storage objects after LUN symlinks have been removed
    for name in remove_names:
        if name in live_iblock:
            so_dir = IBLOCK_DIR / name
        else:
            so_dir = FILEIO_DIR / name
        _delete_storage_object(so_dir)


def _configure_storage_object(so_dir: pathlib.Path, extent: dict, render_ctx: dict):
    """Write configfs attributes for a newly created storage object."""
    device_path = _extent_device_path(extent)
    control = so_dir / "control"

    if extent["type"] == "DISK":
        # iblock: write device path via udev_path file and control knob
        if not _wait_for(control):
            raise RuntimeError(f"LIO configfs: {control} never appeared")
        _write(control, f"udev_path={device_path}")
        udev_path_file = so_dir / "udev_path"
        # udev_path_file is a secondary confirmation attribute; best-effort write only
        if _wait_for(udev_path_file):
            _write(udev_path_file, device_path)
        if extent.get("ro"):
            _write(control, "readonly=1")
        else:
            _write(control, "readonly=0")
    else:
        # fileio: write device path and size via control knob
        if not _wait_for(control):
            raise RuntimeError(f"LIO configfs: {control} never appeared")
        size = extent.get("filesize") or 0
        if size:
            _write(control, f"fd_dev_name={device_path},fd_dev_size={size}")
        else:
            _write(control, f"fd_dev_name={device_path}")
        if extent.get("ro"):
            _write(control, "fd_dev_readonly=1")

    # Set serial and identity attributes (wwn/ appears after control write)
    _set_storage_object_identity(so_dir, extent)

    # Enable the storage object
    enable = so_dir / "enable"
    if not _wait_for(enable):
        raise RuntimeError(f"LIO configfs: {enable} never appeared")
    _write(enable, "1")

    # Configure ALUA groups (after enable so alua/ is populated)
    _configure_alua(so_dir, render_ctx)


def _set_storage_object_identity(so_dir: pathlib.Path, extent: dict):
    """Write VPD serial and product identity attributes.

    LIO's spc_gen_naa_6h_vendor_specific() derives the VPD page 0x83 NAA type 6
    from company_id (OUI) + hex digits of vpd_unit_serial.  We reverse-engineer
    the stored TrueNAS NAA to recover those two fields so LIO emits the exact
    same NAA that SCST would.  Both must be written before the storage object is
    enabled (the kernel gates writes with export_count == 0).
    """
    wwn_dir = so_dir / "wwn"
    if not _wait_for(wwn_dir):
        raise RuntimeError(f"LIO configfs: {wwn_dir} never appeared")

    components = _naa_to_vpd_components(extent.get("naa") or "")
    if components:
        vpd_serial_str, company_id_hex = components
        company_id_path = wwn_dir / "company_id"
        if company_id_path.exists():
            _write_if_changed(company_id_path, company_id_hex)
        vpd_serial_path = wwn_dir / "vpd_unit_serial"
        # vpd_unit_serial appears shortly after wwn_dir; best-effort write only
        if _wait_for(vpd_serial_path):
            _write_vpd_serial(vpd_serial_path, vpd_serial_str)
    else:
        # No valid NAA -- fall back to the human-readable serial from the DB.
        serial = extent.get("serial") or ""
        if serial:
            vpd_serial_path = wwn_dir / "vpd_unit_serial"
            # vpd_unit_serial appears shortly after wwn_dir; best-effort write only
            if _wait_for(vpd_serial_path):
                _write_vpd_serial(vpd_serial_path, serial)

    vendor_id = wwn_dir / "vendor_id"
    if vendor_id.exists():
        _write_if_changed(vendor_id, (extent.get("vendor") or "TrueNAS")[:8])

    product_id_path = wwn_dir / "product_id"
    if product_id_path.exists():
        _write_if_changed(
            product_id_path, (extent.get("product_id") or "iSCSI Disk")[:16]
        )


def _configure_alua(so_dir: pathlib.Path, render_ctx: dict):
    """Configure ALUA groups for a storage object.

    Non-HA (SINGLE): the kernel auto-creates default_tg_pt_gp with state
    ACTIVE_OPTIMIZED (0).  We write it explicitly so the intent is clear and so the
    correct state is restored if something externally altered it.

    HA (MASTER/BACKUP): create controller_A and controller_B groups under alua/, set
    their tg_pt_gp_id values to match the SCST group IDs (101/102), and write the
    access state according to the 4-row state table:

      MASTER  + synced:     local=ACTIVE_OPTIMIZED   remote=NONOPTIMIZED
      MASTER  + other:      local=ACTIVE_OPTIMIZED   remote=TRANSITIONING
      BACKUP  + synced:     local=NONOPTIMIZED       remote=ACTIVE_OPTIMIZED
      BACKUP  + other:      local=TRANSITIONING      remote=ACTIVE_OPTIMIZED

    "local" is the controller group for this node (controller_A on node A,
    controller_B on node B); "remote" is the other node's group.

    ha_state is read live from LIO_HA_DIR so the reconciler always reflects
    the current link state rather than stale render_ctx data.
    """
    failover_status = render_ctx.get("failover.status", "SINGLE")
    alua_enabled = render_ctx.get("iscsi.global.config", {}).get("alua")

    if failover_status == "SINGLE" or not alua_enabled:
        alua_dir = so_dir / "alua" / ALUA_DEFAULT_GROUP
        if not alua_dir.exists():
            return
        state_path = alua_dir / "alua_access_state"
        if state_path.exists():
            _write_if_changed(state_path, str(ALUA_STATE.OPTIMIZED))
        # Clean up any controller groups left from a previous HA ALUA config.
        # Whether the kernel auto-reassigns LUN ports to default_tg_pt_gp on
        # rmdir is untested; if it does not, the rmdir will fail and the groups
        # will remain until the next full service stop (teardown removes them
        # as part of SO deletion).
        for group_name in (ALUA_GROUP_A, ALUA_GROUP_B):
            group_dir = so_dir / "alua" / group_name
            if group_dir.exists():
                try:
                    group_dir.rmdir()
                except OSError:
                    pass
        return

    # HA path
    node = render_ctx.get("failover.node", "A")
    is_master = failover_status == "MASTER"

    # Read current ha_state live from configfs so the state table is accurate
    # even if the reconciler runs between a ha_state transition and the event
    # handler that would otherwise trigger a state write.
    try:
        ha_state = (LIO_HA_DIR / "ha_state").read_text().strip()
    except OSError:
        ha_state = "disconnected"
    synced = ha_state == "synced"

    if node == "A":
        local_group, local_id = ALUA_GROUP_A, ALUA_GROUP_ID_A
        remote_group, remote_id = ALUA_GROUP_B, ALUA_GROUP_ID_B
    else:
        local_group, local_id = ALUA_GROUP_B, ALUA_GROUP_ID_B
        remote_group, remote_id = ALUA_GROUP_A, ALUA_GROUP_ID_A

    if is_master:
        local_state = ALUA_STATE.OPTIMIZED
        remote_state = ALUA_STATE.NONOPTIMIZED if synced else ALUA_STATE.TRANSITIONING
    else:
        local_state = ALUA_STATE.NONOPTIMIZED if synced else ALUA_STATE.TRANSITIONING
        remote_state = ALUA_STATE.OPTIMIZED

    alua_dir = so_dir / "alua"
    if not alua_dir.exists():
        return

    for group_name, group_id, state in (
        (local_group, local_id, local_state),
        (remote_group, remote_id, remote_state),
    ):
        group_dir = alua_dir / group_name
        if not group_dir.exists():
            group_dir.mkdir()

        id_path = group_dir / "tg_pt_gp_id"
        if _wait_for(id_path, retries=5):
            _write_if_changed(id_path, str(group_id))

        state_path = group_dir / "alua_access_state"
        if state_path.exists():
            _write_if_changed(state_path, str(state))


def _update_storage_object_attrs(so_dir: pathlib.Path, extent: dict, render_ctx: dict):
    """Update identity attributes and ALUA state on an existing storage object."""
    _set_storage_object_identity(so_dir, extent)
    _configure_alua(so_dir, render_ctx)


def _delete_storage_object(so_dir: pathlib.Path):
    """Remove a storage object directory.

    LIO's enable attribute is write-once ("1" only); there is no disable op.
    Just rmdir directly once all LUN symlinks referencing this object are gone.
    """
    try:
        so_dir.rmdir()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# iSCSI targets
# ---------------------------------------------------------------------------


def _build_iscsi_desired(render_ctx: dict) -> dict:
    """
    Build the desired iSCSI target state from render_ctx.

    Returns a dict:
        {iqn: {
            'iqn': str,
            'tpgs': {
                tpg_tag: {
                    'tag': int,
                    'portals': [{'ip': str, 'port': int, 'iser': bool}],
                    'generate_node_acls': bool,
                    'luns': {lun_id: extent_name},
                    'acls': {initiator_iqn: {'user': str, 'password': str,
                                             'mutual_user': str, 'mutual_password': str,
                                             'luns': {lun_id: extent_name}}},
                }
            }
        }}
    """
    global_cfg = render_ctx["iscsi.global.config"]
    iser_enabled = global_cfg.get("iser", False)

    extents = {e["id"]: e for e in render_ctx["iscsi.extent.query"]}
    portals = {p["id"]: p for p in render_ctx["iscsi.portal.query"]}
    initiators = {i["id"]: i for i in render_ctx["iscsi.initiator.query"]}
    auth_by_tag = defaultdict(list)
    for a in render_ctx["iscsi.auth.query"]:
        auth_by_tag[a["tag"]].append(a)

    # LUN assignments: target_id -> {lun_id -> extent}
    target_luns = defaultdict(dict)
    for te in render_ctx["iscsi.targetextent.query"]:
        extent = extents.get(te["extent"])
        if extent and not extent.get("locked"):
            device_path = _extent_device_path(extent)
            if device_path and os.path.exists(device_path):
                target_luns[te["target"]][te["lunid"]] = extent

    desired = {}
    for target in render_ctx["iscsi.target.query"]:
        if target["mode"] == "FC":
            continue  # FC-only targets handled separately

        iqn = f"{global_cfg['basename']}:{target['name']}"
        tpgs = {}

        for group in target.get("groups", []):
            portal = portals.get(group["portal"])
            if not portal:
                continue

            tag = portal["tag"]
            initiator_group = (
                initiators.get(group["initiator"]) if group.get("initiator") else None
            )
            authmethod = group.get("authmethod", "NONE")
            auth_tag = group.get("auth")

            # Resolve CHAP credentials
            chap_entries = auth_by_tag.get(auth_tag, []) if auth_tag else []

            if tag not in tpgs:
                tpgs[tag] = {
                    "tag": tag,
                    "alias": target.get("alias") or "",
                    "portals": [],
                    "generate_node_acls": False,
                    "chap_user": "",
                    "chap_password": "",
                    "chap_mutual_user": "",
                    "chap_mutual_password": "",
                    "luns": target_luns[target["id"]],
                    "acls": {},
                }

            # Add portals (avoid duplicates)
            existing_portal_addrs = {(p["ip"], p["port"]) for p in tpgs[tag]["portals"]}
            for listen in portal.get("listen", []):
                key = (listen["ip"], listen.get("port", global_cfg["listen_port"]))
                if key not in existing_portal_addrs:
                    tpgs[tag]["portals"].append(
                        {
                            "ip": listen["ip"],
                            "port": listen.get("port", global_cfg["listen_port"]),
                            "iser": iser_enabled,
                        }
                    )
                    existing_portal_addrs.add(key)

            # ACLs
            if initiator_group is None or not initiator_group.get("initiators"):
                # Allow all: use generate_node_acls.
                # NOTE: CHAP cannot be enforced with generate_node_acls=1.  LIO
                # verifies initiator CHAP credentials from the per-ACL auth
                # directory; dynamic ACLs have empty credentials, so CHAP
                # negotiation always fails.  CHAP targets must use static ACLs
                # (a specific initiator group).  The tpgt_N/auth/ directory
                # holds the TARGET's outgoing credentials for mutual CHAP only.
                tpgs[tag]["generate_node_acls"] = True
                if authmethod in ("CHAP", "CHAP_MUTUAL") and chap_entries:
                    cred = chap_entries[0]
                    tpgs[tag]["chap_user"] = cred.get("user", "")
                    tpgs[tag]["chap_password"] = cred.get("secret", "")
                    if authmethod == "CHAP_MUTUAL":
                        tpgs[tag]["chap_mutual_user"] = cred.get("peeruser", "")
                        tpgs[tag]["chap_mutual_password"] = cred.get("peersecret", "")
            else:
                for iqn_initiator in initiator_group["initiators"]:
                    if iqn_initiator not in tpgs[tag]["acls"]:
                        tpgs[tag]["acls"][iqn_initiator] = {
                            "user": "",
                            "password": "",
                            "mutual_user": "",
                            "mutual_password": "",
                            "luns": target_luns[target["id"]],
                        }
                    acl = tpgs[tag]["acls"][iqn_initiator]
                    if authmethod in ("CHAP", "CHAP_MUTUAL") and chap_entries:
                        cred = chap_entries[0]
                        acl["user"] = cred.get("user", "")
                        acl["password"] = cred.get("secret", "")
                        if authmethod == "CHAP_MUTUAL":
                            acl["mutual_user"] = cred.get("peeruser", "")
                            acl["mutual_password"] = cred.get("peersecret", "")

        if tpgs:
            desired[iqn] = {"iqn": iqn, "tpgs": tpgs}

    return desired


@contextmanager
def _iscsi_targets(render_ctx: dict):
    """Reconcile iSCSI targets, TPGs, portals, LUNs, and ACLs."""
    if not ISCSI_DIR.exists():
        yield
        return

    desired = _build_iscsi_desired(render_ctx)
    live_targets = {e.name for e in ISCSI_DIR.iterdir() if e.is_dir()}

    add_targets = set(desired) - live_targets
    remove_targets = live_targets - set(desired)
    update_targets = set(desired) & live_targets

    # Create new targets and their full sub-tree
    for iqn in add_targets:
        target_dir = ISCSI_DIR / iqn
        target_dir.mkdir()
        _configure_iscsi_target(target_dir, desired[iqn], render_ctx)

    # Update existing targets
    for iqn in update_targets:
        target_dir = ISCSI_DIR / iqn
        _update_iscsi_target(target_dir, desired[iqn], render_ctx)

    yield

    # Remove stale targets (TPGs, LUNs, ACLs must be removed first)
    for iqn in remove_targets:
        target_dir = ISCSI_DIR / iqn
        _delete_iscsi_target(target_dir)


def _configure_iscsi_target(
    target_dir: pathlib.Path, target_cfg: dict, render_ctx: dict
):
    """Create and configure all TPGs under a new iSCSI target."""
    for tpg_cfg in target_cfg["tpgs"].values():
        _create_iscsi_tpg(target_dir, tpg_cfg, render_ctx)


def _update_iscsi_target(target_dir: pathlib.Path, target_cfg: dict, render_ctx: dict):
    """Reconcile TPGs under an existing iSCSI target."""
    live_tpgs = {
        int(d.name.split("_")[1])
        for d in target_dir.iterdir()
        if d.is_dir() and d.name.startswith("tpgt_")
    }
    desired_tags = set(target_cfg["tpgs"].keys())

    for tag in desired_tags - live_tpgs:
        _create_iscsi_tpg(target_dir, target_cfg["tpgs"][tag], render_ctx)

    for tag in desired_tags & live_tpgs:
        tpg_dir = target_dir / f"tpgt_{tag}"
        _update_iscsi_tpg(tpg_dir, target_cfg["tpgs"][tag], render_ctx)

    for tag in live_tpgs - desired_tags:
        tpg_dir = target_dir / f"tpgt_{tag}"
        _delete_iscsi_tpg(tpg_dir)


def _create_iscsi_tpg(target_dir: pathlib.Path, tpg_cfg: dict, render_ctx: dict):
    """Create a TPG and all its sub-objects.

    Note: the TPG tag comes from portal["tag"] and is not hardcoded to 1.
    A target can have multiple TPGs with different tags (one per portal group).
    All TPGs on a target share the same LUN set.  Contrast with FC targets,
    which always have exactly one TPG with tag 1.
    """
    tag = tpg_cfg["tag"]
    tpg_dir = target_dir / f"tpgt_{tag}"
    tpg_dir.mkdir()

    _set_tpg_attribs(tpg_dir, tpg_cfg)
    _set_tpg_alias(tpg_dir, tpg_cfg)
    _set_tpg_auth(tpg_dir, tpg_cfg)
    _reconcile_portals(tpg_dir, tpg_cfg)
    _reconcile_luns(tpg_dir, tpg_cfg, render_ctx)
    _reconcile_acls(tpg_dir, tpg_cfg)

    enable = tpg_dir / "enable"
    if not _wait_for(enable):
        raise RuntimeError(f"LIO configfs: {enable} never appeared")
    _write(enable, "1")


def _update_iscsi_tpg(tpg_dir: pathlib.Path, tpg_cfg: dict, render_ctx: dict):
    """Update portals, LUNs, and ACLs on an existing TPG."""
    _set_tpg_attribs(tpg_dir, tpg_cfg)
    _set_tpg_alias(tpg_dir, tpg_cfg)
    _set_tpg_auth(tpg_dir, tpg_cfg)
    _reconcile_portals(tpg_dir, tpg_cfg)
    _reconcile_luns(tpg_dir, tpg_cfg, render_ctx)
    _reconcile_acls(tpg_dir, tpg_cfg)


def _set_tpg_attribs(tpg_dir: pathlib.Path, tpg_cfg: dict):
    """Set TPG-level attributes."""
    attrib_dir = tpg_dir / "attrib"
    if not attrib_dir.exists():
        return

    generate_acls = "1" if tpg_cfg["generate_node_acls"] else "0"
    has_chap = (
        any(
            acl.get("user") or acl.get("mutual_user")
            for acl in tpg_cfg["acls"].values()
        )
        or bool(tpg_cfg.get("chap_user"))
        or bool(tpg_cfg.get("chap_mutual_user"))
    )
    for attr, val in (
        ("authentication", "1" if has_chap else "0"),
        ("generate_node_acls", generate_acls),
        ("cache_dynamic_acls", generate_acls),
        ("demo_mode_write_protect", "0"),
    ):
        p = attrib_dir / attr
        if p.exists():
            _write_if_changed(p, val)


def _set_tpg_alias(tpg_dir: pathlib.Path, tpg_cfg: dict):
    """Write TargetAlias to tpgt_N/param/TargetAlias.

    An empty string clears the alias (no TargetAlias sent in LOGIN response).
    """
    p = tpg_dir / "param" / "TargetAlias"
    if p.exists():
        _write_if_changed(p, tpg_cfg.get("alias") or "")


def _set_tpg_auth(tpg_dir: pathlib.Path, tpg_cfg: dict):
    """Write TPG-level auth credentials to tpgt_N/auth/.

    tpgt_N/auth/ holds the TARGET's outgoing credentials for mutual CHAP
    (target authenticates itself to the initiator).  These are distinct from
    the per-ACL credentials in acls/<iqn>/auth/ that verify the initiator.
    """
    auth_dir = tpg_dir / "auth"
    if not auth_dir.exists():
        return
    for attr, key in (
        ("userid", "chap_user"),
        ("password", "chap_password"),
        ("userid_mutual", "chap_mutual_user"),
        ("password_mutual", "chap_mutual_password"),
    ):
        p = auth_dir / attr
        if p.exists():
            _write_auth_cred(p, tpg_cfg.get(key, "") or "")
    authenticate_target = auth_dir / "authenticate_target"
    if authenticate_target.exists():
        _write_if_changed(
            authenticate_target, "1" if tpg_cfg.get("chap_mutual_user") else "0"
        )


def _portal_key(ip: str, port: int) -> str:
    """Return the configfs directory name for a portal."""
    # IPv6 addresses use brackets in the directory name
    if ":" in ip and not ip.startswith("["):
        return f"[{ip}]:{port}"
    return f"{ip}:{port}"


def _reconcile_portals(tpg_dir: pathlib.Path, tpg_cfg: dict):
    """Add/remove network portals in this TPG."""
    np_dir = tpg_dir / "np"
    if not np_dir.exists():
        return

    desired = {_portal_key(p["ip"], p["port"]): p for p in tpg_cfg["portals"]}
    live = set(os.listdir(np_dir))

    for key in set(desired) - live:
        p = desired[key]
        portal_dir = np_dir / key
        portal_dir.mkdir()
        # Set iSER attribute if supported — best-effort; older kernels may not expose it
        iser_path = portal_dir / "iser"
        if _wait_for(iser_path, retries=5):
            _write(iser_path, "1" if p.get("iser") else "0")

    for key in live - set(desired):
        portal_dir = np_dir / key
        try:
            portal_dir.rmdir()
        except OSError:
            pass


def _reconcile_luns(tpg_dir: pathlib.Path, tpg_cfg: dict, render_ctx: dict):
    """Reconcile LUN -> storage object associations in this TPG.

    In HA mode, each new LUN entry's alua_tg_pt_gp attribute is written with
    the local controller's group name (controller_A on node A, controller_B on
    node B), assigning the LUN to the correct ALUA target port group for this
    node.  The kernel stores the current assignment as "Group Name: {name}" on
    read, but accepts just the name on write; always written unconditionally on
    new LUN creation (no read-compare guard needed since the file only appears
    after the LUN directory is created).
    """
    lun_dir = tpg_dir / "lun"
    if not lun_dir.exists():
        return

    desired_luns = tpg_cfg["luns"]  # {lun_id: extent}
    live_lun_dirs = {
        int(d.name.split("_")[1]): d
        for d in lun_dir.iterdir()
        if d.is_dir() and d.name.startswith("lun_")
    }

    # Determine local ALUA group name for HA LUN assignment
    ha_mode = render_ctx.get("failover.status", "SINGLE") != "SINGLE"
    if ha_mode:
        node = render_ctx.get("failover.node", "A")
        local_group = ALUA_GROUP_A if node == "A" else ALUA_GROUP_B

    # Add missing LUNs
    for lun_id, extent in desired_luns.items():
        if lun_id not in live_lun_dirs:
            lun_path = lun_dir / f"lun_{lun_id}"
            lun_path.mkdir()
            so_path = _so_path(extent)
            # Create symlink: {alias} -> storage object directory
            alias = (
                f"iblock_{sanitize_lio_extent(extent['name'])}"
                if extent["type"] == "DISK"
                else f"fileio_{sanitize_lio_extent(extent['name'])}"
            )
            link = lun_path / alias
            link.symlink_to(so_path)
            # In HA mode assign the LUN to the local controller's ALUA group.
            if ha_mode:
                alua_attr = lun_path / "alua_tg_pt_gp"
                if _wait_for(alua_attr, retries=5):
                    _write(alua_attr, local_group)

    # Remove stale LUNs
    for lun_id, lun_path in live_lun_dirs.items():
        if lun_id not in desired_luns:
            # Remove the symlink inside first
            for child in lun_path.iterdir():
                if child.is_symlink():
                    child.unlink()
            try:
                lun_path.rmdir()
            except OSError:
                pass


def _reconcile_acls(tpg_dir: pathlib.Path, tpg_cfg: dict):
    """Reconcile initiator ACLs in this TPG."""
    acls_dir = tpg_dir / "acls"
    if not acls_dir.exists():
        return

    if tpg_cfg["generate_node_acls"]:
        # Allow-all: remove all explicit ACLs
        for acl_dir in list(acls_dir.iterdir()):
            if acl_dir.is_dir():
                _delete_acl(acl_dir)
        return

    desired_acls = tpg_cfg["acls"]  # {iqn: acl_cfg}
    live_acls = {d.name for d in acls_dir.iterdir() if d.is_dir()}

    for iqn in set(desired_acls) - live_acls:
        acl_dir = acls_dir / iqn
        acl_dir.mkdir()
        _configure_acl(acl_dir, desired_acls[iqn], tpg_dir)

    for iqn in set(desired_acls) & live_acls:
        acl_dir = acls_dir / iqn
        _update_acl(acl_dir, desired_acls[iqn], tpg_dir)

    for iqn in live_acls - set(desired_acls):
        _delete_acl(acls_dir / iqn)


def _configure_acl(acl_dir: pathlib.Path, acl_cfg: dict, tpg_dir: pathlib.Path):
    """Set auth and mapped LUNs on a new ACL."""
    _set_acl_auth(acl_dir, acl_cfg)
    _reconcile_mapped_luns(acl_dir, acl_cfg["luns"], tpg_dir)


def _update_acl(acl_dir: pathlib.Path, acl_cfg: dict, tpg_dir: pathlib.Path):
    """Update auth and mapped LUNs on an existing ACL."""
    _set_acl_auth(acl_dir, acl_cfg)
    _reconcile_mapped_luns(acl_dir, acl_cfg["luns"], tpg_dir)


def _set_acl_auth(acl_dir: pathlib.Path, acl_cfg: dict):
    """Write CHAP credentials to an ACL's auth/ directory."""
    auth_dir = acl_dir / "auth"
    if not auth_dir.exists():
        return

    for attr, val in (
        ("userid", acl_cfg.get("user", "")),
        ("password", acl_cfg.get("password", "")),
        ("userid_mutual", acl_cfg.get("mutual_user", "")),
        ("password_mutual", acl_cfg.get("mutual_password", "")),
    ):
        p = auth_dir / attr
        if p.exists():
            _write_auth_cred(p, val or "")


def _reconcile_mapped_luns(acl_dir: pathlib.Path, luns: dict, tpg_dir: pathlib.Path):
    """Reconcile mapped LUN entries under an ACL."""
    desired_lun_ids = set(luns.keys())
    live_mapped = {
        int(d.name.split("_")[1]): d
        for d in acl_dir.iterdir()
        if d.is_dir() and d.name.startswith("lun_")
    }

    for lun_id in desired_lun_ids - set(live_mapped):
        mapped_dir = acl_dir / f"lun_{lun_id}"
        mapped_dir.mkdir()
        # Symlink 'default' -> TPG lun/lun_N directory
        tpg_lun_path = tpg_dir / "lun" / f"lun_{lun_id}"
        link = mapped_dir / "default"
        link.symlink_to(tpg_lun_path)

    for lun_id, mapped_dir in live_mapped.items():
        if lun_id not in desired_lun_ids:
            for child in mapped_dir.iterdir():
                if child.is_symlink():
                    child.unlink()
            try:
                mapped_dir.rmdir()
            except OSError:
                pass


def _delete_acl(acl_dir: pathlib.Path):
    """Remove an ACL and all its mapped LUNs."""
    for d in list(acl_dir.iterdir()):
        if d.is_dir() and d.name.startswith("lun_"):
            for child in d.iterdir():
                if child.is_symlink():
                    child.unlink()
            try:
                d.rmdir()
            except OSError:
                pass
    try:
        acl_dir.rmdir()
    except OSError:
        pass


def _delete_iscsi_tpg(tpg_dir: pathlib.Path):
    """Remove a TPG and all its sub-objects."""
    # Remove ACLs
    acls_dir = tpg_dir / "acls"
    if acls_dir.exists():
        for acl_dir in list(acls_dir.iterdir()):
            if acl_dir.is_dir():
                _delete_acl(acl_dir)

    # Remove LUNs
    lun_dir = tpg_dir / "lun"
    if lun_dir.exists():
        for d in list(lun_dir.iterdir()):
            if d.is_dir() and d.name.startswith("lun_"):
                for child in d.iterdir():
                    if child.is_symlink():
                        child.unlink()
                try:
                    d.rmdir()
                except OSError:
                    pass

    # Remove portals
    np_dir = tpg_dir / "np"
    if np_dir.exists():
        for d in list(np_dir.iterdir()):
            if d.is_dir():
                try:
                    d.rmdir()
                except OSError:
                    pass

    # Disable and remove TPG
    enable = tpg_dir / "enable"
    if enable.exists():
        try:
            _write(enable, "0")
        except OSError:
            pass
    try:
        tpg_dir.rmdir()
    except OSError:
        pass


def _delete_iscsi_target(target_dir: pathlib.Path):
    """Remove an iSCSI target and all its TPGs."""
    for d in list(target_dir.iterdir()):
        if d.is_dir() and d.name.startswith("tpgt_"):
            _delete_iscsi_tpg(d)
    try:
        target_dir.rmdir()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# iSCSI discovery auth
# ---------------------------------------------------------------------------


@contextmanager
def _discovery_auth(render_ctx: dict):
    """Configure discovery authentication."""
    disc_auth_dir = ISCSI_DIR / "discovery_auth"
    if not disc_auth_dir.exists():
        yield
        return

    # Find the first discovery CHAP credential
    incoming_user = ""
    incoming_pass = ""
    outgoing_user = ""
    outgoing_pass = ""

    for auth in render_ctx["iscsi.auth.query"]:
        disc_auth = auth.get("discovery_auth", "NONE")
        if disc_auth in ("CHAP", "CHAP_MUTUAL"):
            if not incoming_user and auth.get("user") and auth.get("secret"):
                incoming_user = auth["user"]
                incoming_pass = auth["secret"]
                if (
                    disc_auth == "CHAP_MUTUAL"
                    and auth.get("peeruser")
                    and auth.get("peersecret")
                ):
                    outgoing_user = auth["peeruser"]
                    outgoing_pass = auth["peersecret"]
                break

    for attr, val in (
        ("userid", incoming_user),
        ("password", incoming_pass),
        ("userid_mutual", outgoing_user),
        ("password_mutual", outgoing_pass),
    ):
        p = disc_auth_dir / attr
        if p.exists():
            _write_auth_cred(p, val)

    # Enable/disable discovery auth enforcement
    enforce = disc_auth_dir / "enforce_discovery_auth"
    if enforce.exists():
        _write_if_changed(enforce, "1" if incoming_user else "0")

    yield


# ---------------------------------------------------------------------------
# FC targets
# ---------------------------------------------------------------------------


def _build_fc_desired(render_ctx: dict) -> dict:
    """
    Build the desired FC target state.

    Returns {wwpn_colon_hex: {
        'wwpn': str,
        'luns': {lun_id: extent},
        'acls': {initiator_wwpn: {'luns': {lun_id: extent}}},
    }}
    """
    if not render_ctx.get("fc.capable"):
        return {}

    extents = {e["id"]: e for e in render_ctx["iscsi.extent.query"]}
    node = render_ctx.get("failover.node", "A")
    licensed = render_ctx.get("failover.licensed", False)

    # LUN assignments: target_id -> {lun_id -> extent}
    target_luns = defaultdict(dict)
    for te in render_ctx["iscsi.targetextent.query"]:
        extent = extents.get(te["extent"])
        if extent and not extent.get("locked"):
            device_path = _extent_device_path(extent)
            if device_path and os.path.exists(device_path):
                target_luns[te["target"]][te["lunid"]] = extent

    desired = {}
    for fcport in render_ctx["fcport.query"]:
        if not fcport.get("target"):
            continue
        target = fcport["target"]
        if target.get("mode") == "ISCSI":
            continue  # iSCSI-only targets

        wwpn = _fc_wwpn(fcport, node, licensed)
        if not wwpn:
            continue

        desired[wwpn] = {
            "wwpn": wwpn,
            "luns": target_luns[target["id"]],
            "acls": {},  # FC ACLs populated from initiator groups if any
        }

    return desired


@contextmanager
def _fc_targets(render_ctx: dict):
    """Reconcile FC targets and their LUNs/ACLs."""
    if not FC_DIR.exists():
        yield
        return

    desired = _build_fc_desired(render_ctx)
    live_targets = {e.name for e in FC_DIR.iterdir() if e.is_dir()}

    add_targets = set(desired) - live_targets
    remove_targets = live_targets - set(desired)
    update_targets = set(desired) & live_targets

    for wwpn in add_targets:
        target_dir = FC_DIR / wwpn
        target_dir.mkdir()
        _configure_fc_target(target_dir, desired[wwpn], render_ctx)

    for wwpn in update_targets:
        target_dir = FC_DIR / wwpn
        _update_fc_target(target_dir, desired[wwpn], render_ctx)

    yield

    for wwpn in remove_targets:
        target_dir = FC_DIR / wwpn
        _delete_fc_target(target_dir)


def _configure_fc_target(target_dir: pathlib.Path, fc_cfg: dict, render_ctx: dict):
    """Create FC TPG (always tag 1) with LUNs.

    Note: FC targets always have exactly one TPG with tag 1.  iSCSI targets
    differ — their TPG tag comes from portal["tag"] and is not hardcoded.
    Code that manipulates TPG directories must account for this asymmetry
    (e.g. do not assume tpgt_1 when iterating iSCSI targets).
    """
    tpg_dir = target_dir / "tpgt_1"
    tpg_dir.mkdir()
    _reconcile_luns(tpg_dir, fc_cfg, render_ctx)
    _reconcile_acls(tpg_dir, fc_cfg)
    enable = tpg_dir / "enable"
    if not _wait_for(enable):
        raise RuntimeError(f"LIO configfs: {enable} never appeared")
    _write(enable, "1")


def _update_fc_target(target_dir: pathlib.Path, fc_cfg: dict, render_ctx: dict):
    """Update an existing FC target's LUNs."""
    tpg_dir = target_dir / "tpgt_1"
    if tpg_dir.exists():
        _reconcile_luns(tpg_dir, fc_cfg, render_ctx)
        _reconcile_acls(tpg_dir, fc_cfg)


def _delete_fc_target(target_dir: pathlib.Path):
    """Remove a FC target and its TPG."""
    tpg_dir = target_dir / "tpgt_1"
    if tpg_dir.exists():
        _delete_iscsi_tpg(tpg_dir)  # same cleanup logic as iSCSI TPG
    try:
        target_dir.rmdir()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def _load_modules(render_ctx: dict):
    """Load any LIO kernel modules that are not yet present.

    Presence is detected via configfs/sysfs paths that each module creates,
    avoiding a modprobe call when everything is already loaded (the common
    case on every render after first start).

      target_core_mod + iscsi_target_mod -> MOD_ISCSI_TARGET exists
      tcm_qla2xxx                        -> MOD_TCM_QLA2XXX exists
      ib_isert                           -> MOD_IB_ISERT exists
      lio_ha                             -> MOD_LIO_HA exists (alua only)

    lio_ha is loaded with module parameters rather than via modprobe -a
    because it needs per-node IP addresses and the initial forward_active
    value baked in at load time.
    """
    needed = []

    if not MOD_ISCSI_TARGET.exists():
        needed.extend(["target_core_mod", "iscsi_target_mod"])

    if render_ctx.get("fc.capable") and not MOD_TCM_QLA2XXX.exists():
        needed.append("tcm_qla2xxx")

    if render_ctx.get("iscsi.global.config", {}).get("iser"):
        if not MOD_IB_ISERT.exists():
            needed.append("ib_isert")

    if needed:
        subprocess.run(["modprobe", "-a"] + needed, capture_output=True)

    # lio_ha is loaded/unloaded separately (needs per-module parameters).
    alua_enabled = render_ctx.get("iscsi.global.config", {}).get("alua")
    if alua_enabled and not MOD_LIO_HA.exists():
        local_ip = render_ctx.get("failover.local_ip", "")
        remote_ip = render_ctx.get("failover.remote_ip", "")
        is_backup = render_ctx.get("failover.status") == "BACKUP"
        params = [
            f"default_local_addr={local_ip}",
            f"default_peer_addr={remote_ip}",
        ]
        if is_backup:
            params.append("default_forward_active=1")
        subprocess.run(["modprobe", "lio_ha"] + params, capture_output=True)
    elif not alua_enabled and MOD_LIO_HA.exists():
        subprocess.run(["modprobe", "-r", "lio_ha"], capture_output=True)


def _wait_for_iscsi_threads(timeout: float = 10.0) -> None:
    """Wait for all iscsi_target_mod kthreads to exit after target teardown.

    iscsi_target_mod spawns three thread types per connection/portal:
      iscsi_trx  -- RX thread (ISCSI_RX_THREAD_NAME, iscsi_target_core.h:26)
      iscsi_ttx  -- TX thread (ISCSI_TX_THREAD_NAME, iscsi_target_core.h:27)
      iscsi_np   -- per-portal login/accept thread (iscsi_target.c:374)

    Removing network portals and disabling TPGs triggers async teardown of
    all three.  modprobe -r must not run until they are gone -- if it does,
    the threads wake from schedule_timeout into poisoned (freed) module
    memory and the kernel panics (observed as int3 / 0xcc fill oops).

    Races with thread exit are expected: OSError from /proc reads is normal
    and is silently ignored.
    """
    _ISCSI_THREAD_NAMES = {"iscsi_trx", "iscsi_ttx", "iscsi_np"}
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        alive = False
        for comm in pathlib.Path("/proc").glob("*/task/*/comm"):
            try:
                if comm.read_text().strip() in _ISCSI_THREAD_NAMES:
                    alive = True
                    break
            except OSError:
                pass
        if not alive:
            return
        time.sleep(0.1)


def teardown_lio_config():
    """Remove all LIO configfs state.

    Deletion order mirrors the creation order in write_lio_config: targets
    before storage objects, so LUN symlinks are gone before the SOs they
    reference are removed.
    """
    if not LIO_CONFIG_DIR.exists():
        return

    # iSCSI targets (skip discovery_auth which is a file node, not a target)
    if ISCSI_DIR.exists():
        for entry in list(ISCSI_DIR.iterdir()):
            if entry.is_dir() and entry.name != "discovery_auth":
                _delete_iscsi_target(entry)
        try:
            ISCSI_DIR.rmdir()
        except OSError:
            pass

    # FC targets
    if FC_DIR.exists():
        for entry in list(FC_DIR.iterdir()):
            if entry.is_dir():
                _delete_fc_target(entry)
        try:
            FC_DIR.rmdir()
        except OSError:
            pass

    # Storage objects -- remove SOs, then the backstore group dir, then core.
    # The kernel holds a module reference on target_core_iblock / target_core_file
    # for as long as the backstore group directory (iblock_0 / fileio_0) exists,
    # even when it is empty.
    core_dir = LIO_CONFIG_DIR / "core"
    for backstore in (IBLOCK_DIR, FILEIO_DIR):
        if backstore.exists():
            for entry in list(backstore.iterdir()):
                if entry.is_dir():
                    _delete_storage_object(entry)
            try:
                backstore.rmdir()
            except OSError:
                pass
    if core_dir.exists():
        try:
            core_dir.rmdir()
        except OSError:
            pass

    # Wait for iscsi_trx kthreads to exit before unloading the module.
    # Portal removal triggers async session teardown; the threads must be
    # fully gone before modprobe -r or the kernel panics on poisoned memory.
    _wait_for_iscsi_threads()

    # Unload all LIO modules so the next start gets a clean state.
    # Order: fabric modules first (most dependent), then backends, then core.
    to_unload = []
    for mod, name in (
        (MOD_LIO_HA, "lio_ha"),  # must unload before the modules it depends on
        (MOD_IB_ISERT, "ib_isert"),
        (MOD_TCM_QLA2XXX, "tcm_qla2xxx"),
        (MOD_ISCSI_TARGET, "iscsi_target_mod"),
        (MOD_TCM_IBLOCK, "target_core_iblock"),
        (MOD_TCM_FILE, "target_core_file"),
        (MOD_TCM_PSCSI, "target_core_pscsi"),
        (MOD_TCM_USER, "target_core_user"),
        (MOD_TARGET_CORE, "target_core_mod"),
    ):
        if mod.exists():
            to_unload.append(name)
    if to_unload:
        subprocess.run(["modprobe", "-ra"] + to_unload, capture_output=True)


def write_lio_config(render_ctx: dict):
    """
    Reconcile the live LIO configfs state against the desired state.

    Context managers are nested so that:
    - Storage objects are created before targets reference them (LUNs)
    - LUN symlinks are removed before storage objects are deleted
    """
    _load_modules(render_ctx)
    if not LIO_CONFIG_DIR.exists():
        return

    # Ensure backstore directories exist
    IBLOCK_DIR.mkdir(parents=True, exist_ok=True)
    FILEIO_DIR.mkdir(parents=True, exist_ok=True)

    # Fabric dirs are created on demand via configfs mkdir (target_register_template
    # only adds to a list; the directory appears when we mkdir it here).
    if MOD_ISCSI_TARGET.exists():
        ISCSI_DIR.mkdir(exist_ok=True)
    if MOD_TCM_QLA2XXX.exists():
        FC_DIR.mkdir(exist_ok=True)

    with (
        _storage_objects(render_ctx),
        _iscsi_targets(render_ctx),
        _fc_targets(render_ctx),
        _discovery_auth(render_ctx),
    ):
        pass
