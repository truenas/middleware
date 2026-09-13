"""Keep every production entitlement gate spelling a feature the live policy rules on.

The endpoint answers `NOT_GATED` for a key `POLICY` does not carry rather than raising, so a
gate naming an unruled feature is silently open -- it denies nothing and says nothing. There
is no runtime complaint to notice, which is what this scan replaces.

It reads the source rather than importing it, because reaching a gate at runtime means
standing up the plugin that holds it. A scan that matched nothing would pass, so the gates it
finds are frozen below and compared as a whole: a gate that moves, loses its feature or
disappears fails here. Regenerate with `UPDATE_ENTITLEMENT_GATE_INVENTORY=1`, which prints the
replacement literal instead of asserting.
"""

import ast
import os
import pprint

from middlewared.utils.entitlements import POLICY, DerivedEntitlement, LicenseFeature
from middlewared.utils.python import get_middlewared_dir

ENDPOINT = "truenas.entitlements.check"

VOCABULARIES = {"LicenseFeature": LicenseFeature, "DerivedEntitlement": DerivedEntitlement}

# Every gate, as (path relative to the middlewared package, the vocabulary member it names).
# `None` is a site that reaches the endpoint without naming one: a `method=` string or a mock.
GATES = [
    ("etc_files/truenas_zfstierd.py", "LicenseFeature.ZFSTIER"),
    ("plugins/alert/runtime.py", "LicenseFeature.SUPPORT"),
    ("plugins/catalog/config.py", "LicenseFeature.CATALOG_ENTERPRISE_TRAIN"),
    ("plugins/catalog/config.py", "LicenseFeature.CATALOG_ENTERPRISE_TRAIN"),
    ("plugins/container/info.py", "LicenseFeature.CONTAINERS"),
    ("plugins/disk.py", "LicenseFeature.SED"),
    ("plugins/docker/service_utils.py", "LicenseFeature.APPS"),
    ("plugins/etc.py", "LicenseFeature.SUPPORT"),
    ("plugins/fc/fc.py", "LicenseFeature.FIBRECHANNEL"),
    ("plugins/iscsi_/targets.py", "LicenseFeature.FIBRECHANNEL"),
    ("plugins/kmip/config.py", "LicenseFeature.KMIP"),
    ("plugins/network.py", "LicenseFeature.NETWORK_FEC"),
    ("plugins/nfs.py", "LicenseFeature.NFS_SNAPSHOT"),
    ("plugins/nvmet/global.py", "LicenseFeature.NVMEOF_SPDK"),
    ("plugins/pool_/pool.py", "LicenseFeature.SUPPORT"),
    ("plugins/pool_/utils.py", "LicenseFeature.DEDUP"),
    ("plugins/rdma/rdma.py", "LicenseFeature.RDMA"),
    ("plugins/security/info.py", "LicenseFeature.STIG"),
    ("plugins/smb.py", "LicenseFeature.SMB_FASTPATH"),
    ("plugins/smb.py", "LicenseFeature.SMB_VEEAM"),
    ("plugins/support/__init__.py", "DerivedEntitlement.PROACTIVE_SUPPORT"),
    ("plugins/support/execute.py", "LicenseFeature.SUPPORT"),
    ("plugins/support/execute.py", "LicenseFeature.SUPPORT"),
    ("plugins/system/product.py", None),
    ("plugins/system/product.py", "LicenseFeature.SED"),
    ("plugins/system_general/update.py", "LicenseFeature.DIRECTORY_SERVICES_AUTH"),
    ("plugins/truesearch.py", "LicenseFeature.TRUESEARCH"),
    ("plugins/update_/profile_.py", "LicenseFeature.MISSION_CRITICAL"),
    ("plugins/update_/profile_.py", "LicenseFeature.MISSION_CRITICAL"),
    ("plugins/vm/info.py", "LicenseFeature.VMS"),
    ("plugins/webshare/sharing.py", "LicenseFeature.WEBSHARE"),
    ("plugins/zfs/resource_crud.py", "LicenseFeature.DEDUP"),
    ("plugins/zfs/tier.py", "LicenseFeature.ZFSTIER"),
    ("test/integration/assets/entitlements.py", None),
    ("utils/service/entitlement.py", "LicenseFeature.SED"),
]


def _literal(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _dotted(node):
    """Render an attribute chain as its dotted source text, or None if it is not one."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _names_the_endpoint(call):
    """Whether `call` hands the endpoint to something, by bound method or by name.

    A gate reaches it as `<something>.truenas.entitlements.check` passed to `call2`, and
    `plugins/etc.py` reaches it as a `method=` string on a `CtxMethod`.
    """
    for value in [*call.args, *(keyword.value for keyword in call.keywords)]:
        if _literal(value) == ENDPOINT or (_dotted(value) or "").endswith(ENDPOINT):
            return True
    return False


def _scan():
    """Return every gate as (relpath, member, lineno), and the unruled members found."""
    known = {str(key) for key in POLICY}
    gates = []
    unruled = []
    source_dir = get_middlewared_dir()
    for dirpath, dirnames, filenames in os.walk(source_dir):
        # This package holds the tests themselves, several of which name unruled features on
        # purpose to pin what the endpoint answers for one.
        dirnames[:] = [name for name in dirnames if name != "pytest"]
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=path)

            relpath = os.path.relpath(path, source_dir)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not _names_the_endpoint(node):
                    continue

                members = []
                for inner in ast.walk(node):
                    if not isinstance(inner, ast.Attribute) or not isinstance(inner.value, ast.Name):
                        continue
                    vocabulary = VOCABULARIES.get(inner.value.id)
                    if vocabulary is None:
                        continue
                    members.append(f"{inner.value.id}.{inner.attr}")
                    member = vocabulary.__members__.get(inner.attr)
                    if member is None or str(member) not in known:
                        unruled.append((relpath, node.lineno, f"{inner.value.id}.{inner.attr}"))

                gates.append((relpath, members[0] if members else None, node.lineno))

    gates.sort(key=lambda gate: (gate[0], gate[1] or "", gate[2]))
    return gates, unruled


def test_production_gates_name_a_feature_the_live_policy_rules_on():
    gates, unruled = _scan()
    found = [(relpath, member) for relpath, member, _ in gates]

    if os.environ.get("UPDATE_ENTITLEMENT_GATE_INVENTORY"):
        print(f"GATES = {pprint.pformat(found)}")
        return

    assert unruled == []
    assert found == GATES
