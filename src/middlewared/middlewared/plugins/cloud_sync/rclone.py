from __future__ import annotations

import base64
import collections
import configparser
import itertools
import json
import logging
import os
import re
import shlex
import subprocess
import tempfile
import threading
from typing import TYPE_CHECKING, Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from middlewared.api.current import CloudSyncEntry, ZFSResourceSnapshotDestroyQuery
from middlewared.job import JobCancelledException
from middlewared.plugins.cloud.crud import validate_task_attributes
from middlewared.plugins.cloud.path import check_local_path, get_remote_path
from middlewared.plugins.cloud.remotes import REMOTES
from middlewared.plugins.cloud.script import env_mapping, run_script
from middlewared.plugins.cloud.snapshot import create_snapshot
from middlewared.service import CallError
from middlewared.utils.crypto import ssl_random
from middlewared.utils.lang import undefined

if TYPE_CHECKING:
    from middlewared.api.current import (
        CloudCredentialProvider,
        CloudSyncListDirectory,
        CredentialsEntry,
    )
    from middlewared.job import Job
    from middlewared.main import Middleware


logger = logging.getLogger(__name__)

RE_TRANSF1 = re.compile(r"Transferred:\s*(?P<progress_1>.+), (?P<progress>[0-9]+)%$")
RE_TRANSF2 = re.compile(r"Transferred:\s*(?P<progress_1>.+, )(?P<progress>[0-9]+)%, (?P<progress_2>.+)$")
RE_CHECKS = re.compile(r"Checks:\s*(?P<checks>[0-9 /]+)(, (?P<progress>[0-9]+)%)?$")
RcloneConfigTuple = collections.namedtuple("RcloneConfigTuple", ["config_path", "remote_path", "extra_args"])


class RcloneConfig:
    def __init__(
        self,
        credentials: CloudCredentialProvider,
        cloud_sync: CloudSyncEntry | CloudSyncListDirectory | None = None,
    ):
        self.provider = REMOTES[credentials.type]
        self.credentials = credentials
        self.task = cloud_sync
        self.config: dict[str, Any] | None = None
        self.tmp_file: Any = None
        self.tmp_file_filter: Any = None

    def __enter__(self) -> RcloneConfigTuple:
        self.tmp_file = tempfile.NamedTemporaryFile(mode="w+")

        # Make sure only root can read it as there is sensitive data
        os.chmod(self.tmp_file.name, 0o600)

        config = {
            **{k: v for k, v in self.credentials.model_dump(expose_secrets=True).items() if v is not None},
            "type": self.provider.rclone_type,
            **self.provider.get_credentials_extra(self.credentials),
        }
        if "pass" in config:
            config["pass"] = rclone_encrypt_password(config["pass"])

        remote_path = None
        extra_args = []

        if self.task is not None:
            raw_attributes = self.task.attributes.model_dump(expose_secrets=True)
            attributes = validate_task_attributes(self.provider, raw_attributes)
            extra_args = self.provider.get_task_extra_args(attributes, self.credentials)

            config.update(dict(raw_attributes, **self.provider.get_task_extra(attributes, self.credentials)))
            for k, v in list(config.items()):
                if v is undefined:
                    config.pop(k)

            remote_path = get_remote_path(self.provider, raw_attributes)
            remote_path = f"remote:{remote_path}"

            if self.task.encryption:
                encryption_password = self.task.encryption_password.get_secret_value()
                encryption_salt = self.task.encryption_salt.get_secret_value()
                self.tmp_file.write("[encrypted]\n")
                self.tmp_file.write("type = crypt\n")
                self.tmp_file.write(f"remote = {remote_path}\n")
                self.tmp_file.write(
                    "filename_encryption = {}\n".format("standard" if self.task.filename_encryption else "off")
                )
                self.tmp_file.write("password = {}\n".format(rclone_encrypt_password(encryption_password)))
                if encryption_salt:
                    self.tmp_file.write("password2 = {}\n".format(rclone_encrypt_password(encryption_salt)))

                remote_path = "encrypted:/"

            rclone_filter = [
                "- .zfs",
                "- .zfs/**",
            ]

            if isinstance(self.task, CloudSyncEntry):
                if os.path.dirname(self.task.path.rstrip("/")) == "/mnt":
                    rclone_filter.extend(
                        [
                            "- /ix-applications",
                            "- /ix-apps",
                            "- /ix-applications/**",
                            "- /ix-apps/**",
                        ]
                    )

                for item in self.task.exclude:
                    rclone_filter.append(f"- {item}")

                if self.task.include:
                    for item in self.task.include:
                        rclone_filter.append(f"+ {item}")
                    rclone_filter.append("- *")

            self.tmp_file_filter = tempfile.NamedTemporaryFile(mode="w+")
            self.tmp_file_filter.write("\n".join(rclone_filter))
            self.tmp_file_filter.flush()
            extra_args.extend(["--filter-from", self.tmp_file_filter.name])

        self.tmp_file.write("[remote]\n")
        for k, v in config.items():
            if isinstance(v, bool):
                v = json.dumps(v)
            self.tmp_file.write(f"{k} = {v}\n")

        self.tmp_file.flush()

        self.config = config

        return RcloneConfigTuple(self.tmp_file.name, remote_path, extra_args)

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.config is not None:
            self.provider.cleanup(self.credentials, self.config)
        if self.tmp_file:
            self.tmp_file.close()
        if self.tmp_file_filter:
            self.tmp_file_filter.close()


