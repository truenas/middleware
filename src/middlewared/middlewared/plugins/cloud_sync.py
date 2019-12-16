from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import accepts, Bool, Cron, Dict, Error, Int, Patch, Str
from middlewared.service import (
    CallError, CRUDService, ValidationErrors, filterable, item_method, job, private
)
from middlewared.utils import load_modules, load_classes, Popen, run

import asyncio
import base64
import codecs
from collections import namedtuple
import configparser
from Crypto import Random
from Crypto.Cipher import AES
from Crypto.Util import Counter
import json
import logging
import os
import re
import shlex
import subprocess
import tempfile

CHUNK_SIZE = 5 * 1024 * 1024
RE_TRANSF = re.compile(r"Transferred:\s*?(.+)$", re.S)

REMOTES = {}

OAUTH_URL = "https://freenas.org/oauth"

RcloneConfigTuple = namedtuple("RcloneConfigTuple", ["config_path", "remote_path"])

logger = logging.getLogger(__name__)


class RcloneConfig:
    def __init__(self, cloud_sync):
        self.cloud_sync = cloud_sync

        self.provider = REMOTES[self.cloud_sync["credentials"]["provider"]]

        self.tmp_file = None
        self.path = None

    def __enter__(self):
        self.tmp_file = tempfile.NamedTemporaryFile(mode="w+")

        # Make sure only root can read it as there is sensitive data
        os.chmod(self.tmp_file.name, 0o600)

        config = dict(self.cloud_sync["credentials"]["attributes"], type=self.provider.rclone_type)
        config = dict(config, **self.provider.get_credentials_extra(self.cloud_sync["credentials"]))
        if "pass" in config:
            config["pass"] = rclone_encrypt_password(config["pass"])

        remote_path = None

        if "attributes" in self.cloud_sync:
            config.update(dict(self.cloud_sync["attributes"], **self.provider.get_task_extra(self.cloud_sync)))

            remote_path = self.cloud_sync["attributes"]["folder"].rstrip()
            if self.provider.buckets:
                remote_path = f"{self.cloud_sync['attributes']['bucket']}/{remote_path}"
            remote_path = f"remote:{remote_path}"

            if self.cloud_sync.get("encryption"):
                self.tmp_file.write("[encrypted]\n")
                self.tmp_file.write("type = crypt\n")
                self.tmp_file.write(f"remote = {remote_path}\n")
                self.tmp_file.write("filename_encryption = {}\n".format(
                    "standard" if self.cloud_sync["filename_encryption"] else "off"))
                self.tmp_file.write("password = {}\n".format(
                    rclone_encrypt_password(self.cloud_sync["encryption_password"])))
                if self.cloud_sync.get("encryption_salt"):
                    self.tmp_file.write("password2 = {}\n".format(
                        rclone_encrypt_password(self.cloud_sync["encryption_salt"])))

                remote_path = "encrypted:/"

        self.tmp_file.write("[remote]\n")
        for k, v in config.items():
            self.tmp_file.write(f"{k} = {v}\n")

        self.tmp_file.flush()

        return RcloneConfigTuple(self.tmp_file.name, remote_path)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.tmp_file:
            self.tmp_file.close()


