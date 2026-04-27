import os

from .context import Context


def set_env(ctx: Context) -> None:
    if ctx.ha and ctx.ip2:
        os.environ["controller1_ip"] = ctx.ip
        os.environ["controller2_ip"] = ctx.ip2

    if ctx.ha:
        # Set various env variables for HA, if not already set
        if not os.environ.get("virtual_ip"):
            os.environ["virtual_ip"] = ctx.vip
        if not os.environ.get("domain"):
            os.environ["domain"] = ctx.domain
        if not os.environ.get("hostname_virtual"):
            os.environ["hostname_virtual"] = ctx.hostname or ""
        if not os.environ.get("hostname"):
            os.environ["hostname"] = f"{ctx.hostname}-nodea"
        if not os.environ.get("hostname_b"):
            os.environ["hostname_b"] = f"{ctx.hostname}-nodeb"
        if not os.environ.get("primary_dns"):
            os.environ["primary_dns"] = ctx.ns1 or "10.230.0.10"
        if not os.environ.get("secondary_dns"):
            os.environ["secondary_dns"] = ctx.ns2 or "10.230.0.11"