def rclone(
    middleware: Middleware,
    job: Job,
    cloud_sync: CloudSyncEntry,
    credentials: CredentialsEntry,
    dry_run: bool,
) -> None:
    middleware.call_sync("network.general.will_perform_activity", "cloud_sync")

    # The rclone args/env are flat text, so work off plaintext dumps; the typed models flow into `RcloneConfig`.
    task = cloud_sync.model_dump(expose_secrets=True)
    provider = credentials.provider.model_dump(expose_secrets=True)

    path = task["path"]
    check_local_path(middleware, path)

    # Use a temporary file to store rclone file
    with RcloneConfig(credentials.provider, cloud_sync) as config:
        args = [
            "rclone",
            "--config",
            config.config_path,
            "-v",
            "--stats",
            "1s",
        ]

        if task["attributes"].get("fast_list"):
            args.append("--fast-list")

        if task["follow_symlinks"]:
            args.append("-L")

        if task["transfers"]:
            args.extend(["--transfers", str(task["transfers"])])

        if task["bwlimit"]:
            args.extend(
                [
                    "--bwlimit",
                    " ".join(
                        [
                            f"{limit['time']},{str(limit['bandwidth']) + 'b' if limit['bandwidth'] else 'off'}"
                            for limit in task["bwlimit"]
                        ]
                    ),
                ]
            )

        if dry_run:
            args.append("--dry-run")

        args += config.extra_args

        args += shlex.split(task["args"])

        args += [task["transfer_mode"].lower()]

        if task["create_empty_src_dirs"]:
            args.append("--create-empty-src-dirs")

        snapshot = None
        if task["direction"] == "PUSH":
            if task["snapshot"]:
                snapshot_name = f"cloud_sync-{task.get('id', 'onetime')}"
                snapshot, path = create_snapshot(middleware, path, snapshot_name)

            args.extend([path, config.remote_path])
        else:
            args.extend([config.remote_path, path])

        env = env_mapping(
            "CLOUD_SYNC_",
            {
                **{
                    k: v
                    for k, v in task.items()
                    if k
                    in [
                        "id",
                        "description",
                        "direction",
                        "transfer_mode",
                        "encryption",
                        "filename_encryption",
                        "encryption_password",
                        "encryption_salt",
                        "snapshot",
                    ]
                },
                **provider,
                **task["attributes"],
                "path": path,
            },
        )
        run_script(job, "Pre-script", task["pre_script"], env)

        job.middleware.logger.trace("Running %r", args)
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        check_thread = threading.Thread(target=rclone_check_progress, args=(job, proc))
        check_thread.start()

        aborted = False
        try:
            while proc.poll() is None:
                if job.aborted_event.wait(timeout=0.2):
                    aborted = True
                    try:
                        middleware.call_sync2(middleware.services.service.terminate_process, proc.pid)
                    except CallError as e:
                        job.middleware.logger.warning(f"Error terminating rclone on cloud sync abort: {e!r}")
                        break
        finally:
            check_thread.join()

        if snapshot:
            try:
                middleware.call_sync2(
                    middleware.services.zfs.resource.snapshot.destroy_impl,
                    ZFSResourceSnapshotDestroyQuery(path=snapshot),
                )
            except Exception as e:
                middleware.logger.warning(f"Error deleting ZFS snapshot on cloud sync finish: {e!r}")

        refresh_credentials = REMOTES[credentials.provider.type].refresh_credentials
        if refresh_credentials:
            credentials_attributes = provider.copy()
            updated = False
            ini = configparser.ConfigParser()
            ini.read(config.config_path)
            for key, value in ini["remote"].items():
                if (
                    key in refresh_credentials
                    and key in credentials_attributes
                    and credentials_attributes[key] != value
                ):
                    logger.debug("Updating credentials attributes key %r", key)
                    credentials_attributes[key] = value
                    updated = True
            if updated:
                middleware.call_sync2(
                    middleware.services.cloudsync.credentials.update,
                    credentials.id,
                    {"provider": credentials_attributes},
                )

        if aborted:
            raise JobCancelledException()
        if proc.returncode != 0:
            message = "".join(job.internal_data.get("messages", []))
            if message and proc.returncode != 1:
                if not message.endswith("\n"):
                    message += "\n"
                message += f"rclone failed with exit code {proc.returncode}"
            raise CallError(message)

        run_script(job, "Post-script", task["post_script"], env)