async def rclone(job, cloud_sync):
    if not os.path.exists(cloud_sync["path"]):
        raise CallError(f"Directory {cloud_sync['path']!r} does not exist")

    if os.stat(cloud_sync["path"]).st_dev == os.stat("/mnt").st_dev:
        raise CallError(f"Directory {cloud_sync['path']!r} must reside within volume mount point")

    # Use a temporary file to store rclone file
    with RcloneConfig(cloud_sync) as config:
        args = [
            "/usr/local/bin/rclone",
            "--config", config.config_path,
            "-v",
            "--stats", "1s",
            "--exclude", ".zfs",
            "--exclude", ".zfs/**",
        ] + shlex.split(cloud_sync["args"]) + [
            cloud_sync["transfer_mode"].lower(),
        ]

        if cloud_sync["direction"] == "PUSH":
            args.extend([cloud_sync["path"], config.remote_path])
        else:
            args.extend([config.remote_path, cloud_sync["path"]])

        job.middleware.logger.debug("Running %r", args)
        proc = await Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        check_cloud_sync = asyncio.ensure_future(rclone_check_progress(job, proc))
        await proc.wait()
        if proc.returncode != 0:
            await asyncio.wait_for(check_cloud_sync, None)

            message = "rclone failed"
            if "dropbox__restricted_content" in job.internal_data:
                message = "DropBox restricted content"
            raise ValueError(message)

        refresh_credentials = REMOTES[cloud_sync["credentials"]["provider"]].refresh_credentials
        if refresh_credentials:
            credentials_attributes = cloud_sync["credentials"]["attributes"].copy()
            updated = False
            ini = configparser.ConfigParser()
            ini.read(config.config_path)
            for key, value in ini["remote"].items():
                if (key in refresh_credentials and
                        key in credentials_attributes and
                        credentials_attributes[key] != value):
                    logger.debug("Updating credentials attributes key %r", key)
                    credentials_attributes[key] = value
                    updated = True
            if updated:
                await job.middleware.call("cloudsync.credentials.update", cloud_sync["credentials"]["id"], {
                    "attributes": credentials_attributes
                })

        return True


async def rclone_check_progress(job, proc):
    dropbox__restricted_content = False
    while True:
        read = (await proc.stdout.readline()).decode()
        if read == "":
            break
        if "failed to open source object: path/restricted_content/" in read:
            job.internal_data["dropbox__restricted_content"] = True
            dropbox__restricted_content = True
        job.logs_fd.write(read.encode("utf-8", "ignore"))
        reg = RE_TRANSF.search(read)
        if reg:
            transferred = reg.group(1).strip()
            if not transferred.isdigit():
                job.set_progress(None, transferred)

    if dropbox__restricted_content:
        message = "\n" + (
            "Dropbox sync failed due to restricted content being present in one of the folders. This may include\n"
            "copyrighted content or the DropBox manual PDF that appears in the home directory after signing up.\n"
            "All other files were synchronized, but no deletions were performed as synchronization is considered\n"
            "unsuccessful. Please inspect logs to determine which files are considered restricted and exclude them\n"
            "from your synchronization. If you think that files are restricted erroneously, contact\n"
            "Dropbox Support: https://www.dropbox.com/support"
        )
        job.logs_fd.write(message.encode("utf-8", "ignore"))


def rclone_encrypt_password(password):
    key = bytes([0x9c, 0x93, 0x5b, 0x48, 0x73, 0x0a, 0x55, 0x4d,
                 0x6b, 0xfd, 0x7c, 0x63, 0xc8, 0x86, 0xa9, 0x2b,
                 0xd3, 0x90, 0x19, 0x8e, 0xb8, 0x12, 0x8a, 0xfb,
                 0xf4, 0xde, 0x16, 0x2b, 0x8b, 0x95, 0xf6, 0x38])

    iv = Random.new().read(AES.block_size)
    counter = Counter.new(128, initial_value=int(codecs.encode(iv, "hex"), 16))
    cipher = AES.new(key, AES.MODE_CTR, counter=counter)
    encrypted = iv + cipher.encrypt(password.encode("utf-8"))
    return base64.urlsafe_b64encode(encrypted).decode("ascii").rstrip("=")


def validate_attributes(schema, data, additional_attrs=False):
    verrors = ValidationErrors()

    schema = Dict("attributes", *schema, additional_attrs=additional_attrs)

    try:
        data["attributes"] = schema.clean(data["attributes"])
    except Error as e:
        verrors.add(e.attribute, e.errmsg, e.errno)

    try:
        schema.validate(data["attributes"])
    except ValidationErrors as e:
        verrors.extend(e)

    return verrors


