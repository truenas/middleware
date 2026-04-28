import sys
import textwrap

from .context import Context


def write_config(ctx: Context) -> None:
    cfg_content = textwrap.dedent(f"""\
        #!{sys.executable}

        user = "root"
        password = "{ctx.password}"
        netmask = "{ctx.netmask}"
        gateway = "{ctx.gateway}"
        vip = "{ctx.vip}"
        vm_name = {f"'{ctx.vm_name}'" if ctx.vm_name else None}
        hostname = "{ctx.hostname}"
        domain = "{ctx.domain}"
        api_url = 'http://{ctx.ip}/api/v2.0'
        interface = "{ctx.interface}"
        badNtpServer = "10.20.20.122"
        localHome = "{ctx.local_home}"
        keyPath = "{ctx.ssh_key_path}"
        pool_name = "{ctx.pool_name}"
        ha_pool_name = "ha"
        ha = {ctx.ha}
        ha_license = {ctx.ha_license!r}
        update = {ctx.update}
        artifacts = "{ctx.artifacts}"
        isns_ip = "{ctx.isns_ip}"
        extended_tests = {ctx.extended_tests}
        sshKey = "{ctx.ssh_key}"
    """)

    with open("auto_config.py", "w") as f:
        f.writelines(cfg_content)