# Prevents clogging job logs with progress reports every second
class RcloneVerboseLogCutter:
    PREFIXES = (
        re.compile(r"([0-9]{4}/[0-9]{2}/[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} |<6>)INFO {2}:\s*$"),
        re.compile(r"Transferred:\s+"),
        re.compile(r"Errors:\s+"),
        re.compile(r"Checks:\s+"),
        re.compile(r"Elapsed time:\s+"),
        re.compile(r"Transferring:"),
        re.compile(r" * .+"),
    )

    def __init__(self, interval: int):
        self.interval = interval

        self.buffer: list[str] = []
        self.counter = 0

    def notify(self, line: str) -> str | None:
        if self.buffer:
            # We are currently reading progress message

            self.buffer.append(line)

            if line.rstrip("\n"):
                # We are still reading message

                matches = any(prefix.match(line) for prefix in self.PREFIXES)

                if matches:
                    # Good, consuming this line to buffer and yet not writing it to logs
                    return None
                else:
                    # This was unexpected form of progress message (or not a progress message at all)

                    new_buffer = []
                    if self.PREFIXES[0].match(line):
                        # This line can be start of new progress message, ejecting it from buffer
                        self.buffer = self.buffer[:-1]
                        # And adding to new buffer
                        new_buffer = [line]

                    # Writing buffer to logs
                    try:
                        return self.flush()
                    finally:
                        self.buffer = new_buffer
            else:
                # This message ends with newline
                try:
                    if self.counter % self.interval == 0:
                        # Every {counter} times we still write this buffer to logs
                        return "".join(self.buffer)
                    else:
                        return None
                finally:
                    # Resetting state, ready to consume next line
                    self.buffer = []
                    self.counter += 1
        else:
            # We are not reading progress message

            if self.PREFIXES[0].match(line):
                # This is the first line of progress message
                self.buffer.append(line)
                return None
            else:
                return line

    def flush(self) -> str:
        try:
            return "".join(self.buffer)
        finally:
            self.buffer = []


def rclone_check_progress(job: Job, proc: subprocess.Popen[bytes]) -> None:
    assert proc.stdout is not None
    assert job.logs_fd is not None

    cutter = RcloneVerboseLogCutter(300)
    dropbox__restricted_content = False
    try:
        progress1 = None
        transferred1 = None
        progress2 = None
        transferred2 = None
        progress3 = None
        checks = None
        while True:
            read = proc.stdout.readline().decode("utf-8", "ignore")
            if read == "":
                break

            job.internal_data.setdefault("messages", [])
            job.internal_data["messages"] = job.internal_data["messages"][-4:] + [read]

            if "failed to open source object: path/restricted_content/" in read:
                job.internal_data["dropbox__restricted_content"] = True
                dropbox__restricted_content = True

            result = cutter.notify(read)
            if result:
                job.logs_fd.write(result.encode("utf-8", "ignore"))

            if reg := RE_TRANSF1.search(read):
                progress1 = int(reg.group("progress"))
                transferred1 = reg.group("progress_1")
            if reg := RE_TRANSF2.search(read):
                progress2 = int(reg.group("progress"))
                transferred2 = reg.group("progress_1") + reg.group("progress_2")
            if reg := RE_CHECKS.search(read):
                progress3 = int(reg.group("progress"))
                checks = f"checks: {reg.group('checks')}"

            progresses = [p for p in (progress1, progress2, progress3) if p is not None]
            if progresses:
                job.set_progress(min(progresses), ", ".join(filter(None, [transferred1, transferred2, checks])))
    finally:
        result = cutter.flush()
        if result:
            job.logs_fd.write(result.encode("utf-8", "ignore"))

    if dropbox__restricted_content:
        message = (
            "Dropbox sync failed due to restricted content being present in one of the folders. This may include\n"
            "copyrighted content or the DropBox manual PDF that appears in the home directory after signing up.\n"
            "All other files were synchronized, but no deletions were performed as synchronization is considered\n"
            "unsuccessful. Please inspect logs to determine which files are considered restricted and exclude them\n"
            "from your synchronization. If you think that files are restricted erroneously, contact\n"
            "Dropbox Support: https://www.dropbox.com/support\n"
        )
        job.internal_data["messages"] = [message]
        job.logs_fd.write(("\n" + message).encode("utf-8", "ignore"))


