from collections import defaultdict
import ipaddress
import logging
import os

from middlewared.utils import run

logger = logging.getLogger(__name__)


async def get_exports(config, shares, kerberos_keytabs):
    networks_pool = defaultdict(lambda: defaultdict(lambda: 0))

    result = []

    if config["v4"]:
        if config["v4_krb"] or kerberos_keytabs:
            result.append("V4: / -sec=krb5:krb5i:krb5p")
        else:
            result.append("V4: / -sec=sys")

    for share in shares:
        if share["paths"]:
            share = build_share(config, share, networks_pool)
            if share:
                result.append(share)

    return "\n".join(result) + "\n"


def build_share(config, share, networks_pool):
    if share["paths"]:
        result = list(share["paths"])

        if share["alldirs"]:
            result.append("-alldirs")

        if share["ro"]:
            result.append("-ro")

        if share["quiet"]:
            result.append("-quiet")

        if share["mapall_user"]:
            s = f'-mapall="{share["mapall_user"]}"'
            if share["mapall_group"]:
                s += f':"{share["mapall_group"]}"'
            result.append(s)
        elif share["maproot_user"]:
            s = f'-maproot="{share["maproot_user"]}"'
            if share["maproot_group"]:
                s += f':"{share["maproot_group"]}"'
            result.append(s)

        if config["v4"] and share["security"]:
            result.append("-sec=" + ":".join([s.lower() for s in share["security"]]))

        targets = build_share_targets(share, networks_pool)

        if targets:
            result.extend(targets)

            return " ".join(result)


def build_share_targets(share, networks_pool):
    result = []

    try:
        dev = os.stat(share["paths"][0]).st_dev
    except Exception as e:
        logger.warning("Unable to stat {share['paths'][0]:r}: {e}")
    else:
        for network in share["networks"]:
            try:
                network = ipaddress.ip_network(network, strict=False)
            except Exception as e:
                logger.warning(f"Invalid network: {network} ({e})")
            else:
                inc = networks_pool[dev][network]
                networks_pool[dev][network] += 1
                if networks_pool[dev][network] > 2 ** (32 - network.prefixlen):
                    logger.warning(f"No space for network {network} on path {share['paths'][0]}")
                    continue

                result.append("-network " + str(network.network_address + inc) + "/" + str(network.prefixlen))

        for host in share["hosts"]:
            try:
                network = ipaddress.ip_network(f"{host}/32")
            except Exception as e:
                logger.warning(f"Invalid IP address: {host} ({e})")
            else:
                networks_pool[dev][network] += 1
                if networks_pool[dev][network] > 2 ** (32 - network.prefixlen):
                    logger.warning(f"No space for host {host} on path {share['paths'][0]}")
                    continue

                networks_pool[dev][network] += 1
                result.append(host)

    return result


async def render(service, middleware):
    config = await middleware.call("nfs.config")

    shares = await middleware.call("sharing.nfs.query")

    kerberos_keytabs = await middleware.call("datastore.query", "directoryservice.kerberoskeytab")

    with open("/etc/exports", "w") as f:
        f.write(await get_exports(config, shares, kerberos_keytabs))

    try:
        os.unlink("/etc/nfsd.virtualhost")
    except Exception:
        pass

    if config["v4_krb"] or kerberos_keytabs:
        gc = await middleware.call("datastore.config", "network.globalconfiguration")
        if gc["gc_hostname_virtual"] and gc["gc_domain"]:
            with open("/etc/nfsd.virtualhost", "w") as f:
                f.write(f'{gc["gc_hostname_virtual"]}.{gc["gc_domain"]}')

            await run("service", "nfsd", "restart", check=False)
            await run("service", "gssd", "restart", check=False)

    await run("service", "mountd", "quietreload", check=False)