class CredentialsService(CRUDService):

    class Config:
        namespace = "cloudsync.credentials"

        datastore = "system.cloudcredentials"

    @accepts(Dict(
        "cloud_sync_credentials_create",
        Str("name", required=True),
        Str("provider", required=True),
        Dict("attributes", additional_attrs=True),
        register=True,
    ))
    async def do_create(self, data):
        await self._validate("cloud_sync_credentials_create", data)

        data["id"] = await self.middleware.call(
            "datastore.insert",
            "system.cloudcredentials",
            data,
        )
        return data

    @accepts(
        Int("id"),
        Patch(
            "cloud_sync_credentials_create",
            "cloud_sync_credentials_update",
            ("attr", {"update": True})
        )
    )
    async def do_update(self, id, data):
        await self._validate("cloud_sync_credentials_update", data, id)

        await self.middleware.call(
            "datastore.update",
            "system.cloudcredentials",
            id,
            data,
        )

        data["id"] = id

        return data

    @accepts(Int("id"))
    async def do_delete(self, id):
        await self.middleware.call(
            "datastore.delete",
            "system.cloudcredentials",
            id,
        )

    async def _validate(self, schema_name, data, id=None):
        verrors = ValidationErrors()

        if "name" in data:
            await self._ensure_unique(verrors, schema_name, "name", data["name"], id)

        if "provider" in data:
            if data["provider"] not in REMOTES:
                verrors.add(f"{schema_name}.provider", "Invalid provider")
            else:
                provider = REMOTES[data["provider"]]

                attributes_verrors = validate_attributes(provider.credentials_schema, data)
                verrors.add_child(f"{schema_name}.attributes", attributes_verrors)

        if verrors:
            raise verrors


