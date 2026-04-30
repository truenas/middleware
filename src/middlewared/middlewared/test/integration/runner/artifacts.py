from subprocess import PIPE, run

from middlewared.test.integration.utils.ssh import ssh

from .context import Context


def get_artifacts(ctx: Context) -> None:
    if ctx.ha:
        get_folder("/var/log", f"{ctx.artifacts}/log_nodea", "root", "testing", ctx.ip)
        get_folder("/var/log", f"{ctx.artifacts}/log_nodeb", "root", "testing", ctx.ip2)
        get_cmd_result(
            "midclt call core.get_jobs | jq .",
            f"{ctx.artifacts}/core.get_jobs_nodea.json",
            ctx.ip,
        )
        get_cmd_result(
            "midclt call core.get_jobs | jq .",
            f"{ctx.artifacts}/core.get_jobs_nodeb.json",
            ctx.ip2,
        )
        get_cmd_result("dmesg", f"{ctx.artifacts}/dmesg_nodea.json", ctx.ip)
        get_cmd_result("dmesg", f"{ctx.artifacts}/dmesg_nodeb.json", ctx.ip2)
    else:
        get_folder("/var/log", f"{ctx.artifacts}/log", "root", "testing", ctx.ip)
        get_cmd_result(
            "midclt call core.get_jobs | jq .",
            f"{ctx.artifacts}/core.get_jobs.json",
            ctx.ip,
        )
        get_cmd_result("dmesg", f"{ctx.artifacts}/dmesg.json", ctx.ip)


def get_folder(folder: str, destination: str, username: str, passwrd: str | None, host: str) -> dict[str, bool | str]:
    cmd = [] if passwrd is None else ["sshpass", "-p", passwrd]
    cmd += [
        "scp",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "VerifyHostKeyDNS=no",
        "-r",
        f"{username}@{host}:{folder}",
        destination,
    ]
    process = run(cmd, stdout=PIPE, universal_newlines=True)
    output = process.stdout
    if process.returncode != 0:
        return {"result": False, "output": output}
    else:
        return {"result": True, "output": output}


def get_cmd_result(cmd: str, target_file: str, target_ip: str) -> None:
    try:
        results = ssh(cmd, ip=target_ip)  # type: ignore[no-untyped-call]
    except Exception as exc:
        with open(f"{target_file}.error.txt", "w") as f:
            f.write(f"{target_ip}: command [{cmd}] failed: {exc}\n")
            f.flush()
    else:
        with open(target_file, "w") as f:
            f.writelines(results["stdout"])
            f.flush()
