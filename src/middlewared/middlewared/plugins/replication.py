from datetime import time
import os
import pickle
import re
import subprocess

from middlewared.async_validators import resolve_hostname
from middlewared.client import Client
from middlewared.schema import accepts, Bool, Cron, Dict, Int, List, Patch, Str, Time
from middlewared.service import private, CallError, CRUDService, ValidationErrors
from middlewared.utils import Popen
from middlewared.utils.path import normpath
from middlewared.validators import Port, Range, ReplicationSnapshotNamingSchema, Unique


def is_child(child: str, parent: str):
    rel = os.path.relpath(child, parent)
    return rel == "." or not rel.startswith("..")


class ReplicationService(CRUDService):

    class Config:
        datastore = "storage.replication"
        datastore_prefix = "repl_"
        datastore_extend = "replication.extend"

    @private
    async def extend(self, data):
        data["periodic_snapshot_tasks"] = [
            await self.middleware.call("pool.snapshottask.extend", {k.replace("task_", ""): v
                                                                    for k, v in task.items()})
            for task in data.pop("tasks")
        ]

        if data["direction"] == "PUSH":
            data["also_include_naming_schema"] = data["naming_schema"]
            data["naming_schema"] = []
        if data["direction"] == "PULL":
            data["also_include_naming_schema"] = []

        schedule_name = self._schedule_name(data)
        if schedule_name:
            Cron.convert_db_format_to_schedule(data, schedule_name, begin_end=True)

        return data

    @private
    async def compress(self, data):
        del data["periodic_snapshot_tasks"]

        if data["direction"] == "PUSH":
            data["naming_schema"] = data.pop("also_include_naming_schema")

        schedule_name = self._schedule_name(data)
        if schedule_name:
            Cron.convert_schedule_to_db_format(data, schedule_name, begin_end=True)
        data.pop("schedule", None)
        data.pop("restrict_schedule", None)

        return data

    """
    @private
    async def replication_extend(self, data):

        remote_data = data.pop("remote")
        data["remote"] = remote_data["id"]
        data["remote_dedicateduser_enabled"] = remote_data["ssh_remote_dedicateduser_enabled"]
        data["remote_port"] = remote_data["ssh_remote_port"]
        data["remote_cipher"] = remote_data["ssh_cipher"].upper()
        data["remote_dedicateduser"] = remote_data["ssh_remote_dedicateduser"]
        data["remote_hostkey"] = remote_data["ssh_remote_hostkey"]
        data["remote_hostname"] = remote_data["ssh_remote_hostname"]

        if not os.path.exists(REPL_RESULTFILE):
            data["lastresult"] = {"msg": "Waiting"}
        else:
            with open(REPL_RESULTFILE, "rb") as f:
                file_data = f.read()
            try:
                results = pickle.loads(file_data)
                data["lastresult"] = results[data["id"]]
            except Exception:
                data["lastresult"] = {"msg": None}

        progressfile = f"/tmp/.repl_progress_{data["id"]}"
        if os.path.exists(progressfile):
            with open(progressfile, "r") as f:
                pid = int(f.read())
            title = await self.middleware.call("notifier.get_proc_title", pid)
            if title:
                reg = re.search(r"sending (\S+) \((\d+)%", title)
                if reg:
                    data["status"] = f"Sending {reg.groups()[0]}s {reg.groups()[1]}s"
                else:
                    data["status"] = "Sending"

        if "status" not in data:
            data["status"] = data["lastresult"].get("msg")


        return data

    @private
    async def validate_data(self, data, schema_name):
        verrors = ValidationErrors()

        remote_hostname = data.pop("remote_hostname")
        await resolve_hostname(
            self.middleware, verrors, f"{schema_name}.remote_hostname", remote_hostname
        )

        remote_dedicated_user_enabled = data.pop("remote_dedicateduser_enabled", False)
        remote_dedicated_user = data.pop("remote_dedicateduser", None)
        if remote_dedicated_user_enabled and not remote_dedicated_user:
            verrors.add(
                f"{schema_name}.remote_dedicateduser",
                "You must select a user when remote dedicated user is enabled"
            )

        if not await self.middleware.call(
                "pool.snapshottask.query",
                [("filesystem", "=", data.get("filesystem"))]
        ):
            verrors.add(
                f"{schema_name}.filesystem",
                "Invalid Filesystem"
            )

        remote_mode = data.pop("remote_mode", "MANUAL")

        remote_port = data.pop("remote_port")

        repl_remote_dict = {
            "ssh_remote_hostname": remote_hostname,
            "ssh_remote_dedicateduser_enabled": remote_dedicated_user_enabled,
            "ssh_remote_dedicateduser": remote_dedicated_user,
            "ssh_cipher": data.pop("remote_cipher", "STANDARD").lower()
        }

        if remote_mode == "SEMIAUTOMATIC":
            token = data.pop("remote_token", None)
            if not token:
                verrors.add(
                    f"{schema_name}.remote_token",
                    "This field is required"
                )
        else:
            remote_host_key = data.pop("remote_hostkey", None)
            if not remote_host_key:
                verrors.add(
                    f"{schema_name}.remote_hostkey",
                    "This field is required"
                )
            else:
                repl_remote_dict["ssh_remote_port"] = remote_port
                repl_remote_dict["ssh_remote_hostkey"] = remote_host_key

        if verrors:
            raise verrors

        data["begin"] = time(*[int(v) for v in data.pop("begin").split(":")])
        data["end"] = time(*[int(v) for v in data.pop("end").split(":")])

        data["compression"] = data["compression"].lower()

        data.pop("remote_hostkey", None)
        data.pop("remote_token", None)

        return verrors, data, repl_remote_dict
    """

    @accepts(
        Dict(
            "replication_create",
            Str("direction", enum=["PUSH", "PULL"], required=True),
            Str("transport", enum=["SSH", "SSH+NETCAT", "LOCAL", "LEGACY"], required=True),
            Int("ssh_credentials", null=True, default=None),
            Str("netcat_active_side", enum=["LOCAL", "REMOTE"], null=True, default=None),
            Int("netcat_active_side_port_min", null=True, default=None, validators=[Port()]),
            Int("netcat_active_side_port_max", null=True, default=None, validators=[Port()]),
            List("source_datasets", items=[Str("dataset", empty=False)], required=True, empty=False),
            Str("target_dataset", required=True, empty=False),
            Bool("recursive", required=True),
            List("exclude", items=[Str("dataset", empty=False)], default=[]),
            List("periodic_snapshot_tasks", items=[Int("periodic_snapshot_task")], default=[],
                 validators=[Unique()]),
            List("naming_schema", items=[
                Str("naming_schema", validators=[ReplicationSnapshotNamingSchema()])], default=[]),
            List("also_include_naming_schema", items=[
                Str("naming_schema", validators=[ReplicationSnapshotNamingSchema()])], default=[]),
            Bool("auto", required=True),
            Cron("schedule"),
            Cron("restrict_schedule"),
            Bool("only_matching_schedule", default=False),
            Bool("allow_from_scratch", default=False),
            Bool("hold_pending_snapshots", default=False),
            Str("retention_policy", enum=["SOURCE", "CUSTOM", "NONE"], required=True),
            Int("lifetime_value", null=True, default=None, validators=[Range(min=1)]),
            Str("lifetime_unit", null=True, default=None, enum=["HOUR", "DAY", "WEEK", "MONTH", "YEAR"]),
            Str("compression", enum=["LZ4", "PIGZ", "PLZIP"], null=True, default=None),
            Int("speed_limit", null=True, default=None, validators=[Range(min=1)]),
            Bool("dedup", default=True),
            Bool("large_block", default=True),
            Bool("embed", default=True),
            Bool("compressed", default=True),
            Int("retries", default=5, validators=[Range(min=1)]),
            Bool("enabled", default=True),
            register=True
        )
    )
    async def do_create(self, data):
        verrors = ValidationErrors()
        verrors.add_child("replication_create", await self._validate(data))

        if verrors:
            raise verrors

        periodic_snapshot_tasks = data["periodic_snapshot_tasks"]
        await self.compress(data)

        id = await self.middleware.call(
            "datastore.insert",
            self._config.datastore,
            data,
            {"prefix": self._config.datastore_prefix}
        )

        await self._set_periodic_snapshot_tasks(id, periodic_snapshot_tasks)

        return await self._get_instance(id)

    async def _validate(self, data):
        data["source_datasets"] = list(map(normpath, data["source_datasets"]))
        data["target_dataset"] = normpath(data["target_dataset"])
        data["exclude"] = list(map(normpath, data["exclude"]))

        verrors = ValidationErrors()

        # Direction

        snapshot_tasks = []

        if data["direction"] == "PUSH":
            e, snapshot_tasks = await self._query_periodic_snapshot_tasks(data["periodic_snapshot_tasks"])
            verrors.add_child("periodic_snapshot_tasks", e)

            if data["naming_schema"]:
                verrors.add("naming_schema", "This field has no sense for push replication")

            if data["schedule"]:
                if data["periodic_snapshot_tasks"]:
                    verrors.add("schedule", "Push replication can't be bound to periodic snapshot task and have "
                                            "schedule at the same time")
            else:
                if data["auto"] and not data["periodic_snapshot_tasks"]:
                    verrors.add("auto", "Push replication that runs automatically must be either "
                                        "bound to periodic snapshot task or have schedule")

            if data["restrict_schedule"]:
                if not data["auto"]:
                    verrors.add("restrict_schedule", "You can only have restrict-schedule for replication that runs "
                                                     "automatically")

                if not data["periodic_snapshot_tasks"]:
                    verrors.add("restrict_schedule", "You can only have restrict-schedule for replication that is "
                                                     "bound to periodic snapshot tasks")

        if data["direction"] == "PULL":
            if data["periodic_snapshot_tasks"]:
                verrors.add("periodic_snapshot_tasks", "This field has no sense for pull replication")

            if not data["naming_schema"]:
                verrors.add("naming_schema", "Naming schema is required for pull replication")

            if data["also_include_naming_schema"]:
                verrors.add("also_include_naming_schema", "This field has no sense for pull replication")

            if data["restrict_schedule"]:
                verrors.add("restrict_schedule", "Restricting schedule has no sense for pull replication")

            if data["hold_pending_snapshots"]:
                verrors.add("hold_pending_snapshots", "Pull replication tasks can't hold pending snapshots because "
                                                      "they don't do source retention")

        # Transport

        if data["transport"] == "SSH+NETCAT":
            if data["netcat_active_side"] is None:
                verrors.add("netcat_active_side", "You must choose active side for SSH+netcat replication")

            if data["netcat_active_side_port_min"] is None:
                verrors.add("netcat_active_side_port_min",
                            "You must specify minimum active side port for SSH+netcat replication")

            if data["netcat_active_side_port_max"] is None:
                verrors.add("netcat_active_side_port_max",
                            "You must specify maximum active side port for SSH+netcat replication")

            if data["netcat_active_side_port_min"] is not None and data["netcat_active_side_port_max"] is not None:
                if data["netcat_active_side_port_min"] > data["netcat_active_side_port_max"]:
                    verrors.add("netcat_active_side_port_max",
                                "Please specify value greater or equal than netcat_active_side_port_min")

            if data["compression"] is not None:
                verrors.add("compression", "Compression is not supported for SSH+netcat replication")

            if data["speed_limit"] is not None:
                verrors.add("speed_limit", "Speed limit is not supported for SSH+netcat replication")
        else:
            if data["netcat_active_side"] is not None:
                verrors.add("netcat_active_side", "This field only has sense for SSH+netcat replication")

            if data["netcat_active_side_port_min"] is not None:
                verrors.add("netcat_active_side_port_min", "This field only has sense for SSH+netcat replication")

            if data["netcat_active_side_port_max"] is not None:
                verrors.add("netcat_active_side_port_max", "This field only has sense for SSH+netcat replication")

        if data["transport"] == "LOCAL":
            if data["ssh_credentials"] is not None:
                verrors.add("ssh_credentials", "Remote credentials have no sense for local replication")

            if data["compression"] is not None:
                verrors.add("compression", "Compression has no sense for local replication")

            if data["speed_limit"] is not None:
                verrors.add("speed_limit", "Speed limit has no sense for local replication")
        else:
            if data["ssh_credentials"] is None:
                verrors.add("ssh_credentials", "SSH Credentials are required for non-local replication")
            else:
                try:
                    credentials = await self.middleware.call(
                        "keychaincredential.query", [["id", "=", data["ssh_credentials"]]], {"get": True})
                except IndexError:
                    verrors.add("ssh_credentials", "Specified credentials do not exist")
                else:
                    if credentials["type"] != "SSH_CREDENTIALS":
                        verrors.add("ssh_credentials", "Specified credentials are not SSH credentials")

        if data["transport"] == "LEGACY":
            for should_be_true in ["auto", "allow_from_scratch"]:
                if not data[should_be_true]:
                    verrors.add(should_be_true, "Legacy replication does not support disabling this option")

            for should_be_false in ["exclude", "naming_schema", "also_include_naming_schema",
                                    "only_matching_schedule", "dedup", "large_block", "embed", "compressed"]:
                if data[should_be_false]:
                    verrors.add(should_be_false, "Legacy replication does not support this option")

            if data["direction"] != "PUSH":
                verrors.add("direction", "Only push application is allowed for Legacy transport")

            legacy_dataset = None
            if len(data["source_datasets"]) != 1:
                verrors.add("source_datasets", "You can only have one source dataset for legacy replication")
            else:
                legacy_dataset = data["source_datasets"][0]

            for i, snapshot_task in enumerate(snapshot_tasks):
                if not snapshot_task["legacy_allowed"]:
                    verrors.add(f"periodic_snapshot_tasks.{i}", "This periodic snapshot task is not suitable for "
                                                                "legacy replication")

            if legacy_dataset is not None:
                for snapshot_task in await self.middleware.call(
                        "pool.snapshottask.query", [["id", "nin", [task["id"] for task in snapshot_tasks]],
                                                    ["enabled", "=", True]]):
                    if (snapshot_task["dataset"] == legacy_dataset or
                            (snapshot_task["recursive"] and is_child(legacy_dataset, snapshot_task["dataset"]))):
                        verrors.add("periodic_snapshot_tasks", "Legacy replication should include all enabled snapshot "
                                                               "tasks for it's source dataset")
                        break

        # Common for all directions and transports

        for i, source_dataset in enumerate(data["source_datasets"]):
            for snapshot_task in snapshot_tasks:
                if is_child(source_dataset, snapshot_task["dataset"]):
                    if data["recursive"]:
                        for exclude in snapshot_task["exclude"]:
                            if exclude not in data["exclude"]:
                                verrors.add("exclude", f"You should exclude {exclude!r} as bound periodic snapshot "
                                                       f"task dataset {snapshot_task['dataset']!r} does")
                    else:
                        if source_dataset in snapshot_task["exclude"]:
                            verrors.add(f"source_datasets.{i}", f"Dataset {source_dataset!r} is excluded by bound "
                                                                f"periodic snapshot task for dataset "
                                                                f"{snapshot_task['dataset']!r}")

        if not data["recursive"] and data["exclude"]:
            verrors.add("exclude", "Excluding child datasets is only supported for recursive replication")

        for i, v in enumerate(data["exclude"]):
            if not any(v.startswith(ds + "/") for ds in data["source_datasets"]):
                verrors.add(f"exclude.{i}", "This dataset is not a child of any of source datasets")

        if data["retention_policy"] == "CUSTOM":
            if data["lifetime_value"] is None:
                verrors.add("lifetime_value", "This field is required for custom retention policy")
            if data["lifetime_unit"] is None:
                verrors.add("lifetime_value", "This field is required for custom retention policy")
        else:
            if data["lifetime_value"] is not None:
                verrors.add("lifetime_value", "This field has no sense for specified retention policy")
            if data["lifetime_unit"] is not None:
                verrors.add("lifetime_unit", "This field has no sense for specified retention policy")

        return verrors

    async def _set_periodic_snapshot_tasks(self, replication_task_id, periodic_snapshot_tasks_ids):
        await self.middleware.call("datastore.delete", "storage.replication_repl_tasks",
                                   [["replication_id", "=", replication_task_id]])
        for periodic_snapshot_task_id in periodic_snapshot_tasks_ids:
            await self.middleware.call(
                "datastore.insert", "storage.replication_repl_tasks",
                {
                    "replication_id": replication_task_id,
                    "task_id": periodic_snapshot_task_id,
                },
            )

    """

        remote_hostname = data.get("remote_hostname")
        remote_dedicated_user = data.get("remote_dedicateduser")
        remote_port = data.get("remote_port")
        remote_https = data.pop("remote_https", False)
        remote_token = data.get("remote_token")
        remote_mode = data.get("remote_mode")

        verrors, data, repl_remote_dict = await self.validate_data(data, "replication_create")

        if remote_mode == "SEMIAUTOMATIC":

            remote_uri = f"ws{"s" if remote_https else ""}://{remote_hostname}:{remote_port}/websocket"

            try:
                with Client(remote_uri) as c:
                    if not c.call("auth.token", remote_token):
                        verrors.add(
                            "replication_create.remote_token",
                            "Please provide a valid token"
                        )
                    else:
                        try:
                            with open(REPLICATION_KEY, "r") as f:
                                publickey = f.read()

                            call_data = c.call("replication.pair", {
                                "hostname": remote_hostname,
                                "public-key": publickey,
                                "user": remote_dedicated_user,
                            })
                        except Exception as e:
                            raise CallError("Failed to set up replication " + str(e))
                        else:
                            repl_remote_dict["ssh_remote_port"] = call_data["ssh_port"]
                            repl_remote_dict["ssh_remote_hostkey"] = call_data["ssh_hostkey"]
            except Exception as e:
                verrors.add(
                    "replication_create.remote_token",
                    f"Failed to connect to remote host {remote_uri} with following exception {e}"
                )

        if verrors:
            raise verrors

        remote_pk = await self.middleware.call(
            "datastore.insert",
            "storage.replremote",
            repl_remote_dict
        )

        await self._service_change("ssh", "reload")

        data["remote"] = remote_pk

        pk = await self.middleware.call(
            "datastore.insert",
            self._config.datastore,
            data,
            {"prefix": self._config.datastore_prefix}
        )

        return await self._get_instance(pk)

    @accepts(
        Int("id", required=True),
        Patch(
            "replication_create", "replication_update",
            ("attr", {"update": True}),
            ("rm", {"name": "remote_mode"}),
            ("rm", {"name": "remote_https"}),
            ("rm", {"name": "remote_token"}),
        )
    )
    async def do_update(self, id, data):

        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)

        verrors, new, repl_remote_dict = await self.validate_data(new, "replication_update")

        new.pop("status")
        new.pop("lastresult")

        await self.middleware.call(
            "datastore.update",
            "storage.replremote",
            new["remote"],
            repl_remote_dict
        )

        await self._service_change("ssh", "reload")

        await self.middleware.call(
            "datastore.update",
            self._config.datastore,
            id,
            new,
            {"prefix": self._config.datastore_prefix}
        )

        return await self._get_instance(id)
    """

    @accepts(
        Int("id")
    )
    async def do_delete(self, id):

        replication = await self._get_instance(id)

        """
        try:
            if replication["lastsnapshot"]:
                zfsname = replication["lastsnapshot"].split("@")[0]
                await self.middleware.call("notifier.zfs_dataset_release_snapshots", zfsname, True)
        except Exception:
            pass

        await self.middleware.call("replication.remove_from_state_file", id)
        """

        response = await self.middleware.call(
            "datastore.delete",
            self._config.datastore,
            id
        )

        await self._service_change("ssh", "reload")

        return response

    """

    @private
    def remove_from_state_file(self, id):
        if os.path.exists(REPL_RESULTFILE):
            with open(REPL_RESULTFILE, "rb") as f:
                data = f.read()
            try:
                results = pickle.loads(data)
                results.pop(id, None)
                with open(REPL_RESULTFILE, "wb") as f:
                    f.write(pickle.dumps(results))
            except Exception as e:
                self.logger.debug("Failed to remove replication from state file %s", e)

        progressfile = "/tmp/.repl_progress_%d" % id
        try:
            os.unlink(progressfile)
        except Exception:
            pass

    @accepts()
    def public_key(self):
        if (os.path.exists(REPLICATION_KEY) and os.path.isfile(REPLICATION_KEY)):
            with open(REPLICATION_KEY, "r") as f:
                key = f.read()
        else:
            key = None
        return key

    @accepts(
        Str("host", required=True),
        Int("port", required=True),
    )
    async def ssh_keyscan(self, host, port):
        proc = await Popen([
            "/usr/bin/ssh-keyscan",
            "-p", str(port),
            "-T", "2",
            str(host),
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        key, errmsg = await proc.communicate()
        if proc.returncode != 0 or not key:
            if not errmsg:
                errmsg = "ssh key scan failed for unknown reason"
            else:
                errmsg = errmsg.decode()
            raise CallError(errmsg)
        return key.decode()

    @private
    @accepts(Dict(
        "replication-pair-data",
        Str("hostname", required=True),
        Str("public-key", required=True),
        Str("user"),
    ))
    async def pair(self, data):
        result = await self.middleware.call("keychaincredential.ssh_pair", {
            "remote_hostname": data["hostname"],
            "username": data["user"],
            "public_key": data["public-key"],
        })
        return {
            "ssh_port": result["port"],
            "ssh_hostkey": result["host_key"],
        }
    
    """

    def _schedule_name(self, data):
        if not data["auto"]:
            return None
        
        if data["direction"] == "PUSH":
            if data["periodic_snapshot_tasks"]:
                return "restrict_schedule"
            else:
                return "schedule"

        if data["directon"] == "PULL":
            return "schedule"

    async def _query_periodic_snapshot_tasks(self, ids):
        verrors = ValidationErrors()

        query_result = await self.middleware.call("pool.snapshottask.query", [["id", "in", ids]])

        snapshot_tasks = []
        for i, task_id in enumerate(ids):
            for task in query_result:
                if task["id"] == task_id:
                    snapshot_tasks.append(task)
                    break
            else:
                verrors.add(str(i), "This snapshot task does not exist")

        return verrors, snapshot_tasks
