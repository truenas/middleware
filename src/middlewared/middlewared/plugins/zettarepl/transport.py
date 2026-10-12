from __future__ import annotations

from contextlib import asynccontextmanager
import errno
import socket
from typing import TYPE_CHECKING, Any, AsyncIterator, Literal

import paramiko.ssh_exception
from zettarepl.transport.create import create_transport

from middlewared.api.current import SSHCredentialsEntry
from middlewared.service_exception import CallError

if TYPE_CHECKING:
    from zettarepl.transport.interface import Shell

    from middlewared.service import ServiceContext

Transport = Literal["SSH", "SSH+NETCAT", "LOCAL"]


@asynccontextmanager
async def handle_ssh_exceptions() -> AsyncIterator[None]:
    try:
        yield
    except paramiko.ssh_exception.BadHostKeyException as e:
        fingerprint = ":".join([hex(c)[2:] for c in e.key.get_fingerprint()])
        raise CallError(
            "Remote host identification has changed. Someone could be eavesdropping on you right now (man-in-the-"
            "middle attack)! It is also possible that a host key has just been changed. The fingerprint for the "
            f"RSA key sent by the remote host is {fingerprint}. Please edit your SSH connection and click "
            '"Discover Remote Host Key" to resolve this issue.',
            errno=errno.EACCES,
        )
    except (
        socket.timeout,
        paramiko.ssh_exception.NoValidConnectionsError,
        paramiko.ssh_exception.SSHException,
        IOError,
        OSError,
    ) as e:
        raise CallError(repr(e).replace("[Errno None] ", ""), errno=errno.EACCES)


@asynccontextmanager
async def get_zettarepl_shell(
    context: ServiceContext,
    transport: Transport,
    ssh_credentials: int | None,
) -> AsyncIterator[Shell]:
    if transport != "LOCAL":
        await context.middleware.call("network.general.will_perform_activity", "replication")

    if transport == "SSH+NETCAT":
        # There is no difference shell-wise, but `define_transport` for `SSH+NETCAT` will fail if we don't
        # supply `netcat_active_side` and other parameters which are totally unrelated here.
        transport = "SSH"

    transport_definition = await define_transport(context, transport, ssh_credentials)
    transport_object = create_transport(transport_definition)
    shell = transport_object.shell(transport_object)
    try:
        yield shell
    finally:
        await context.middleware.run_in_thread(shell.close)


async def define_transport(
    context: ServiceContext,
    transport: Transport,
    ssh_credentials: int | None = None,
    netcat_active_side: str | None = None,
    netcat_active_side_listen_address: str | None = None,
    netcat_active_side_port_min: int | None = None,
    netcat_active_side_port_max: int | None = None,
    netcat_passive_side_connect_address: str | None = None,
    sudo: bool = False,
) -> dict[str, Any]:
    if transport not in ["SSH", "SSH+NETCAT"]:
        return dict(type="local")

    if ssh_credentials is None:
        raise CallError(f"You should pass SSH credentials for {transport} transport")

    credentials = await context.call2(context.s.keychaincredential.get_of_type, ssh_credentials, "SSH_CREDENTIALS")

    transport_definition = dict(type="ssh", **await define_ssh_transport(context, credentials), sudo=sudo)

    if transport == "SSH+NETCAT":
        assert netcat_active_side is not None
        transport_definition["type"] = "ssh+netcat"
        transport_definition["active-side"] = netcat_active_side.lower()
        if netcat_active_side_listen_address is not None:
            transport_definition["active-side-listen-address"] = netcat_active_side_listen_address
        if netcat_active_side_port_min is not None:
            transport_definition["active-side-min-port"] = netcat_active_side_port_min
        if netcat_active_side_port_max is not None:
            transport_definition["active-side-max-port"] = netcat_active_side_port_max
        if netcat_passive_side_connect_address is not None:
            transport_definition["passive-side-connect-address"] = netcat_passive_side_connect_address

    return transport_definition


async def define_ssh_transport(context: ServiceContext, credentials: SSHCredentialsEntry) -> dict[str, Any]:
    attributes = credentials.attributes.get_secret_value()
    try:
        key_pair = await context.call2(context.s.keychaincredential.get_of_type, attributes.private_key, "SSH_KEY_PAIR")
    except CallError as e:
        raise CallError(f"Error while querying SSH key pair for credentials {credentials.id}: {e!s}")

    transport = {
        "hostname": attributes.host,
        "port": attributes.port,
        "username": attributes.username,
        "private-key": key_pair.attributes.get_secret_value().private_key,
        "host-key": attributes.remote_host_key,
        "connect-timeout": attributes.connect_timeout,
    }

    if (await context.call2(context.s.system.security.config)).enable_fips:
        transport["cipher"] = "fips"

    return transport
