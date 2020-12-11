import logging

from middlewared.utils import run

logger = logging.getLogger(__name__)


async def get_exports(middleware, config, shares, has_nfs_principal):
    result = []

    sec = await middleware.call("nfs.sec", config, has_nfs_principal)
    if sec:
        result.append(f"V4: / -sec={':'.join(sec)}")

    for share in shares:
        if share['locked']:
            middleware.logger.debug(
                'Skipping generation of %r NFS share as the underlying resource is locked', share['id']
            )
            await middleware.call('sharing.nfs.generate_locked_alert', share['id'])
            continue

        if share["paths"]:
            result.extend(build_share(config, share))

    return "\n".join(result) + "\n"


def build_share(config, share):
    if share["paths"]:
        result = list(share["paths"])

        if share["alldirs"]:
            result.append("-alldirs")

        if share["ro"]:
            result.append("-ro")

        if share["quiet"]:
            result.append("-quiet")

        if share["mapall_user"]:
            s = '-mapall="' + share["mapall_user"].replace('\\', '\\\\') + '"'
            if share["mapall_group"]:
                s += ':"' + share["mapall_group"].replace('\\', '\\\\') + '"'
            result.append(s)
        elif share["maproot_user"]:
            s = '-maproot="' + share["maproot_user"].replace('\\', '\\\\') + '"'
            if share["maproot_group"]:
                s += ':"' + share["maproot_group"].replace('\\', '\\\\') + '"'
            result.append(s)

        if config["v4"] and share["security"]:
            result.append("-sec=" + ":".join([s.lower() for s in share["security"]]))

        targets = build_share_targets(share)
        if targets:
            return [" ".join(result + [target])
                    for target in targets]
        else:
            return [" ".join(result)]

    return []


def build_share_targets(share):
    result = []

    for network in share["networks"]:
        result.append("-network " + network)

    if share["hosts"]:
        result.append(" ".join(share["hosts"]))

    return result


async def render(service, middleware):
    config = await middleware.call("nfs.config")

    shares = await middleware.call("sharing.nfs.query", [["enabled", "=", True]])

    has_nfs_principal = await middleware.call('kerberos.keytab.has_nfs_principal')

    with open("/etc/exports", "w") as f:
        f.write(await get_exports(middleware, config, shares, has_nfs_principal))

    await run("service", "mountd", "quietreload", check=False)
