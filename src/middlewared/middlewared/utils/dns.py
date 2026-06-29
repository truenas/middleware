from collections.abc import Callable
from dataclasses import dataclass
import ipaddress
from subprocess import CompletedProcess
from typing import Any


@dataclass(frozen=True)
class NSUpdatePlan:
    """The set of nsupdate transactions derived from a list of record ops.

    A DNS UPDATE message targets exactly one zone, and a reverse name's zone is
    a server-side delegation that cannot be derived from the address. Rather than
    try to determine it, the records are split into independent transactions and
    nsupdate resolves each transaction's zone itself (via an SOA lookup):

    * ``forward`` -- the A / AAAA directives. They share the host's forward zone
      and are submitted together as a single transaction.
    * ``reverse`` -- ``(reverse_pointer, directive)`` pairs, one per PTR record,
      each submitted as its own transaction. Isolating every PTR guarantees two
      records from different reverse zones can never share a transaction (which
      the server would reject with NOTZONE), without us having to know where any
      zone is cut.
    """

    forward: list[str]
    reverse: list[tuple[str, str]]


@dataclass(frozen=True)
class NSUpdateResult:
    """Outcome of running an :class:`NSUpdatePlan`.

    ``forward_error`` holds the nsupdate error output when the (critical) forward
    transaction failed, otherwise ``None``. ``ptr_failures`` pairs each failed
    reverse pointer with its error output; PTR failures are non-fatal.
    """

    forward_error: str | None
    ptr_failures: list[tuple[str, str]]


def nsupdate_directive(command: str, name: str, ttl: int, rtype: str, rdata: str) -> str:
    """Build a single nsupdate ``update`` directive line (newline terminated)."""
    return " ".join(["update", command.lower(), name, str(ttl), rtype, rdata, "\n"])


def build_nsupdate_plan(ops: list[dict[str, Any]]) -> NSUpdatePlan:
    """Split record ops into a single forward transaction and one transaction
    per PTR record. Each op carries its own ``command`` and ``ttl``, so a reverse
    directive is always built from the op that produced it."""
    forward = []
    reverse = []
    for entry in ops:
        addr = ipaddress.ip_address(entry["address"])
        forward.append(
            nsupdate_directive(entry["command"], entry["name"], entry["ttl"], entry["type"], addr.compressed)
        )
        if entry["do_ptr"]:
            reverse.append(
                (
                    addr.reverse_pointer,
                    nsupdate_directive(entry["command"], addr.reverse_pointer, entry["ttl"], "PTR", entry["name"]),
                )
            )

    return NSUpdatePlan(forward=forward, reverse=reverse)


def run_nsupdate_plan(plan: NSUpdatePlan, send: Callable[[list[str]], CompletedProcess[bytes]]) -> NSUpdateResult:
    """Execute ``plan`` one transaction at a time using ``send``.

    ``send`` takes the directive lines for a single transaction and returns a
    completed process exposing ``returncode`` (int) and ``stderr`` (bytes).

    The forward transaction is critical: if it fails the reverse records are not
    attempted and its error is returned in :attr:`NSUpdateResult.forward_error`.
    Each PTR is attempted independently so one failing reverse zone cannot abort
    the rest; any PTR failures are collected for the caller to surface."""
    proc = send(plan.forward)
    if proc.returncode:
        return NSUpdateResult(forward_error=proc.stderr.decode(), ptr_failures=[])

    ptr_failures = []
    for reverse_pointer, directive in plan.reverse:
        proc = send([directive])
        if proc.returncode:
            ptr_failures.append((reverse_pointer, proc.stderr.decode().strip()))

    return NSUpdateResult(forward_error=None, ptr_failures=ptr_failures)
