"""Render the S3 service's configuration files.

Pure functions over plain dicts, so the output can be held against the
daemon's own example files in unit tests. The etc_files renderers call
these with the query results the etc plugin gathers.

The daemon reads every file whole: one malformed value refuses the
entire load, and at boot the service then does not start. So the rules
here mirror the daemon's reader exactly: interpolation off, no
[DEFAULT] section, lowercase keys, quoted section headings, enum values
as the daemon's lowercase tokens, and a key omitted rather than
rendered empty wherever empty would be refused.
"""

from __future__ import annotations

from configparser import RawConfigParser
import io
import ipaddress
from typing import Any

S3D_BINARY = "/usr/bin/s3d"
WILDCARD_BUCKET = "*"

RESTART_BUCKET_KEYS = (
    "dataset",
    "path",
    "permissions_model",
    "versioning",
    "object_lock",
    "object_lock_default_mode",
    "object_lock_default_days",
    "object_lock_default_years",
    "sosapi_block_size",
)
"""The bucket keys the daemon's registry consumes once at startup. A
reload that moves one, or adds or drops a bucket section, is refused
whole with "restart to apply"."""

RESTART_SERVER_KEYS = ("tls_cert", "tls_key", "region")
"""The [server] keys a reload silently leaves half applied: the TLS
listener is built at startup, and the storage engine keeps the region
it was built with."""


def _parser() -> RawConfigParser:
    # interpolation off on both sides, or a % in a secret corrupts silently
    return RawConfigParser(interpolation=None)


def _dump(parser: RawConfigParser) -> str:
    out = io.StringIO()
    parser.write(out)
    return out.getvalue()


def _lower(value: str) -> str:
    return value.lower()


def _audit_value(audit: list[str] | str) -> str:
    if audit == "ALL":
        return "all"
    return ",".join(audit)


def grant_label(name: str | None, xid: int | None) -> str:
    """The quoted NAME of a grant heading. A label the daemon never
    resolves, but a quote inside it breaks the heading grammar and an
    empty one is refused, either of which refuses the whole load."""
    label = (name or "").replace('"', "").replace("\n", "").replace("\r", "").strip()
    return label or str(xid)


def render_buckets(config: dict[str, Any], buckets: list[dict[str, Any]], audit_licensed: bool) -> str:
    """buckets.conf: the [server] globals and one section per enabled bucket.

    Every enabled bucket renders unconditionally, locked or broken dataset
    included. The daemon excludes an unmountable row at attach and answers
    503 for it; omitting the row would turn that into NoSuchBucket after a
    restart and make every later reload a refused registry change.
    """
    parser = _parser()
    parser.add_section("server")
    server = parser["server"]

    server["servers"] = str(config["servers"])
    if config["region"]:
        server["region"] = config["region"]
    server["host_id"] = config["host_id"]
    server["owner_id_seed"] = config["owner_id_seed"]
    server["log_level"] = _lower(config["log_level"])
    if config["tls_cert"] and config["tls_key"]:
        server["tls_cert"] = config["tls_cert"]
        server["tls_key"] = config["tls_key"]
    if audit_licensed:
        if config["default_audit"]:
            server["default_audit"] = _audit_value(config["default_audit"])
        server["default_audit_overflow"] = _lower(config["default_audit_overflow"])

    for bucket in buckets:
        if not bucket["enabled"]:
            continue

        section = f'bucket "{bucket["name"]}"'
        parser.add_section(section)
        row = parser[section]
        row["dataset"] = bucket["dataset"]
        row["path"] = bucket["path"]
        row["owner"] = bucket["owner_label"]
        row["owner_id"] = str(bucket["owner_id"])
        row["permissions_model"] = _lower(bucket["permissions_model"])
        row["versioning"] = _lower(bucket["versioning"])
        row["object_lock"] = "enabled" if bucket["object_lock"] else "off"
        if bucket["object_lock_default_mode"]:
            row["object_lock_default_mode"] = _lower(bucket["object_lock_default_mode"])
        if bucket["object_lock_default_days"]:
            row["object_lock_default_days"] = str(bucket["object_lock_default_days"])
        if bucket["object_lock_default_years"]:
            row["object_lock_default_years"] = str(bucket["object_lock_default_years"])
        if bucket["sosapi_block_size"]:
            row["sosapi_block_size"] = str(bucket["sosapi_block_size"])
        if audit_licensed:
            # None inherits the server default by omission; an empty list is
            # the empty mask, which must be rendered so it shadows the default
            if bucket["audit"] is not None:
                row["audit"] = _audit_value(bucket["audit"])
            if bucket["audit_overflow"]:
                row["audit_overflow"] = _lower(bucket["audit_overflow"])

    return _dump(parser)


