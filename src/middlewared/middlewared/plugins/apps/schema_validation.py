from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from middlewared.api.current import AppEntry
from middlewared.service import ServiceContext, ValidationErrors

from .ix_apps.path import is_app_mounts_path
from .resources import certificate_choices, used_ports
from .schema_construction_utils import NOT_PROVIDED, RESERVED_NAMES, USER_VALUES, construct_schema

VALIDATION_REF_MAPPING = {
    'definitions/certificate',
    'definitions/port',
    'normalize/acl',
}

IMAGE_DIGEST_RE = re.compile(r'^sha256:[0-9a-f]{64}$')
IMAGE_REGISTRY_RE = re.compile(r'^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?(?::[0-9]{1,5})?$')


def validate_image_overrides(verrors: ValidationErrors, values: dict[str, Any]) -> None:
    """Validate the framework image override contract before schema rendering."""
    overrides = values.get('image_overrides', {})
    if overrides in (None, {}):
        return
    if overrides == []:
        return
    if isinstance(overrides, list):
        selectors = set()
        for index, item in enumerate(overrides):
            path = f'image_overrides.{index}'
            if not isinstance(item, dict) or not isinstance(item.get('selector'), str) or not item['selector'].strip():
                verrors.add(path, 'Each override requires a non-empty selector.')
                continue
            if item['selector'] in selectors:
                verrors.add(path, 'Duplicate image selector.')
            selectors.add(item['selector'])
        overrides = {
            item['selector']: {key: value for key, value in item.items() if key != 'selector' and value != ''}
            for item in overrides if isinstance(item, dict) and isinstance(item.get('selector'), str)
        }
    if not isinstance(overrides, dict):
        verrors.add('image_overrides', 'Must be a list of override entries or a mapping of image selector to override.')
        return
    allowed = {'registry', 'repository', 'tag', 'digest'}
    for name, override in overrides.items():
        path = f'image_overrides.{name}'
        if not isinstance(name, str) or not name:
            verrors.add('image_overrides', 'Image selectors must be non-empty strings.')
            continue
        if not isinstance(override, dict):
            verrors.add(path, 'Must be a mapping.')
            continue
        unknown = set(override) - allowed
        if unknown:
            verrors.add(path, f'Unsupported fields: {sorted(map(repr, unknown))}.')
        for key in set(override) & allowed:
            if (
                not isinstance(override[key], str)
                or not override[key].strip()
                or override[key] != override[key].strip()
                or any(char.isspace() for char in override[key])
            ):
                verrors.add(f'{path}.{key}', 'Must be a non-empty string.')
        if 'tag' in override and 'digest' in override:
            verrors.add(path, 'Specify tag or digest, not both.')
        if 'registry' in override:
            registry = override['registry']
            if not isinstance(registry, str) or not IMAGE_REGISTRY_RE.fullmatch(registry):
                verrors.add(f'{path}.registry', 'Must be a registry host or host:port, not a URL or path.')
        if 'digest' in override and not isinstance(override['digest'], str):
            verrors.add(f'{path}.digest', 'Must be a string.')
        elif 'digest' in override and not IMAGE_DIGEST_RE.fullmatch(override['digest']):
            verrors.add(f'{path}.digest', 'Must be exactly sha256 followed by 64 hexadecimal characters.')
# FIXME: See which are no longer valid
# https://github.com/truenas/middleware/blob/249ed505a121e5238e225a89d3a1fa60f2e55d27/src/middlewared/middlewared/
# plugins/chart_releases_linux/validation.py#L13


async def validate_values(
    context: ServiceContext, app_version_details: dict[str, Any], new_values: dict[str, Any], update: bool,
    app_data: AppEntry | None = None,
) -> dict[str, Any]:
    for k in RESERVED_NAMES:
        new_values.pop(k[0], None)

    config: USER_VALUES = NOT_PROVIDED if app_data is None or app_data.config is None else app_data.config

    verrors = ValidationErrors()
    validate_image_overrides(verrors, new_values)
    verrors.check()

    result = construct_schema(app_version_details, new_values, update, config)
    verrors = result['verrors']
    new_values = result['new_values']
    schema_name = result['schema_name']

    verrors.check()

    # If schema is okay, we see if we have question specific validation to be performed
    questions = {}
    for variable in app_version_details['schema']['questions']:
        questions[variable['variable']] = variable
    for key in filter(lambda k: k in questions, new_values):
        await validate_question(
            context=context,
            verrors=verrors,
            value=new_values[key],
            question=questions[key],
            schema_name=f'{schema_name}.{questions[key]["variable"]}',
            app_data=app_data,
        )

    verrors.check()

    return new_values


