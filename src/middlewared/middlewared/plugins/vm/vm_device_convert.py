from __future__ import annotations

import errno
import json
import math
import os
import re
import subprocess
from typing import TYPE_CHECKING, Any

from middlewared.api.current import VMDeviceConvert, VMDiskDevice, ZFSResourceQuery
from middlewared.plugins.zfs.utils import has_internal_path
from middlewared.service import CallError, ServiceContext
from middlewared.service_exception import InstanceNotFound, ValidationError

if TYPE_CHECKING:
    from middlewared.job import Job

VALID_DISK_FORMATS = ("qcow2", "qed", "raw", "vdi", "vhdx", "vmdk")


def virtual_size_impl(schema: str, file_path: str) -> int:
    if not os.path.isabs(file_path):
        raise ValidationError(schema, f"{file_path!r} must be an absolute path.", errno.EINVAL)

    try:
        rv = subprocess.run(
            ["qemu-img", "info", "--output=json", file_path],
            capture_output=True,
            text=True,
            check=True
        )

    except subprocess.CalledProcessError as e:
        raise ValidationError(schema, f"Failed to run command to determine virtual size: {e}")
    else:
        try:
            return int(json.loads(rv.stdout)["virtual-size"])
        except KeyError:
            raise ValidationError(schema, f"Unable to determine virtual size of {file_path!r}: {rv.stdout}")
        except json.JSONDecodeError as e:
            raise ValidationError(schema, f"Failed to decode json output: {e}")


