import ipaddress
from typing import Any


def nsupdate_directive(command: str, name: str, ttl: int, rtype: str, rdata: str) -> str:
    """Build a single nsupdate ``update`` directive line (newline terminated)."""
    return " ".join(["update", command.lower(), name, str(ttl), rtype, rdata, "\n"])


def build_nsupdate_payload(ops: list[dict[str, Any]]) -> str:
    """Build the command input for a single nsupdate invocation from record ops.

    The forward (A / AAAA) records share the host's forward zone and are sent as
    one transaction. Each PTR record gets its own transaction (its own ``send``):
    a DNS UPDATE message targets exactly one zone, so batching PTRs from
    different reverse zones -- e.g. IPv4 ``in-addr.arpa`` and IPv6 ``ip6.arpa`` --
    makes the server reject the out-of-zone records with NOTZONE and fail the
    whole update. Splitting the ``send`` blocks (rather than splitting into
    separate nsupdate invocations) keeps every record under one GSS-TSIG
    negotiation, and one exit code, so the caller's existing failure handling and
    retries are unchanged. Each PTR is built from the op that produced it, so its
    command and ttl are its own.
    """
    forward = []
    reverse = []
    for entry in ops:
        addr = ipaddress.ip_address(entry["address"])
        forward.append(
            nsupdate_directive(entry["command"], entry["name"], entry["ttl"], entry["type"], addr.compressed)
        )
        if entry["do_ptr"]:
            reverse.append(
                nsupdate_directive(entry["command"], addr.reverse_pointer, entry["ttl"], "PTR", entry["name"])
            )

    lines = forward + ["send\n"]
    for directive in reverse:
        lines += [directive, "send\n"]

    return "".join(lines)