def _grant_section(parser: RawConfigParser, grant: dict[str, Any], bucket: str) -> None:
    kind = _lower(grant["principal_type"])
    if kind == "everyone":
        section = f'grant everyone "{bucket}"'
    else:
        section = f'grant {kind} "{grant_label(grant.get("name"), grant["xid"])}" "{bucket}"'

    # a user and a group may share a label, but the same principal twice on
    # one bucket is a duplicate section the daemon refuses; validation keeps
    # a list free of those, and the last one wins here as a backstop
    if parser.has_section(section):
        parser.remove_section(section)
    parser.add_section(section)
    row = parser[section]
    if kind != "everyone":
        row["xid"] = str(grant["xid"])
    row["access"] = _lower(grant["access"])


def render_policies(config: dict[str, Any], buckets: list[dict[str, Any]]) -> str:
    """policies.conf: every enabled bucket's grants plus the wildcard rows."""
    parser = _parser()
    for bucket in buckets:
        if not bucket["enabled"]:
            continue
        for grant in bucket["grants"]:
            _grant_section(parser, grant, bucket["name"])
    for grant in config["global_grants"]:
        _grant_section(parser, grant, WILDCARD_BUCKET)
    return _dump(parser)


def render_credentials(accesskeys: list[dict[str, Any]]) -> str:
    """credentials.conf: one section per access key.

    Only an ENABLED key renders enabled. A disabled row needs neither a
    secret nor a resolvable user, which is what lets a key whose account
    is gone, or whose secret was lost, stay in the file without refusing
    the load.
    """
    parser = _parser()
    for key in accesskeys:
        section = f'credential "{key["access_key"]}"'
        parser.add_section(section)
        row = parser[section]
        if key["secret"]:
            row["secret_key"] = key["secret"]
        if key["username"]:
            row["user"] = key["username"]
        row["enabled"] = "true" if key["status"] == "ENABLED" else "false"
    return _dump(parser)


def listen_address(bindip: list[str], port: int) -> str:
    """The daemon's one listen address. An empty list is every address."""
    if not bindip:
        return f"0.0.0.0:{port}"
    ip = bindip[0]
    if isinstance(ipaddress.ip_address(ip), ipaddress.IPv6Address):
        return f"[{ip}]:{port}"
    return f"{ip}:{port}"


def render_unit_dropin(config: dict[str, Any]) -> str:
    """The systemd drop-in carrying the listen address, which is the
    unit's concern rather than the config files'. The empty ExecStart
    clears the packaged one first: a Type=simple unit refuses two."""
    return "[Service]\nExecStart=\nExecStart={} {}\n".format(
        S3D_BINARY, listen_address(config["bindip"], config["port"])
    )


def parse(text: str) -> RawConfigParser:
    parser = _parser()
    parser.read_string(text)
    return parser


def needs_restart(old_buckets: str, new_buckets: str, old_dropin: str, new_dropin: str) -> bool:
    """Whether the change between two renders is one the daemon cannot
    take on SIGHUP: a bucket section added or dropped, a registry key
    moved, a [server] key the reload leaves half applied, or a new
    listen address. Everything else is a reload."""
    if old_dropin != new_dropin:
        return True

    old, new = parse(old_buckets), parse(new_buckets)
    for key in RESTART_SERVER_KEYS:
        if old["server"].get(key) != new["server"].get(key):
            return True

    old_rows = {s: old[s] for s in old.sections() if s.startswith("bucket ")}
    new_rows = {s: new[s] for s in new.sections() if s.startswith("bucket ")}
    if old_rows.keys() != new_rows.keys():
        return True
    for section, row in new_rows.items():
        for key in RESTART_BUCKET_KEYS:
            if old_rows[section].get(key) != row.get(key):
                return True
    return False