async def validate_question(
    context: ServiceContext, verrors: ValidationErrors, value: Any, question: dict[str, Any], schema_name: str,
    app_data: AppEntry | None,
) -> ValidationErrors:
    schema = question['schema']

    if schema['type'] == 'dict' and schema.get('attrs') and value:
        dict_attrs = {v['variable']: v for v in schema['attrs']}
        for k in filter(lambda k: k in dict_attrs, value):
            await validate_question(context, verrors, value[k], dict_attrs[k], f'{schema_name}.{k}', app_data)

    elif schema['type'] == 'list' and value:
        for index, item in enumerate(value):
            if schema['items']:
                await validate_question(
                    context, verrors, item, schema['items'][0],  # We will always have a single item schema
                    f'{schema_name}.{index}', app_data,
                )

    # FIXME: See if this is valid or not and port appropriately
    """
    if schema['type'] == 'hostpath':
        await self.validate_host_path_field(value, verrors, schema_name)
    """
    for validator_def in filter(lambda k: k in VALIDATION_REF_MAPPING, schema.get('$ref', [])):
        match validator_def:
            case 'definitions/certificate':
                func = validate_certificate
            case 'definitions/port':
                func = validate_port_available_on_node
            case 'normalize/acl':
                func = validate_acl_entries
            case _:
                raise ValueError(f'Unrecognized validator def {validator_def!r}')

        await func(context, verrors, value, schema_name, app_data)

    return verrors


async def validate_certificate(
    context: ServiceContext, verrors: ValidationErrors, value: Any, schema_name: str, app_data: AppEntry | None,
) -> None:
    if not value:
        return

    if not any(choice.id == value for choice in await certificate_choices(context)):
        verrors.add(schema_name, 'Unable to locate certificate.')
        return

    sub_verrors = await context.call2(
        context.s.certificate.cert_services_validation, value, schema_name, False,
    )
    if sub_verrors:
        verrors.extend(sub_verrors)


def _acl_path_has_data(path: str) -> bool:
    return next(Path(path).iterdir(), None) is not None


async def validate_acl_entries(
    context: ServiceContext, verrors: ValidationErrors, value: Any, schema_name: str, app_data: AppEntry | None,
) -> None:
    path = value.get('path')
    if not path or value.get('options', {}).get('force'):
        return

    if is_app_mounts_path(path):
        # Everything under the app mounts directory is created and owned by middleware, so whether it holds
        # data is not middleware's call to refuse a save over - a stored `force: false` on an ix volume would
        # otherwise make the config permanently unsavable once the app has written anything into its volume.
        # Skipping only drops the pre-flight message: filesystem.add_to_acl still refuses an unforced apply
        # over a populated path, and `force` is written in exactly one place - normalize_ix_volume - which
        # only ever sets it for the requesting app's own volume.
        return
    try:
        if await context.to_thread(_acl_path_has_data, path):
            verrors.add(schema_name, f'{path}: path contains existing data and `force` was not specified')
    except FileNotFoundError:
        verrors.add(schema_name, f'{path}: path does not exist')


async def validate_port_available_on_node(
    context: ServiceContext, verrors: ValidationErrors, value: Any, schema_name: str, app_data: AppEntry | None,
) -> None:
    for port_entry in (app_data.active_workloads.used_ports if app_data else []):
        for host_port in port_entry.host_ports:
            if value == host_port.host_port:
                # TODO: This still leaves a case where user has multiple ports in a single app and mixes
                #  them to the same value however in this case we will still get an error raised by docker.
                return

    if value in await used_ports(context) or value in await context.call2(context.s.port.ports_mapping, 'app'):
        verrors.add(schema_name, 'Port is already in use.')
