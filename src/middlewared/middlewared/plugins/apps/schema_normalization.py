from __future__ import annotations

import functools
import os
from typing import Any

from middlewared.api.current import AppEntry
from middlewared.service import ServiceContext

from .ix_apps.path import get_app_volume_path
from .resources import gpu_choices_internal
from .schema_action_context import apply_acls, update_volumes
from .schema_construction_utils import RESERVED_NAMES
from .schema_validation import validate_values

REF_MAPPING = {
    "definitions/certificate",
    "definitions/gpu_configuration",
    "normalize/acl",
    "normalize/ix_volume",
}


async def normalize_and_validate_values(
    context: ServiceContext, item_details: dict[str, Any], values: dict[str, Any], update: bool,
    app_dir: str, app_data: AppEntry | None = None, perform_actions: bool = True,
) -> dict[str, Any]:
    new_values = await validate_values(context, item_details, values, update, app_data)
    new_values, normalization_context = await normalize_values(
        context, item_details["schema"]["questions"], new_values, update, {
            "app": {
                "name": app_dir.split("/")[-1],
                "path": app_dir,
            },
            "actions": [],
        },
    )
    if perform_actions:
        await execute_actions(context, normalization_context)
    return new_values


async def execute_actions(context: ServiceContext, normalization_context: dict[str, Any]) -> None:
    for action in sorted(normalization_context["actions"], key=lambda d: 0 if d["method"] == "update_volumes" else 1):
        if action["method"] == "update_volumes":
            await update_volumes(context, action["args"][0], action["args"][1])
        elif action["method"] == "apply_acls":
            await apply_acls(context, action["args"][0])


async def normalize_values(
    context: ServiceContext, dict_attrs: list[dict[str, Any]], values: dict[str, Any],
    update: bool, normalization_context: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    for k in RESERVED_NAMES:
        # We reset reserved names from configuration as these are automatically going to
        # be added by middleware during the process of normalising the values
        values[k[0]] = k[1]()

    for attr in filter(lambda v: v["variable"] in values, dict_attrs):
        values[attr["variable"]] = await normalize_question(
            context, attr, values[attr["variable"]], update, values, normalization_context
        )

    return values, normalization_context


async def normalize_question(
    context: ServiceContext, attr_schema: dict[str, Any], value: Any, update: bool, complete_config: dict[str, Any],
    normalization_context: dict[str, Any],
) -> Any:
    schema_def = attr_schema["schema"]
    schema_type = schema_def["type"]
    if value is None and schema_type in ("dict", "list"):
        # This shows that the value provided has been explicitly specified as null and if validation
        # was okay with it, we shouldn't try to normalize it
        return value

    if schema_type == "dict":
        assert isinstance(value, dict)
        for attr in filter(lambda v: v["variable"] in value, schema_def.get("attrs", [])):
            value[attr["variable"]] = await normalize_question(
                context, attr, value[attr["variable"]], update, complete_config, normalization_context
            )

    if schema_type == "list":
        assert isinstance(value, list)
        for index, item in enumerate(value):
            if schema_def.get("items"):
                value[index] = await normalize_question(
                    context, schema_def["items"][0], item, update, complete_config, normalization_context
                )

    for ref in filter(lambda k: k in REF_MAPPING, schema_def.get("$ref", [])):
        match ref:
            case "definitions/certificate":
                func = normalize_certificate
            case "definitions/gpu_configuration":
                func = normalize_gpu_configuration
            case "normalize/acl":
                func = normalize_acl
            case "normalize/ix_volume":
                func = normalize_ix_volume
            case _:
                raise ValueError(f"Unknown {ref!r} ref type for normalization")

        value = await func(context, attr_schema, value, complete_config, normalization_context)

    return value


async def normalize_certificate(
    context: ServiceContext, attr_schema: dict[str, Any], value: Any, complete_config: dict[str, Any],
    normalization_context: dict[str, Any],
) -> Any:
    assert attr_schema["schema"]["type"] == "int"

    if not value:
        return value

    complete_config["ix_certificates"][value] = await context.middleware.call("certificate.get_instance", value)

    return value


async def normalize_gpu_configuration(
    context: ServiceContext, attr_schema: dict[str, Any], value: Any, complete_config: dict[str, Any],
    normalization_context: dict[str, Any],
) -> Any:
    gpu_choices = {
        gpu["pci_slot"]: gpu
        for gpu in await gpu_choices_internal(context) if not gpu["error"]
    }

    assert isinstance(value, dict)
    value["kfd_device_exists"] = kfd_exists()

    if all(gpu["vendor"] == "NVIDIA" for gpu in gpu_choices.values()):
        value["use_all_gpus"] = False

    for nvidia_gpu_pci_slot in list(value["nvidia_gpu_selection"]):
        if nvidia_gpu_pci_slot not in gpu_choices or gpu_choices[nvidia_gpu_pci_slot]["vendor"] != "NVIDIA":
            value["nvidia_gpu_selection"].pop(nvidia_gpu_pci_slot)

    return value


async def normalize_ix_volume(
    context: ServiceContext, attr_schema: dict[str, Any], value: Any, complete_config: dict[str, Any],
    normalization_context: dict[str, Any],
) -> Any:
    # Let's allow ix volume attr to be a string as well making it easier to define a volume in questions.yaml
    assert attr_schema["schema"]["type"] in ("dict", "string")

    if attr_schema["schema"]["type"] == "dict":
        assert isinstance(value, dict)
        vol_data = {"name": value["dataset_name"], "properties": value.get("properties") or {}}
        acl_dict = value.get("acl_entries", {})
    else:
        assert isinstance(value, str)
        vol_data = {"name": value, "properties": {}}
        acl_dict = None

    ds_name = vol_data["name"]

    action_dict = next((d for d in normalization_context["actions"] if d["method"] == "update_volumes"), None)
    if action_dict is None:
        normalization_context["actions"].append({
            "method": "update_volumes",
            "args": [normalization_context["app"]["name"], [vol_data]],
        })
    elif ds_name not in [v["name"] for v in action_dict["args"][-1]]:
        action_dict["args"][-1].append(vol_data)
    else:
        # We already have this in action dict, let's not add a duplicate
        return value

    host_path = os.path.join(get_app_volume_path(normalization_context["app"]["name"]), ds_name)
    complete_config["ix_volumes"][ds_name] = host_path

    if acl_dict:
        acl_dict["path"] = host_path
        await normalize_acl(context, {"schema": {"type": "dict"}}, acl_dict, complete_config, normalization_context)
    return value


async def normalize_acl(
    context: ServiceContext, attr_schema: dict[str, Any], value: Any, complete_config: dict[str, Any],
    normalization_context: dict[str, Any],
) -> Any:
    assert attr_schema["schema"]["type"] == "dict"

    if not value or any(not value[k] for k in ("entries", "path")):
        return value

    if (
        action_dict := next((d for d in normalization_context["actions"] if d["method"] == "apply_acls"), None)
    ) is None:
        normalization_context["actions"].append({
            "method": "apply_acls",
            "args": [{value["path"]: value}],
        })
    elif value["path"] not in action_dict["args"][-1]:
        action_dict["args"][-1][value["path"]] = value
    else:
        # We already have this in action dict, let's not add a duplicate
        return value

    return value


@functools.cache
def kfd_exists() -> bool:
    return os.path.exists("/dev/kfd")