class CloudSyncService(CRUDService):

    class Config:
        datastore = "tasks.cloudsync"
        datastore_extend = "cloudsync._extend"

    @filterable
    async def query(self, filters=None, options=None):
        tasks_or_task = await super().query(filters, options)

        jobs = {}
        for j in await self.middleware.call("core.get_jobs", [("method", "=", "cloudsync.sync")],
                                            {"order_by": ["id"]}):
            try:
                task_id = int(j["arguments"][0])
            except (IndexError, ValueError):
                continue

            if task_id in jobs and jobs[task_id]["state"] == "RUNNING":
                continue

            jobs[task_id] = j

        if isinstance(tasks_or_task, list):
            for task in tasks_or_task:
                task["job"] = jobs.get(task["id"])
        else:
            tasks_or_task["job"] = jobs.get(tasks_or_task["id"])

        return tasks_or_task

    @private
    async def _extend(self, cloud_sync):
        cloud_sync["credentials"] = cloud_sync.pop("credential")

        if "encryption_password" in cloud_sync:
            cloud_sync["encryption_password"] = await self.middleware.call(
                "notifier.pwenc_decrypt", cloud_sync["encryption_password"])
        if "encryption_salt" in cloud_sync:
            cloud_sync["encryption_salt"] = await self.middleware.call(
                "notifier.pwenc_decrypt", cloud_sync["encryption_salt"])

        Cron.convert_db_format_to_schedule(cloud_sync)

        return cloud_sync

    @private
    async def _compress(self, cloud_sync):
        if "credentials" in cloud_sync:
            cloud_sync["credential"] = cloud_sync.pop("credentials")

        if "encryption_password" in cloud_sync:
            cloud_sync["encryption_password"] = await self.middleware.call(
                "notifier.pwenc_encrypt", cloud_sync["encryption_password"])
        if "encryption_salt" in cloud_sync:
            cloud_sync["encryption_salt"] = await self.middleware.call(
                "notifier.pwenc_encrypt", cloud_sync["encryption_salt"])

        Cron.convert_schedule_to_db_format(cloud_sync)

        return cloud_sync

    @private
    async def _get_credentials(self, credentials_id):
        try:
            return await self.middleware.call("datastore.query", "system.cloudcredentials",
                                              [("id", "=", credentials_id)], {"get": True})
        except IndexError:
            return None

    @private
    async def _validate(self, verrors, name, data):
        if data["encryption"]:
            if not data.get("encryption_password"):
                verrors.add(f"{name}.encryption_password", "This field is required when encryption is enabled")

        credentials = await self._get_credentials(data["credentials"])
        if not credentials:
            verrors.add(f"{name}.credentials", "Invalid credentials")

        if verrors:
            raise verrors

        provider = REMOTES[credentials["provider"]]

        schema = []

        if provider.buckets:
            schema.append(Str("bucket", required=True, empty=False))

        schema.append(Str("folder", required=True))

        schema.extend(provider.task_schema)

        attributes_verrors = validate_attributes(schema, data, additional_attrs=True)

        if not attributes_verrors:
            await provider.pre_save_task(data, credentials, verrors)

        verrors.add_child(f"{name}.attributes", attributes_verrors)

        try:
            shlex.split(data["args"])
        except ValueError as e:
            verrors.add(f"{name}.args", f"Parse error: {e.args[0]}")

    @private
    async def _validate_folder(self, verrors, name, data):
        if data["direction"] == "PULL":
            folder = data["attributes"]["folder"].rstrip("/")
            if folder:
                folder_parent = os.path.normpath(os.path.join(folder, ".."))
                if folder_parent == ".":
                    folder_parent = ""
                folder_basename = os.path.basename(folder)
                ls = await self.list_directory(dict(
                    credentials=data["credentials"],
                    encryption=data.get("encryption"),
                    filename_encryption=data.get("filename_encryption"),
                    encryption_password=data.get("encryption_password"),
                    encryption_salt=data.get("encryption_salt"),
                    attributes=dict(data["attributes"], folder=folder_parent),
                    args=data.get("args"),
                ))
                for item in ls:
                    if item["Name"] == folder_basename:
                        if not item["IsDir"]:
                            verrors.add(f"{name}.attributes.folder", "This is not a directory")
                        break
                else:
                    verrors.add(f"{name}.attributes.folder", "Directory does not exist")

        if data["direction"] == "PUSH":
            credentials = await self._get_credentials(data["credentials"])

            provider = REMOTES[credentials["provider"]]

            if provider.readonly:
                verrors.add(f"{name}.direction", "This remote is read-only")

    @accepts(Dict(
        "cloud_sync",
        Str("description"),
        Str("direction", enum=["PUSH", "PULL"], required=True),
        Str("transfer_mode", enum=["SYNC", "COPY", "MOVE"], required=True),
        Str("path", required=True),
        Int("credentials", required=True),
        Bool("encryption", default=False),
        Bool("filename_encryption", default=False),
        Str("encryption_password"),
        Str("encryption_salt"),
        Cron("schedule"),
        Dict("attributes", additional_attrs=True),
        Str("args", default=""),
        Bool("enabled", default=True),
        register=True,
    ))
    async def do_create(self, cloud_sync):
        """
        Creates a new cloud_sync entry.

        .. examples(websocket)::

          Create a new cloud_sync using amazon s3 attributes, which is supposed to run every hour.

            :::javascript
            {
              "id": "6841f242-840a-11e6-a437-00e04d680384",
              "msg": "method",
              "method": "cloudsync.create",
              "params": [{
                "description": "s3 sync",
                "path": "/mnt/tank",
                "credentials": 1,
                "minute": "00",
                "hour": "*",
                "daymonth": "*",
                "month": "*",
                "attributes": {
                  "bucket": "mybucket",
                  "folder": ""
                },
                "enabled": true
              }]
            }
        """

        verrors = ValidationErrors()

        await self._validate(verrors, "cloud_sync", cloud_sync)

        if verrors:
            raise verrors

        await self._validate_folder(verrors, "cloud_sync", cloud_sync)

        if verrors:
            raise verrors

        cloud_sync = await self._compress(cloud_sync)

        cloud_sync["id"] = await self.middleware.call("datastore.insert", "tasks.cloudsync", cloud_sync)
        await self.middleware.call("service.restart", "cron")

        cloud_sync = await self._extend(cloud_sync)
        return cloud_sync

    @accepts(Int("id"), Patch("cloud_sync", "cloud_sync_update", ("attr", {"update": True})))
    async def do_update(self, id, data):
        """
        Updates the cloud_sync entry `id` with `data`.
        """
        cloud_sync = await self._get_instance(id)

        # credentials is a foreign key for now
        if cloud_sync["credentials"]:
            cloud_sync["credentials"] = cloud_sync["credentials"]["id"]

        cloud_sync.update(data)

        verrors = ValidationErrors()

        await self._validate(verrors, "cloud_sync_update", cloud_sync)

        if verrors:
            raise verrors

        await self._validate_folder(verrors, "cloud_sync_update", cloud_sync)

        if verrors:
            raise verrors

        cloud_sync = await self._compress(cloud_sync)

        await self.middleware.call("datastore.update", "tasks.cloudsync", id, cloud_sync)
        await self.middleware.call("service.restart", "cron")

        cloud_sync = await self._extend(cloud_sync)
        return cloud_sync

    @accepts(Int("id"))
    async def do_delete(self, id):
        """
        Deletes cloud_sync entry `id`.
        """
        await self.middleware.call("datastore.delete", "tasks.cloudsync", id)
        await self.middleware.call("service.restart", "cron")

    @accepts(Int("credentials_id"))
    async def list_buckets(self, credentials_id):
        credentials = await self._get_credentials(credentials_id)
        if not credentials:
            raise CallError("Invalid credentials")

        provider = REMOTES[credentials["provider"]]

        if not provider.buckets:
            raise CallError("This provider does not use buckets")

        return await self.ls({"credentials": credentials}, "")

    @accepts(Dict(
        "cloud_sync_ls",
        Int("credentials"),
        Bool("encryption", default=False),
        Bool("filename_encryption", default=False),
        Str("encryption_password"),
        Str("encryption_salt"),
        Dict("attributes", additional_attrs=True),
        Str("args"),
    ))
    async def list_directory(self, cloud_sync):
        verrors = ValidationErrors()

        await self._validate(verrors, "cloud_sync", cloud_sync)

        if verrors:
            raise verrors

        credentials = await self._get_credentials(cloud_sync["credentials"])

        if REMOTES[credentials["provider"]].buckets:
            path = f"{cloud_sync['attributes']['bucket']}/{cloud_sync['attributes']['folder']}"
        else:
            path = cloud_sync["attributes"]["folder"]

        return await self.ls(dict(cloud_sync, credentials=credentials), path)

    @private
    async def ls(self, config, path):
        with RcloneConfig(config) as config:
            proc = await run(["rclone", "--config", config.config_path, "lsjson", "remote:" + path],
                             check=False, encoding="utf8")
            if proc.returncode == 0:
                return json.loads(proc.stdout)
            else:
                raise CallError(proc.stderr)

    @item_method
    @accepts(Int("id"))
    @job(lock=lambda args: "cloud_sync:{}".format(args[-1]), lock_queue_size=1, logs=True)
    async def sync(self, job, id):
        """
        Run the cloud_sync job `id`, syncing the local data to remote.
        """

        cloud_sync = await self._get_instance(id)

        return await rclone(job, cloud_sync)

    @accepts()
    async def providers(self):
        return sorted(
            [
                {
                    "name": provider.name,
                    "title": provider.title,
                    "credentials_schema": [
                        {
                            "property": field.name,
                            "schema": field.to_json_schema()
                        }
                        for field in provider.credentials_schema
                    ],
                    "credentials_oauth": f"{OAUTH_URL}/{provider.name.lower()}" if provider.credentials_oauth else None,
                    "buckets": provider.buckets,
                    "task_schema": [
                        {
                            "property": field.name,
                            "schema": field.to_json_schema()
                        }
                        for field in provider.task_schema
                    ],
                }
                for provider in REMOTES.values() if provider.name != 'MEGA'
                # MEGA needs newer rclone
            ],
            key=lambda provider: provider["title"].lower()
        )


async def setup(middleware):
    for module in load_modules(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.path.pardir,
                                            "rclone", "remote")):
        for cls in load_classes(module, BaseRcloneRemote, []):
            remote = cls(middleware)
            REMOTES[remote.name] = remote