def run_convert_cmd(context: ServiceContext, cmd_args: list[str], job: Job, progress_desc: str) -> None:
    context.logger.info("Running command: %r", cmd_args)
    progress_pattern = re.compile(r"(\d+\.\d+)")
    try:
        with subprocess.Popen(
            cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as process:
            assert process.stdout is not None
            assert process.stderr is not None
            stderr_data = []
            while True:
                output = process.stdout.readline()
                if not output and process.poll() is not None:
                    break

                if output:
                    line = output.strip()
                    progress_match = progress_pattern.search(line)
                    if progress_match:
                        try:
                            progress_value = round(float(progress_match.group(1)))
                            job.set_progress(progress_value, progress_desc)
                        except ValueError:
                            context.logger.warning("Invalid progress value: %r", progress_match.group(1))
                    else:
                        context.logger.debug("qemu-img output: %r", line)

            remaining_stderr = process.stderr.read()
            if remaining_stderr:
                stderr_data.append(remaining_stderr.strip())

            return_code = process.wait()
            if return_code != 0:
                stderr_msg = "\n".join(stderr_data) if stderr_data else "No error details available"
                raise CallError(f"qemu-img convert failed: {stderr_msg}", return_code)
    except (OSError, subprocess.SubprocessError) as e:
        raise CallError(f"Failed to execute qemu-img convert: {e}")


def validate_convert_disk_image(
    context: ServiceContext, dip: str, schema: str, converting_from_image_to_zvol: bool = False,
) -> dict[str, Any] | None:
    if not dip.startswith("/mnt/") or os.path.dirname(dip) == "/mnt":
        raise ValidationError(schema, f"{dip!r} is an invalid location", errno.EINVAL)

    st = None
    try:
        st = context.middleware.call_sync("filesystem.stat", dip)
        if converting_from_image_to_zvol:
            if st["type"] != "FILE":
                raise ValidationError(schema, f"{dip!r} is not a file", errno.EINVAL)

            vfs = context.middleware.call_sync("filesystem.statfs", dip)
            if has_internal_path(vfs["source"]):
                raise ValidationError(
                    schema,
                    f'{dip!r} is in a protected system path ({vfs["source"]})',
                    errno.EACCES
                )
        else:
            # if converting from a zvol to a disk image,
            # qemu-img will create the file if it doesn't
            # exist OR it will OVERWRITE the file that exists
            raise ValidationError(
                schema,
                f"{dip!r} already exists and would be overwritten",
                errno.EEXIST
            )
    except CallError as e:
        if e.errno == errno.ENOENT:
            if converting_from_image_to_zvol:
                raise ValidationError(schema, f"{dip!r} does not exist", errno.ENOENT)
        else:
            raise e from None

    if not converting_from_image_to_zvol:
        sp = os.path.dirname(dip)
        try:
            dst = context.middleware.call_sync("filesystem.stat", os.path.dirname(sp))
            if dst["type"] != "DIRECTORY":
                raise ValidationError(schema, f"{sp!r} is not a directory", errno.EINVAL)

            vfs = context.middleware.call_sync("filesystem.statfs", dst["realpath"])
            if has_internal_path(vfs["source"]):
                raise ValidationError(
                    schema,
                    f'{sp!r} is in a protected system path ({vfs["source"]})',
                    errno.EACCES
                )
        except CallError as e:
            if e.errno == errno.ENOENT:
                raise ValidationError(schema, f"{sp!r} does not exist", errno.ENOENT)
            else:
                raise e from None
    return st


def validate_convert_zvol(
    context: ServiceContext, zvp: str, schema: str,
) -> tuple[dict[str, Any], str]:
    ptn = zvp.removeprefix("/dev/zvol/").replace("+", " ")
    ntp = os.path.join("/dev/zvol", ptn.replace(" ", "+"))
    zv = context.call_sync2(
        context.s.zfs.resource.query_impl,
        ZFSResourceQuery(paths=[ptn], properties=["volsize"])
    )
    if not zv:
        raise ValidationError(schema, f"{ptn!r} does not exist", errno.ENOENT)
    elif zv[0]["type"] != "VOLUME":
        raise ValidationError(schema, f"{ptn!r} is not a volume", errno.EINVAL)
    elif has_internal_path(ptn):
        raise ValidationError(schema, f"{ptn!r} is in a protected system path", errno.EACCES)
    elif not os.path.exists(ntp):
        raise ValidationError(schema, f"{ntp!r} does not exist", errno.ENOENT)

    for device in context.call_sync2(context.s.vm.device.query, [["attributes.dtype", "=", "DISK"]]):
        if not isinstance(device.attributes, VMDiskDevice):
            continue
        vmzv = device.attributes.path
        if vmzv and vmzv == ntp:
            try:
                vm = context.call_sync2(context.s.vm.get_instance, device.vm)
                if vm.status.state == "RUNNING":
                    raise ValidationError(
                        schema,
                        f"{vmzv!r} is part of running VM. {vm.name!r} must be stopped first",
                        errno.EBUSY
                    )
            except InstanceNotFound:
                pass

    return zv[0], ntp


def convert_disk(context: ServiceContext, job: Job, data: VMDeviceConvert) -> bool:
    """Convert between disk images and ZFS volumes."""
    schema = "vm.device.convert"
    # Determine conversion direction
    source_is_image = data.source.endswith(VALID_DISK_FORMATS)
    dest_is_image = data.destination.endswith(VALID_DISK_FORMATS)
    if (source_is_image and dest_is_image) or (not source_is_image and not dest_is_image):
        raise ValidationError(
            schema,
            "One path must be a disk image and the other must be a ZFS volume",
            errno.EINVAL
        )

    converting_from_image_to_zvol = False
    if source_is_image:
        schema += ".source"
        source_image = data.source
        zvol = data.destination
        converting_from_image_to_zvol = True
        progress_desc = "Convert to zvol progress"
    else:
        schema += ".destination"
        source_image = data.destination
        zvol = data.source
        progress_desc = "Convert to disk image progress"

    st = validate_convert_disk_image(context, source_image, schema, converting_from_image_to_zvol)
    zv, abs_zvolpath = validate_convert_zvol(context, zvol, schema)
    cmd_args = ["qemu-img", "convert", "-p"]
    if converting_from_image_to_zvol:
        assert st is not None
        vsize = virtual_size_impl(schema, st["realpath"])
        if vsize > zv["properties"]["volsize"]["value"]:
            # always convert to next whole GB.
            vshgb = max(1, math.ceil(vsize / (1024 ** 3)))
            zvhgb = max(1, math.ceil(zv["properties"]["volsize"]["value"] / (1024 ** 3)))
            raise ValidationError(
                schema,
                f"{zv['name']} too small (~{zvhgb}G). Minimum size must be {vshgb}G",
                errno.ENOSPC
            )
        cmd_args.extend(["-O", "raw", source_image, abs_zvolpath])
    else:
        dl = data.destination.lower()
        for fmt in VALID_DISK_FORMATS:
            if dl.endswith(f".{fmt}"):
                cmd_args.extend(["-f", "raw", "-O", fmt, abs_zvolpath, source_image])
                break
        else:
            raise ValidationError(
                schema,
                f'Destination must have a valid format extension: {", ".join(VALID_DISK_FORMATS)}',
                errno.EINVAL
            )

    run_convert_cmd(context, cmd_args, job, progress_desc)
    if not converting_from_image_to_zvol and st:
        # set the user/group owner to the uid/gid of the parent directory
        chown_job = context.middleware.call_sync(
            "filesystem.chown",
            {"path": data.destination, "uid": st["uid"], "gid": st["gid"]}
        )
        chown_job.wait_sync(raise_error=True)

    return True