def rclone_encrypt_password(password: str) -> str:
    """
    Note: rclone uses aes-256-ctr with a hard-coded key to slightly obfuscate passwords in the configuration file. The
    following is required by the application itself.
    """
    key = bytes(
        [
            0x9C,
            0x93,
            0x5B,
            0x48,
            0x73,
            0x0A,
            0x55,
            0x4D,
            0x6B,
            0xFD,
            0x7C,
            0x63,
            0xC8,
            0x86,
            0xA9,
            0x2B,
            0xD3,
            0x90,
            0x19,
            0x8E,
            0xB8,
            0x12,
            0x8A,
            0xFB,
            0xF4,
            0xDE,
            0x16,
            0x2B,
            0x8B,
            0x95,
            0xF6,
            0x38,
        ]
    )

    aes = algorithms.AES256
    iv = ssl_random(aes.block_size // 8)
    counter = modes.CTR(iv)
    cipher = Cipher(aes(key), counter)
    encryptor = cipher.encryptor()
    encrypted = iv + encryptor.update(password.encode("utf-8")) + encryptor.finalize()
    return base64.urlsafe_b64encode(encrypted).decode("ascii").rstrip("=")


def lsjson_error_excerpt(error: str) -> str:
    excerpt = error.split("\n")[0]
    excerpt = re.sub(r"^[0-9]{4}/[0-9]{2}/[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} ", "", excerpt)
    excerpt = excerpt.replace('Failed to create file system for "remote:": ', "")
    excerpt = excerpt.replace("ERROR : : error listing: ", "")
    return excerpt


def ls(
    middleware: Middleware,
    credentials: CloudCredentialProvider,
    cloud_sync: CloudSyncListDirectory | None,
    path: str,
) -> list[dict[str, Any]]:
    middleware.call_sync("network.general.will_perform_activity", "cloud_sync")

    decrypt_filenames = cloud_sync is not None and cloud_sync.encryption and cloud_sync.filename_encryption
    with RcloneConfig(credentials, cloud_sync) as rclone_config:
        proc = subprocess.run(
            ["rclone", "--config", rclone_config.config_path, "lsjson", "remote:" + path],
            check=False,
            encoding="utf8",
            errors="ignore",
            capture_output=True,
        )
        if proc.returncode == 0:
            result = json.loads(proc.stdout)

            for item in result:
                item["Enabled"] = True

            if decrypt_filenames:
                if result:
                    decrypted_names = {}
                    # truenas_admin@prometheus[~]$ rclone cryptdecode --help
                    # Returns unencrypted file names when provided with a list of encrypted file
                    # names. List limit is 10 items
                    for batch in itertools.batched([item["Name"] for item in result], 10):
                        proc = subprocess.run(
                            ["rclone", "--config", rclone_config.config_path, "cryptdecode", "encrypted:", *batch],
                            check=False,
                            encoding="utf8",
                            errors="ignore",
                            capture_output=True,
                        )
                        for line in proc.stdout.splitlines():
                            try:
                                encrypted, decrypted = line.rstrip("\r\n").split(" \t ", 1)
                            except ValueError:
                                continue

                            if decrypted != "Failed to decrypt":
                                decrypted_names[encrypted] = decrypted

                    for item in result:
                        if item["Name"] in decrypted_names:
                            item["Decrypted"] = decrypted_names[item["Name"]]

            return result  # type: ignore[no-any-return]
        else:
            raise CallError(proc.stderr, extra={"excerpt": lsjson_error_excerpt(proc.stderr)})
